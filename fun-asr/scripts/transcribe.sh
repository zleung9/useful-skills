#!/usr/bin/env bash
# Fun-ASR 音频转写 — 阿里云百炼 async API
# 需要公网可访问的音频 URL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="fun-asr"
LANGUAGE=""
POLL_INTERVAL=3
POLL_TIMEOUT=300
OUTPUT_JSON=false
OUTPUT_FILE=""

usage() {
  cat >&2 <<'EOF'
Usage:
  transcribe.sh <audio-url> [options]

Options:
  --model <name>       模型，默认 fun-asr
  --language <code>    语言代码（可选）
  --poll-interval <n>  轮询间隔秒数（默认 3）
  --poll-timeout <n>   轮询超时秒数（默认 300）
  --json               输出 JSON 格式
  --out <path>         输出文件路径（默认 stdout）
  -h, --help           显示帮助

Examples:
  transcribe.sh https://example.com/audio.wav
  transcribe.sh oss://my-bucket/audio.wav --model paraformer-v2
EOF
  exit 2
}

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
fi

AUDIO_URL="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="${2:-}"; shift 2 ;;
    --language) LANGUAGE="${2:-}"; shift 2 ;;
    --poll-interval) POLL_INTERVAL="${2:-}"; shift 2 ;;
    --poll-timeout) POLL_TIMEOUT="${2:-}"; shift 2 ;;
    --json) OUTPUT_JSON=true; shift ;;
    --out) OUTPUT_FILE="${2:-}"; shift 2 ;;
    *) echo "Unknown: $1" >&2; usage ;;
  esac
done

# ── dashscope SDK 检查 ────────────────────────────────────────
if ! python3 -c "import dashscope" 2>/dev/null; then
  echo "Installing dashscope..." >&2
  pip3 install --break-system-packages dashscope -q
fi

python3 << PYEOF
import os, sys, json, time, dashscope
from dashscope.audio.asr import Transcription
from urllib.request import urlopen

dashscope.api_key = os.getenv('DASHSCOPE_API_KEY', '')
if not dashscope.api_key:
    print("ERROR: DASHSCOPE_API_KEY not set", file=sys.stderr)
    sys.exit(1)

audio_url = "${AUDIO_URL}"
model = "${MODEL}"
language = "${LANGUAGE}"
poll_interval = ${POLL_INTERVAL}
poll_timeout = ${POLL_TIMEOUT}
output_json = True if "${OUTPUT_JSON}" == "true" else False
output_file = "${OUTPUT_FILE}"

# 提交任务
kwargs = {'model': model, 'file_urls': [audio_url]}
if language:
    kwargs['language_hints'] = [language]

resp = Transcription.async_call(**kwargs)
if resp.status_code != 200:
    print(f"ERROR: Submit failed [{resp.status_code}]: {resp.output}", file=sys.stderr)
    sys.exit(1)

task_id = resp.output.task_id
print(f"Task submitted: {task_id}", file=sys.stderr)

# 轮询等待
elapsed = 0
while elapsed < poll_timeout:
    time.sleep(poll_interval)
    elapsed += poll_interval
    print(f"Polling... {elapsed}s/{poll_timeout}s", file=sys.stderr)

    wait_resp = Transcription.wait(task=task_id)
    status = wait_resp.output.task_status

    if status == 'SUCCEEDED':
        break
    elif status in ('FAILED', 'ERROR'):
        print(f"ERROR: Task {status}: {wait_resp.output}", file=sys.stderr)
        sys.exit(1)

if elapsed >= poll_timeout:
    print(f"ERROR: Timeout after {poll_timeout}s", file=sys.stderr)
    sys.exit(1)

# 获取结果
for transcription in wait_resp.output['results']:
    if transcription.get('subtask_status') == 'SUCCEEDED':
        url = transcription['transcription_url']
        result = json.loads(urlopen(url).read().decode('utf8'))

        if output_json:
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            texts = []
            for t in result.get('transcripts', []):
                for sent in t.get('sentences', []):
                    txt = sent.get('text', '').strip()
                    if txt:
                        texts.append(txt)
            output = ' '.join(texts)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            print(f"Written to: {output_file}", file=sys.stderr)
        else:
            print(output)
    else:
        print(f"WARNING: Subtask failed: {transcription.get('message', '')}", file=sys.stderr)
PYEOF
