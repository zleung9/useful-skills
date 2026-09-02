---
name: funasr
description: "阿里云 FunASR 语音识别 — 录音文件转写、说话人分离，支持 Fun-ASR / Paraformer / SenseVoice 模型。"
version: 1.1.0
author: OpenClaw
homepage: https://help.aliyun.com/zh/model-studio/recording-file-recognition
tags:
  [
    "audio", "transcription", "speech-to-text", "funasr", "fun-asr",
    "alibaba", "dashscope", "speaker-diarization", "meeting",
    "voice", "asr", "中文", "会议", "录音",
  ]
platforms: ["macos", "linux"]
metadata:
  {
    "openclaw":
      {
        "emoji": "🎙️",
        "requires":
          {
            "bins": ["python3", "ffmpeg"],
            "env": ["DASHSCOPE_API_KEY"],
          },
      },
  }
---

# FunASR 语音识别

阿里云百炼 FunASR（Fun-ASR / Paraformer / SenseVoice）录音文件识别，支持**说话人分离**、多语言、中文方言识别。

## 功能

- 🎙️ **录音转文字** — 会议、访谈、语音消息、任何音频文件
- 👥 **说话人分离** — 自动区分不同说话人（Fun-ASR 模型）
- 🌍 **多语言识别** — 中文（含方言）、英、日、韩、德、法、俄等 30+ 语种
- 📝 **时间戳** — 词级、句级时间戳
- 📁 **长音频** — 最长 12 小时、2GB 以内
- 🔗 **URL 输入** — 直接传公开音频 URL
- 🗣️ **歌唱识别** — 支持带背景音乐的歌曲转写（fun-asr-2025-11-07）

## 使用方式

### 语音消息 / 录音转写

```bash
# 基础转写（自动检测语言）
./scripts/transcribe audio.ogg

# 指定语言加速
./scripts/transcribe audio.m4a --language zh

# 启用说话人分离（会议、访谈必备）
./scripts/transcribe meeting.mp3 --diarize
```

### 会议 / 多人录音

```bash
# 推荐：说话人分离 + 标点 + 时间戳
./scripts/transcribe meeting.mp3 --diarize --format text

# 输出为 SRT 字幕（可导入视频编辑器）
./scripts/transcribe meeting.mp3 --diarize --format srt -o ./out/
```

### 输出格式

```bash
# 纯文字（默认）
./scripts/transcribe audio.mp3 --format text

# 完整 JSON（含时间戳、置信度）
./scripts/transcribe audio.mp3 --format json

# SRT 字幕文件
./scripts/transcribe audio.mp3 --format srt -o ./
```

### 其他用法

```bash
# 从公开 URL 转写
./scripts/transcribe https://example.com/audio.wav

# 指定模型
./scripts/transcribe audio.mp3 --model paraformer-v2   # 字幕/新闻访谈
./scripts/transcribe audio.mp3 --model sensevoice-v1   # 情感识别

# 语言提示（混合语言场景）
./scripts/transcribe audio.mp3 --language-hints zh,en,ja

# 批量处理
./scripts/transcribe ./*.wav -o ./transcripts/
```

## 工作流程

```
音频文件 (OGG/MP3/M4A/WAV/FLAC...)
       ↓ ffmpeg 转换为 16kHz mono PCM WAV
       ↓ 上传至 litterbox.catbox.moe (72h 临时托管)
       ↓ 调用 DashScope FunASR 异步 API
       ↓ 轮询任务状态 (自动)
       ↓ 拉取 transcription_url 获取结果
       ↓ 解析：说话人标签 / 时间戳 / 识别文本
```

## 输出示例

**--format text（说话人分离）：**
```
[SPEAKER_0 00:00 → 00:02]
  你好，今天的会议现在开始。
[SPEAKER_1 00:02 → 00:05]
  好的，我们先看第一项议题。
```

**--format srt：**
```
1
00:00:00,840 --> 00:00:02,040
[SPEAKER_0] 你可以使用语音吗？
```

## 模型说明

| 模型 | 适用场景 | 说话人分离 |
|------|---------|-----------|
| `fun-asr`（默认） | 通用，会议，多语言 | ✅ 支持 |
| `paraformer-v2` | 字幕生成，新闻访谈 | ❌ |
| `sensevoice-v1` | 情感识别，语音分析 | ❌ |

## 环境配置

**API Key**（已存放在 `~/.zshrc`）：
```bash
export DASHSCOPE_API_KEY='your-key'
```

**依赖**：
```bash
pip3 install dashscope --break-system-packages
brew install ffmpeg   # macOS
# apt install ffmpeg   # Linux
```

## 注意事项

- 需要网络连接（上传音频 + 调用 DashScope API）
- 说话人分离（`--diarize`）在安静环境、2-4 人场景效果最佳
- 长音频（>1小时）可能需要等待 2-5 分钟
- 临时托管链接 72 小时后自动失效，请及时保存结果
