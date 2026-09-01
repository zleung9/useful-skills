---
name: fun-asr
description: 转写音频文件为文本（阿里云百炼 Fun-ASR / Paraformer）。当用户发来音频文件需要转成文字时使用，支持中文（含方言）、英文、日韩等多语种。阿里云百炼异步接口，需要公网可访问的音频 URL。
metadata:
  {
    "openclaw": {
      "emoji": "🎙️",
      "requires": { "bins": ["python3"], "env": ["DASHSCOPE_API_KEY"] },
      "primaryEnv": "DASHSCOPE_API_KEY"
    }
  }
---

# Fun-ASR 音频转写（阿里云百炼）

调用阿里云百炼 Fun-ASR / Paraformer 录音文件识别 API。

## 使用方式

```bash
# 基本用法（公网 URL）
{baseDir}/scripts/transcribe.sh https://example.com/audio.wav

# 指定模型（fun-asr / paraformer-v2）
{baseDir}/scripts/transcribe.sh https://example.com/audio.wav --model fun-asr

# 指定语言
{baseDir}/scripts/transcribe.sh https://example.com/audio.wav --language zh

# 输出 JSON（含时间戳）
{baseDir}/scripts/transcribe.sh https://example.com/audio.wav --json

# 输出到文件
{baseDir}/scripts/transcribe.sh https://example.com/audio.wav --out /tmp/result.txt
```

## 模型选择

| 模型 | 适用场景 | 特点 |
|------|----------|------|
| `fun-asr` | 通用（默认推荐） | 支持中文7大方言+30语种，含歌唱识别 |
| `paraformer-v2` | 会议/字幕生成 | 长音频+标点+时间戳 |
| `sensevoice-v1` | 通用情感/语音 | SenseVoice 系列 |

## API Key

百炼 API Key，配置到 `~/.zshrc`：
```bash
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxx"
```

## 关键限制

阿里云百炼 Fun-ASR 是**异步接口**，需要音频文件能被阿里云服务器公网访问。如音频文件在本地，请先将文件上传到公网可访问的位置（阿里云 OSS / GitHub / 任意 CDN），得到 URL 后再传入。

## 接口特性

- **异步接口**：提交任务 → 轮询等待 → 获取结果
- 轮询间隔默认 3 秒，超时 300 秒
- 短音频（< 1 分钟）通常 5-15 秒完成
- 阿里云服务器需要能访问到音频 URL
