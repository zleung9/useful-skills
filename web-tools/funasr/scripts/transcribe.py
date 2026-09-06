#!/usr/bin/env python3
"""
FunASR (Fun-ASR / Paraformer / SenseVoice) transcription CLI.
阿里云百炼录音文件识别，支持说话人分离、多语言、长音频转写。
"""

import sys
import os
import json
import time
import tempfile
import argparse
import subprocess
import shutil
import re
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

try:
    import dashscope
    from dashscope.audio.asr import Transcription
except ImportError:
    print("Error: dashscope not installed", file=sys.stderr)
    print("Run: pip3 install dashscope --break-system-packages", file=sys.stderr)
    sys.exit(1)

from urllib import request
from http import HTTPStatus

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_MODEL = "fun-asr"

# Upload service: litterbox (temp file, 72h) — works through WAF
UPLOAD_SERVICES = [
    {
        "name": "litterbox",
        "url": "https://litterbox.catbox.moe/resources/internals/api.php",
        "field": "fileToUpload",
        "extra": {"reqtype": "fileupload", "time": "72h"},
    },
    {
        "name": "catbox",
        "url": "https://litter.catbox.moe/resources/internals/api.php",
        "field": "fileToUpload",
        "extra": {"reqtype": "fileupload", "time": "72h"},
    },
    {
        "name": "catbox-user",
        "url": "https://catbox.moe/user/api.php",
        "field": "fileToUpload",
        "extra": {"reqtype": "fileupload"},
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_api_key():
    """Read DASHSCOPE_API_KEY from environment."""
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        print("Error: DASHSCOPE_API_KEY not set in environment", file=sys.stderr)
        print("Add to ~/.zshrc: export DASHSCOPE_API_KEY='your-key'", file=sys.stderr)
        sys.exit(1)
    return key


def check_ffmpeg():
    """Verify ffmpeg is available."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg not found", file=sys.stderr)
        print("Install: brew install ffmpeg  (macOS)  or  apt install ffmpeg  (Linux)", file=sys.stderr)
        sys.exit(1)


def ensure_wav(input_path: str) -> str:
    """
    Convert any audio file to 16kHz mono PCM WAV using ffmpeg.
    Returns the path to the converted WAV file (in /tmp).
    """
    out_path = tempfile.mktemp(suffix=".wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: ffmpeg conversion failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return out_path


def upload_file(wav_path: str) -> str:
    """Try multiple upload services; return first working public URL."""
    last_error = None
    for svc in UPLOAD_SERVICES:
        name = svc["name"]
        upload_url = svc["url"]
        field = svc["field"]
        extra = svc["extra"]

        cmd = ["curl", "-s", "--max-time", "60", "-F", f"{field}=@{wav_path}"]
        for k, v in extra.items():
            cmd += ["-F", f"{k}={v}"]
        cmd.append(upload_url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=65)
            output = result.stdout.strip()
            # Accept direct URL response
            if output and (output.startswith("http://") or output.startswith("https://")):
                url = output.split()[0]
                sys.stderr.write(f"Uploaded via {name}: {url}\n")
                return url
            # Try JSON
            try:
                j = json.loads(output)
                url = j.get("url") or (j.get("data", {}).get("url"))
                if url:
                    sys.stderr.write(f"Uploaded via {name}: {url}\n")
                    return url
            except Exception:
                pass
            last_error = f"{name}: unexpected response: {output[:80]}"
        except subprocess.TimeoutExpired:
            last_error = f"{name}: timeout"
        except Exception as e:
            last_error = f"{name}: {e}"

        sys.stderr.write(f"Upload to {name} failed ({last_error}), trying next...\n")

    raise RuntimeError(
        f"All upload services failed. Last error: {last_error}\n"
        "FunASR requires a public HTTP URL for the audio file.\n"
        "Check network connectivity or set a custom upload URL via "
        "FUNASR_UPLOAD_URL environment variable."
    )


def is_url(path_or_url: str) -> bool:
    """Return True if input is a HTTP(S) URL."""
    parsed = urlparse(path_or_url)
    return bool(parsed.scheme) and parsed.scheme in ("http", "https")


def transcribe_funASR(
    audio_url: str,
    model: str = DEFAULT_MODEL,
    language: str | None = None,
    language_hints: list | None = None,
    diarize: bool = False,
    punctuation: bool = True,
    verbose: bool = False,
) -> dict:
    """
    Submit a FunASR transcription task and return the result dict.

    Args:
        audio_url: Public HTTP URL to the audio file (WAV/MP3/M4A/OGG/FLAC/...)
        model: fun-asr | paraformer-v2 | sensevoice-v1
        language: Single language code (e.g. 'zh', 'en'). None = auto detect.
        language_hints: List of language codes to boost detection (e.g. ['zh', 'en'])
        diarize: Enable speaker diarization (only fun-asr model)
        punctuation: Enable punctuation & capitalization
        verbose: Print API request/response details

    Returns:
        Dict with keys: text, speakers, sentences, raw
    """
    api_key = get_api_key()
    dashscope.api_key = api_key

    # Build model name
    model_name = model if model else DEFAULT_MODEL

    # Build async API kwargs
    api_kwargs = {
        "model": model_name,
        "language": language or "auto",
        "punctuation": punctuation,
    }
    if language_hints:
        api_kwargs["language_hints"] = language_hints
    if diarize and model_name == "fun-asr":
        api_kwargs["diarization_enabled"] = True
        api_kwargs["speaker_count"] = 10  # Max supported

    if verbose:
        sys.stderr.write(f"\n=== FunASR Request ===\n")
        sys.stderr.write(f"Model: {model_name}\n")
        sys.stderr.write(f"Audio URL: {audio_url}\n")
        sys.stderr.write(f"Params: {api_kwargs}\n")

    # Submit transcription task
    sys.stderr.write(f"Submitting transcription task...\n")
    task_response = Transcription.async_call(
        file_urls=[audio_url],
        **api_kwargs
    )

    if verbose:
        sys.stderr.write(f"Task response: {task_response}\n")

    if not task_response or task_response.get("code"):
        raise RuntimeError(
            f"Failed to submit task: {task_response.get('code', '')} "
            f"{task_response.get('message', '')}"
        )

    task_id = task_response["output"]["task_id"]
    sys.stderr.write(f"Task ID: {task_id}\n")

    # Wait for completion (handles polling internally)
    sys.stderr.write(f"Transcribing (auto-polling, max 10min)...\n")
    try:
        result_response = Transcription.wait(task_id)
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")

    if verbose:
        sys.stderr.write(f"Result response keys: {list(result_response.keys())}\n")

    # Extract transcription URL and fetch actual transcript
    output = result_response.get("output", {})
    results = output.get("results", [])

    if not results:
        raise RuntimeError(f"No transcription results returned. Task: {output.get('task_status')}")

    first_result = results[0]
    transcription_url = first_result.get("transcription_url")

    if not transcription_url:
        subtask_status = first_result.get("subtask_status", "UNKNOWN")
        raise RuntimeError(
            f"Transcription subtask failed: {subtask_status}. "
            f"Result: {first_result}"
        )

    # Fetch the actual transcription JSON
    if verbose:
        sys.stderr.write(f"Fetching transcript from: {transcription_url[:80]}...\n")

    try:
        from urllib import request as urllib_request
        req = urllib_request.Request(
            transcription_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib_request.urlopen(req, timeout=30) as resp:
            transcript_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to fetch transcription result: {e}")

    if verbose:
        sys.stderr.write(f"Transcript data keys: {list(transcript_data.keys())}\n")

    return transcript_data


def format_text(result: dict, diarize: bool = False) -> str:
    """Format result as human-readable text with optional speaker labels."""
    transcripts = result.get("transcripts", [])
    if not transcripts:
        return result.get("text", "")

    lines = []
    for t in transcripts:
        sentences = t.get("sentences", [])
        channel_id = t.get("channel_id", 0)

        if not sentences:
            text = t.get("text", "").strip()
            if text:
                lines.append(text)
            continue

        if diarize:
            # Group consecutive sentences by speaker
            current_speaker = None
            current_sentences = []

            for seg in sentences:
                speaker = seg.get("speaker_id", 0)
                begin_ms = seg.get("begin_time", 0)
                end_ms = seg.get("end_time", 0)
                seg_text = seg.get("text", "").strip()

                if speaker != current_speaker:
                    if current_sentences:
                        start_str = format_ms(current_sentences[0].get("begin_time", 0))
                        end_str = format_ms(current_sentences[-1].get("end_time", 0))
                        lines.append(f"[SPEAKER_{current_speaker} {start_str} → {end_str}]")
                        for cs in current_sentences:
                            lines.append(f"  {cs.get('text', '').strip()}")
                        lines.append("")
                    current_speaker = speaker
                    current_sentences = [seg]
                else:
                    current_sentences.append(seg)

            if current_sentences:
                start_str = format_ms(current_sentences[0].get("begin_time", 0))
                end_str = format_ms(current_sentences[-1].get("end_time", 0))
                lines.append(f"[SPEAKER_{current_speaker} {start_str} → {end_str}]")
                for cs in current_sentences:
                    lines.append(f"  {cs.get('text', '').strip()}")
        else:
            for seg in sentences:
                seg_text = seg.get("text", "").strip()
                if seg_text:
                    lines.append(seg_text)

    return "\n".join(lines).strip()


def format_ms(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS format."""
    ms = int(ms)
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def ms_to_srt(ms: int) -> str:
    """Convert milliseconds to SRT time format HH:MM:SS,mmm."""
    ms = int(ms)
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    ms = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_srt(result: dict) -> str:
    """Format result as SRT subtitles with speaker labels."""
    transcripts = result.get("transcripts", [])
    if not transcripts:
        return ""

    all_sentences = []
    for t in transcripts:
        sentences = t.get("sentences", [])
        for seg in sentences:
            begin_ms = seg.get("begin_time", 0)
            end_ms = seg.get("end_time", 0)
            text = seg.get("text", "").strip()
            speaker = seg.get("speaker_id")

            label = f"[SPEAKER_{speaker}]" if speaker is not None else ""
            all_sentences.append({
                "start": ms_to_srt(begin_ms),
                "end": ms_to_srt(end_ms),
                "text": f"{label} {text}" if label else text,
            })

    srt_lines = []
    for i, seg in enumerate(all_sentences, 1):
        srt_lines.append(f"{i}")
        srt_lines.append(f"{seg['start']} --> {seg['end']}")
        srt_lines.append(seg["text"])
        srt_lines.append("")
    return "\n".join(srt_lines).strip()


def main():
    parser = argparse.ArgumentParser(
        description="FunASR 语音转写 — 阿里云百炼录音文件识别",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="+", help="音频文件路径或公开 URL")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        choices=["fun-asr", "paraformer-v2", "sensevoice-v1"],
                        help="识别模型 (默认: fun-asr)")
    parser.add_argument("--language", default=None,
                        help="语言代码，如 zh/en/ja/ko/de/fr (默认: 自动检测)")
    parser.add_argument("--language-hints", "--hints", default=None,
                        help="语言提示，逗号分隔，如 zh,en,ja")
    parser.add_argument("--diarize", action="store_true",
                        help="启用说话人分离 (仅 fun-asr 模型)")
    parser.add_argument("--no-punct", dest="punctuation", action="store_false", default=True,
                        help="禁用标点符号和大小写")
    parser.add_argument("--format", dest="output_format", default="text",
                        choices=["text", "json", "srt"],
                        help="输出格式 (默认: text)")
    parser.add_argument("-o", "--output", dest="output_dir", default=None,
                        help="输出目录 (批量时)")
    parser.add_argument("--verbose", action="store_true",
                        help="显示详细 API 信息")

    args = parser.parse_args()

    # Validate model + diarize
    if args.diarize and args.model != "fun-asr":
        print("Warning: Speaker diarization only works with 'fun-asr' model. "
              "Ignoring --diarize.", file=sys.stderr)
        args.diarize = False

    # Check ffmpeg
    check_ffmpeg()

    # Parse language hints
    language_hints = None
    if args.language_hints:
        language_hints = [l.strip() for l in args.language_hints.split(",")]

    # Process each input
    inputs = args.input
    if len(inputs) > 1 and args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    for input_path in inputs:
        sys.stderr.write(f"\n=== Processing: {input_path} ===\n")

        # Determine audio URL
        if is_url(input_path):
            audio_url = input_path
            wav_path = None
        else:
            if not os.path.exists(input_path):
                print(f"Error: File not found: {input_path}", file=sys.stderr)
                continue

            # Convert to WAV
            sys.stderr.write(f"Converting to 16kHz mono WAV...\n")
            wav_path = ensure_wav(input_path)

            # Upload
            sys.stderr.write(f"Uploading audio...\n")
            audio_url = upload_file(wav_path)

        # Transcribe
        try:
            result = transcribe_funASR(
                audio_url=audio_url,
                model=args.model,
                language=args.language,
                language_hints=language_hints,
                diarize=args.diarize,
                punctuation=args.punctuation,
                verbose=args.verbose,
            )
        finally:
            # Cleanup temp WAV
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)

        # Output
        if args.output_format == "json":
            output = json.dumps(result, ensure_ascii=False, indent=2)
        elif args.output_format == "srt":
            output = format_srt(result)
        else:
            output = format_text(result, diarize=args.diarize)

        # Determine output destination
        if len(inputs) > 1 and args.output_dir:
            base = os.path.splitext(os.path.basename(input_path))[0]
            ext = "json" if args.output_format == "json" else ("srt" if args.output_format == "srt" else "txt")
            out_path = os.path.join(args.output_dir, f"{base}_funasr.{ext}")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
            sys.stderr.write(f"Written: {out_path}\n")
        else:
            print(output)

        # Also print metadata
        if args.output_format == "text":
            props = result.get("transcripts", [{}])[0].get("properties", {})
            duration = props.get("audio_duration_in_milliseconds", 0)
            if duration:
                sys.stderr.write(f"\nDuration: {duration/1000:.1f}s\n")
            if args.diarize:
                speakers = set()
                for t in result.get("transcripts", []):
                    for seg in t.get("sentences", []):
                        if "speaker" in seg:
                            speakers.add(seg["speaker"])
                if speakers:
                    sys.stderr.write(f"Speakers detected: {', '.join(sorted(speakers))}\n")


if __name__ == "__main__":
    main()
