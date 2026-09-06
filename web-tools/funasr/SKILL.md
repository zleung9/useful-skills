---
name: funasr
description: "阿里云百炼 FunASR 语音识别 — 音频转写为文字、说话人分离、多语言（中文方言/英日韩等）、SRT 字幕，支持云端 API 与本地离线两种模式。只要用户发来音频文件（会议录音、访谈、语音消息、歌曲）想转成文字、需要区分谁说了什么、要生成字幕，或想在无 API key / 离线环境下转写，就应使用本技能。"
version: 2.0.0
author: OpenClaw
homepage: https://help.aliyun.com/zh/model-studio/recording-file-recognition
tags:
  [
    "audio", "transcription", "speech-to-text", "funasr", "fun-asr",
    "alibaba", "dashscope", "speaker-diarization", "meeting",
    "voice", "asr", "offline", "中文", "会议", "录音", "语音转文字",
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

阿里云百炼 FunASR（Fun-ASR / Paraformer / SenseVoice）录音文件识别，支持**说话人分离**、多语言、中文方言识别。提供两种运行模式：

- **云端模式（默认）** — 调用百炼 API，质量最佳，需要 `DASHSCOPE_API_KEY` 和联网
- **本地离线模式** — 在本机跑 FunASR 开源模型，无需 API key，适合内网/离线/隐私敏感场景（中文为主）

## 功能

- 🎙️ **录音转文字** — 会议、访谈、语音消息、任何音频文件
- 👥 **说话人分离** — 自动区分不同说话人（云端 fun-asr 模型 / 本地 speaker 模式）
- 🌍 **多语言识别** — 中文（含方言）、英、日、韩、德、法、俄等 30+ 语种（云端）
- 💛 **情绪识别** — 本地 SenseVoice 模式附带情绪标签
- 🔥 **热词增强** — 本地模式支持热词文件，提升专有名词准确率
- 📝 **时间戳** — 句级时间戳，可导出 SRT 字幕
- 📁 **长音频** — 云端最长 12 小时、2GB 以内
- 🗣️ **歌唱识别** — 支持带背景音乐的歌曲转写（云端 fun-asr）

## 云端模式（默认）

入口：`scripts/transcribe`（自动处理本地文件：ffmpeg 转 16kHz WAV → 上传临时托管 → 调用 API → 轮询 → 输出结果）

### 基本用法

```bash
# 基础转写（本地文件，自动检测语言）
./scripts/transcribe audio.ogg

# 指定语言加速
./scripts/transcribe audio.m4a --language zh

# 启用说话人分离（会议、访谈必备）
./scripts/transcribe meeting.mp3 --diarize

# 从公开 URL 转写（跳过上传）
./scripts/transcribe https://example.com/audio.wav
```

### 输出格式

```bash
# 纯文字（默认，说话人分离时带 [SPEAKER_n 时间] 标签）
./scripts/transcribe audio.mp3 --format text

# 完整 JSON（含时间戳、置信度）
./scripts/transcribe audio.mp3 --format json

# SRT 字幕（可导入视频编辑器）
./scripts/transcribe meeting.mp3 --diarize --format srt -o ./out/

# 批量处理多个文件到输出目录
./scripts/transcribe ./*.wav -o ./transcripts/
```

### 高级选项

```bash
# 指定模型
./scripts/transcribe audio.mp3 --model paraformer-v2   # 字幕/新闻访谈
./scripts/transcribe audio.mp3 --model sensevoice-v1   # 情感识别

# 语言提示（混合语言场景，逗号分隔）
./scripts/transcribe audio.mp3 --language-hints zh,en,ja

# 调试：显示 API 请求/响应
./scripts/transcribe audio.mp3 --verbose
```

### 工作流程

```
音频文件 (OGG/MP3/M4A/WAV/FLAC...)
       ↓ ffmpeg 转换为 16kHz mono PCM WAV
       ↓ 上传至 litterbox/catbox 临时托管 (72h)
       ↓ 调用 DashScope FunASR 异步 API
       ↓ 自动轮询任务状态 (1-5 秒递增间隔)
       ↓ 拉取 transcription_url 获取结果
       ↓ 解析：说话人标签 / 时间戳 / 识别文本
```

### 输出示例

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

## 本地离线模式

入口：`scripts/funasr_transcribe.py`（使用开源 `funasr` pip 包，首次运行自动从 ModelScope 下载模型）

```bash
# 中文高精度识别（Paraformer-zh + VAD + 标点，默认）
python3 scripts/funasr_transcribe.py audio.mp3

# 多语言 + 情绪识别（SenseVoiceSmall）
python3 scripts/funasr_transcribe.py audio.mp3 --mode multi

# 中文 + 说话人分离
python3 scripts/funasr_transcribe.py meeting.mp3 --mode speaker

# 中文 + 时间戳
python3 scripts/funasr_transcribe.py audio.mp3 --mode timestamp

# 热词增强（每行一个词）
python3 scripts/funasr_transcribe.py audio.mp3 --hotword my_hotwords.txt

# JSON 输出
python3 scripts/funasr_transcribe.py audio.mp3 --json
```

**模式说明：**

| 模式 | 模型 | 特点 |
|------|------|------|
| `zh`（默认） | Paraformer-zh + VAD + 标点 | 中文高精度，支持热词 |
| `multi` | SenseVoiceSmall | 多语言 + 情绪 + 语种检测 |
| `speaker` | Paraformer-zh + CAM++ | 中文 + 说话人分离 |
| `timestamp` | Paraformer-zh | 中文 + 句级时间戳 |

**依赖安装：**
```bash
pip3 install funasr --break-system-packages   # 首次运行会下载模型（数百 MB）
```

**适用取舍：** 本地模式完全离线、无需 key、支持热词与情绪；但主要面向中文、速度较慢（首次要下载模型）。英文为主、超长音频（>1h）、多语种混合时优先用云端模式。

## 模型说明（云端）

| 模型 | 适用场景 | 说话人分离 |
|------|---------|-----------|
| `fun-asr`（默认） | 通用，会议，多语言（7 大方言 + 30 语种，含歌唱） | ✅ 支持 |
| `paraformer-v2` | 字幕生成，新闻访谈 | ❌ |
| `sensevoice-v1` | 情感识别，语音分析 | ❌ |

## 环境配置

**API Key**（云端模式必需，已存放在 `~/.zshrc`）：
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

- 云端模式需要联网（上传音频 + 调用 DashScope API）
- 说话人分离（`--diarize` / `--mode speaker`）在安静环境、2-4 人场景效果最佳
- 长音频（>1 小时）可能需要等待 2-5 分钟
- 临时托管链接 72 小时后自动失效，请及时保存结果
- 云端 API 为异步接口：提交任务 → 自动轮询 → 拉取结果，轮询间隔 1-5 秒递增
