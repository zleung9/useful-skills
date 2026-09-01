---
name: pdf-vision-analysis
description: 当用户要求分析 PDF 文件但 Hermes 的 vision_analyze 工具不工作时，通过 delegate_task 调用 OpenClaw 子 agent 来完成 PDF 解读。适用于发票、扫描件、图片型 PDF 等需要视觉分析的场景。
---

# PDF 视觉分析 — OpenClaw 委托法

当用户发送 PDF 文件并要求分析时，如果 `vision_analyze` 对本地 PDF 文件失败（超时或报错 "need to see image"），使用本技能。

## 核心方法

通过 `delegate_task` + `acp_command='openclaw'` 委托给 OpenClaw 的 agent 处理，OpenClaw 内置了完整的 PDF→图片→vision 流程。

## 触发条件

- 用户发送 PDF 文件
- `vision_analyze` 工具对 PDF 文件失败（timeout 或 "Only real image files supported"）
- 用户明确说"模型支持 PDF"

## 操作步骤

### 1. 使用 delegate_task 委托给 OpenClaw

```python
delegate_task(
    goal="请分析这张电子发票 PDF 文件，提取所有文字信息。PDF 文件路径：<PDF完整路径>。请用 PDF 提取工具提取发票文字，如果文字太少则将页面渲染成图片后用 vision 模型分析。提取内容：发票号码、日期、购买方、销售方、商品明细、金额、税率等全部信息。",
    context="用户 Zhu Liang 的 OpenClaw 环境已配置 MiniMax 模型。",
    toolsets=["terminal", "file", "web"],
    acp_command="openclaw"
)
```

### 2. 返回结果

子 agent 会返回完整的发票/文档信息。

## 关键经验

- **OpenClaw 的 PDF 处理流程**（来自 `input-files-y7leIqDP.js` + `pdf-extract-iu4QUGpR.js`）：
  1. 用 `pdfjs-dist` 提取文字
  2. 如果文字 <200 字符（图片型 PDF），用 `@napi-rs/canvas` 把页面渲染成 PNG
  3. 渲染后的图片发送给 vision 模型分析

- **MiniMax CN API 端点**：全球端点 `api.minimax.chat` 比中国端点 `api.minimaxi.com` 更稳定（代理下 `Connection reset` 更少）

- **MiniMax VL 额度**：VL 模型（`MiniMax-VL-01`）和 M2.7 是独立计费的，VL 可能额度不足而 M2.7 正常

- **Hermes vision_analyze 局限性**：对本地图片文件支持不稳定（超时/报错），但对 URL 图片或 base64 图片数据可能有效

## 不要做的事

- ❌ 不要用 `vision_analyze` 直接分析 PDF 文件（不支持）
- ❌ 不要尝试 pip 安装 pdfjs-dist（Node.js 库，Python 无法使用）
- ❌ 不要花时间找 API key 直接调 API（额度、代理、端点问题多）
- ✅ 直接委托 OpenClaw 是最可靠的方法
