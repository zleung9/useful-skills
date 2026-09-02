---
name: dida365
description: "Dida365 (TickTick) 任务管理 API 集成。从 Dida365 读取任务，同步到 GOALS.md 格式。"
version: 0.1
author: 梁柱私人助理
tags: ["任务管理", "Dida365", "TickTick", "待办"]
platforms: ["macos", "linux"]
metadata:
  {
    openclaw:
      {
        emoji: "✅",
        requires:
          {
            bins: ["python3", "curl"],
            env: ["DIDA365_TOKEN"],
          },
      },
  }
---

# Dida365 任务集成

从 Dida365 API 读取任务列表，同步到 GOALS.md 格式。

## 快速开始

### 1. 获取 API Token

1. 打开 [https://dida365.com](https://dida365.com) 网页版并登录
2. 进入 **设置 → 开放 API**
3. 创建应用，获取 **Client ID** 和 **Client Secret**
4. 获取 **Refresh Token**（OAuth2 流程）

### 2. 配置环境变量

```bash
export DIDA365_TOKEN="your_refresh_token_here"
export DIDA365_CLIENT_ID="your_client_id"
export DIDA365_CLIENT_SECRET="your_client_secret"
```

### 3. 读取 Dida365 任务

```bash
python3 ~/.agents/skills/dida365/scripts/sync.py --read
```

### 4. 同步到 GOALS.md

```bash
python3 ~/.agents/skills/dida365/scripts/sync.py --sync-goals
```

## API 认证

Dida365 使用 OAuth2 的 Refresh Token 方式：

```python
REFRESH_TOKEN_URL = "https://api.dida365.com/oauth2/token"
API_BASE = "https://api.dida365.com/v1"
```

每次调用 API 前需要 refresh 获取 Access Token，有效期 1 小时。

## 任务同步格式

Dida365 任务 → GOALS.md 格式：

- **标题** → 任务描述
- **截止日期** → 时间维度（今日/本周/下周）
- **优先级** → 对应 🔴🟡🟢⚪
- **所属清单** → 分类标签

## 注意事项

- Dida365 任务优先级：p1(高), p2(中), p3(低)，无优先级
- 只同步**有截止日期**的任务
- 已完成任务默认不显示（加 `--include-done` 可包含）
