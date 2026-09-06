#!/usr/bin/env python3
"""
FunASR 音频转录 & 分析工具
==========================
支持功能：
  1. 中文语音识别 (Paraformer-zh + VAD + 标点)
  2. 多语言识别 + 情绪识别 (SenseVoiceSmall)
  3. 说话人分离 (Speaker Diarization)
  4. 热词增强 (Hotwords / WFST)
  5. 时间戳输出

用法:
  python3 funasr_transcribe.py <音频文件> [--mode <模式>] [--hotword <热词文件>] [--lang <语言>]

模式 (--mode):
  zh           : 中文识别 (Paraformer-zh, 默认)
  multi        : 多语言 + 情绪 (SenseVoiceSmall)
  speaker      : 中文 + 说话人分离
  timestamp    : 中文 + 时间戳
"""

import sys
import json

try:
    from funasr import AutoModel
except ImportError:
    print("Error: funasr not installed (本地离线模式需要)", file=sys.stderr)
    print("Run: pip3 install funasr --break-system-packages", file=sys.stderr)
    print("(首次运行会自动从 ModelScope 下载模型)", file=sys.stderr)
    sys.exit(1)


def mode_zh(audio_path: str, hotword_path: str = None) -> list:
    """Paraformer-zh: 中文高精度识别, 支持热词"""
    print("模式: 中文高精度识别 (Paraformer-zh + VAD + 标点)")
    model = AutoModel(
        model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        punc_model="iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727-pytorch",
    )
    kwargs = {"input": audio_path}
    if hotword_path:
        kwargs["hotword"] = hotword_path
        print(f"  热词文件: {hotword_path}")
    return model.generate(**kwargs)


def mode_multi(audio_path: str) -> list:
    """SenseVoiceSmall: 多语言识别 + 情绪 + 语种检测"""
    print("模式: 多语言识别 + 情绪 (SenseVoiceSmall)")
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
    )
    return model.generate(
        input=audio_path,
        language="auto",  # 自动检测语言: zh, en, ja, ko, etc.
        use_itn=True,     # 逆文本正则化
    )


def mode_speaker(audio_path: str) -> list:
    """说话人分离 + 中文识别"""
    print("模式: 中文识别 + 说话人分离")
    model = AutoModel(
        model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        punc_model="iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727-pytorch",
        spk_model="iic/speech_campplus_sv_zh-cn_16k-common",
    )
    return model.generate(input=audio_path)


def mode_timestamp(audio_path: str) -> list:
    """中文识别 + 句级时间戳"""
    print("模式: 中文识别 + 时间戳")
    model = AutoModel(
        model="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        punc_model="iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727-pytorch",
    )
    return model.generate(input=audio_path, output_dir="./funasr_output")


MODES = {
    "zh": mode_zh,
    "multi": mode_multi,
    "speaker": mode_speaker,
    "timestamp": mode_timestamp,
}


def format_result(result, mode: str):
    """格式化输出"""
    if not isinstance(result, list):
        print(result)
        return

    for i, item in enumerate(result):
        text = item.get("text", "")
        timestamp = item.get("timestamp", "")

        if mode == "speaker":
            spk = item.get("spk", "?")
            print(f"[说话人{spk}] {text}")
        elif mode == "timestamp":
            start = item.get("start", "")
            end = item.get("end", "")
            ts = f"[{start}-{end}]" if start else ""
            print(f"{ts} {text}")
        else:
            if "emo" in item:
                # SenseVoice 情绪标签: happy/sad/angry/neutral
                print(f"[{item.get('emo', '')}] {text}")
            else:
                print(text)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FunASR 音频转录工具")
    parser.add_argument("audio", help="音频文件路径")
    parser.add_argument("--mode", "-m", default="zh", choices=MODES.keys(),
                        help="转录模式 (默认: zh)")
    parser.add_argument("--hotword", "-w", help="热词文件路径 (每行一个词)")
    parser.add_argument("--json", "-j", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    mode_fn = MODES[args.mode]
    kwargs = {"audio_path": args.audio}
    if args.mode == "zh" and args.hotword:
        kwargs["hotword_path"] = args.hotword

    result = mode_fn(**kwargs)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("--- 转录结果 ---")
        format_result(result, args.mode)
