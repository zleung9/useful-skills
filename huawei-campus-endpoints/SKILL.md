---
name: huawei-campus-endpoints
description: 华为园区网大模型代理端点 — 4 个 vLLM 代理模型（Qwen3.6, DeepSeek-V4, GLM-5, Intern-S2）的连通性和使用方法。端点通过校园网 10.26.15.52:30081 暴露，不需要代理。
triggers:
  - 用户提到华为端点、huawei endpoint、校园网模型、campus model
  - 用户要测试或配置 10.26.15.52:30081 上的模型
  - 用户问"有哪些本地模型可用"或"园区网模型"
---

# 华为园区网大模型端点

## 概览

4 个 vLLM OpenAI 兼容端点，部署在校园网 `10.26.15.52:30081`，API key 统一共享。

> **API key**: `sk-bSQgLAQtr529RnVzaW9ugmlueZGggUVS`（共享 key，2026-07-27 实测 4 个端点全通）。不要写死 key 在代码/文档中。
>
> **注意**: Intern-S2 有独立权限控制——部分 key 对 Intern-S2 返回 401，对其他 3 个模型正常。

| # | 显示名称 | 真实 model id | Hash 前缀 | Context | chat | tool_call | stream | vision |
|---|---------|-------------|-----------|---------|------|-----------|--------|--------|
| 1 | Qwen3.6-35B-A3B | `Qwen3.6-35B-A3B` | `ccb44b4cfe18439f8affd07babd0810e` | ~133K | ✅ | ✅ | ✅ | ✅ |
| 2 | DeepSeek-V4-Flash-w8a8-mtp | `DeepSeek-V4-Flash-w8a8-mtp` | `132bc0947fc64cc79e22618a60394789` | ~131K | ✅ | ✅ | ✅ | ❌ |
| 3 | GLM-5.1-w8a8 | `glm-5` | `7f82733149be43a1b8f26196b2202fa6` | ~133K | ✅ | ✅ | ✅ | ❌ |
| 4 | Intern-S2-Preview | `intern-s2-preview` | `784fa5165cd6424fa19764c8c6b95274` | ~256K | ✅ | ❌ | ✅ | ❌ |

> **已下线端点**: Qwen3.6-35B-A3B (128K 长上下文版，hash `f6f71ef40c934f75920fb8decd6db721`) 于 2026-07-27 确认已下线（返回 404 "服务尚未启动或异常"）。

## 测试

### 快速测试（单端点 curl）

```bash
# 测试 chat（以 DeepSeek-V4 为例）
curl -s http://10.26.15.52:30081/132bc0947fc64cc79e22618a60394789/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash-w8a8-mtp","messages":[{"role":"user","content":"Say hello"}],"max_tokens":50}'

# 测试 tool call（以 GLM-5 为例）
curl -s http://10.26.15.52:30081/7f82733149be43a1b8f26196b2202fa6/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5","messages":[{"role":"user","content":"What is 2+2?"}],"tools":[{"type":"function","function":{"name":"calc","parameters":{"type":"object","properties":{"expr":{"type":"string"}}}}}],"max_tokens":200}'

# 列出端点可用模型
curl -s http://10.26.15.52:30081/<hash>/v1/models \
  -H "Authorization: Bearer $KEY"
```

### 全端点批量测试（Python 脚本）

使用技能内置脚本：

```bash
python3 /Users/zliang/Nutstore\ Files/skills/huawei-campus-endpoints/scripts/test_all_endpoints.py
```

## 关键陷阱

1. **model 字段必须用服务端返回的真实 id**
   - GLM 必须用 `glm-5`，不能用 `GLM-5.1-w8a8`（否则网关返回 500）
   - 其他端点 id 与显示名一致，但建议先 `GET /v1/models` 确认

2. **API key 状态可能因模型而异 — Intern-S2 有独立权限控制** — 部分对 Intern-S2 返回 401 的 key 对其他 3 个模型正常。检测到 401 时，逐个 hash 端点测试而非只测一个就下结论。

3. **Qwen3.6 的 thinking 泄露（实测确认无法关闭）**
   - **华为部署端的 Qwen3.6 会泄露 thinking chain**——输出以英文 "Here's a thinking process:" 开头，占 30-60% 输出 token
   - `enable_thinking: false`、`chat_template_kwargs: {thinking: false}`、`thinking: false`、system prompt 指令——**全部无效**（2026-06-03 实测 4 种方法均无法抑制）
   - **原因**：vLLM 部署时未配置正确的 chat_template 来隔离 `更低` 标签，模型内部生成的 thinking 被原样塞入 `message.content`
   - **缓解**：(a) 后处理剥离（从 "Here's a thinking process" 到第一个正式标题/段落前的内容）；(b) 调大 max_tokens（thinking 吃掉大量配额）；(c) 向服务器管理员申请修复 chat_template 配置
   - 工具调用时需要确保 max_tokens 足够大（推荐 4096+），否则思考链会占用输出空间导致工具调用失败

4. **GLM-5.1 也是 thinking 模型** — 需要较大的 max_tokens（建议 ≥ 512），否则 thinking chain 会消耗完输出配额导致 content 为空。GLM 的 thinking 内容在 `reasoning` 字段而非 `content` 中，所以 `content` 本身是干净的（与 Qwen3.6 不同）。

5. **直连，无需代理** — 校园网内部 IP，不需要走 `http://127.0.0.1:7890` 代理

6. **API key 泄露** — API key 是共享 key，文档中写 sk-xxx 占位即可，不暴露真实 key

7. **Intern-S2-Preview 不支持 tool_call 和 vision** — tool_call 返回 500 Internal Server Error；vision 接受请求但返回 "prompt processing error"。此模型还会**泄露 thinking chain**（详见下方），不适合生产使用。

8. **Intern-S2-Preview thinking chain 泄露（详细）** — 每次响应的 `message.content` 开头会先输出完整英文推理过程（以 "Here's a thinking process that leads to..." 开头），然后才是正式中文回答。thinking 占输出 30-50% token，导致 max_tokens=4096 下频繁截断。**未发现可通过请求参数关闭 thinking 的方法**。缓解措施：(a) 将 max_tokens 提高到 8192+；(b) 后处理剥离 thinking 段落。

9. **批量测试 API key 时注意 xlsx 表头行** — 华为 key 分配表 xlsx 中，第一人的数据可能在第 3 行（与表头混排），而非第 4 行开始。遍历时用 `key_val and str(key_val).startswith("sk-")` 过滤，不要假设固定起始行。

10. **旧版 GLM 端点** (hash `71d0b4e30d7a4fc19661f9409721493d`) 不支持 tool call，已废弃。

## 端点详情

### 1. Qwen3.6-35B-A3B
- Base: `http://10.26.15.52:30081/ccb44b4cfe18439f8affd07babd0810e/v1`
- 模型: 阿里通义千问 3.6，35B 参数，A3B 激活
- Context: ~133K (max_model_len=133000)
- Chat ✅ | Tool call ✅ | Stream ✅ | Vision ✅ (base64 测试通过)
- **Thinking 泄露**: 华为部署端的 Qwen3.6 会泄露 thinking chain，`enable_thinking: false` 无效（2026-06-03 实测 4 种方法均无法抑制）。输出以英文 "Here's a thinking process:" 开头，占 30-60% 输出 token。需后处理剥离或联系管理员修复 vLLM chat_template
- **响应速度偏慢**: thinking bloat 导致响应时间显著高于 GLM-5 / DeepSeek-V4

### 2. DeepSeek-V4-Flash-w8a8-mtp
- Base: `http://10.26.15.52:30081/132bc0947fc64cc79e22618a60394789/v1`
- 模型: DeepSeek V4 Flash，w8a8 量化 + MTP
- Context: ~131K (max_model_len=131072)
- Chat ✅ | Tool call ✅ | Stream ✅ | Vision ❌
- **最稳定**：无 thinking 泄露，响应速度快，tool call 可靠

### 3. GLM-5.1-w8a8
- Base: `http://10.26.15.52:30081/7f82733149be43a1b8f26196b2202fa6/v1`
- 模型: 智谱 GLM-5.1，w8a8 量化
- Context: ~133K (max_model_len=133120)
- Chat ✅ | Tool call ✅ | Stream ✅ | Vision ❌
- **Thinking 模型**: reasoning 内容在 `reasoning` 字段中（不影响 `content` 干净度），但需设置足够 max_tokens（≥ 512）否则 content 为空
- **响应速度最快** 之一

### 4. Intern-S2-Preview
- Base: `http://10.26.15.52:30081/784fa5165cd6424fa19764c8c6b95274/v1`
- 模型: Intern-S2 Preview（上海 AI Lab），lmdeploy 引擎
- Context: ~256K (实测 262144 tokens)
- Chat ✅ | Tool call ❌ (500) | Stream ✅ | Vision ❌ (error)
- **Thinking chain 泄露**: 每次响应的 `message.content` 开头先输出完整英文推理（"Here's a thinking process that leads to..."），然后才是正式中文回答。thinking 占 30-50% 输出 token，导致 4096 token 限制下频繁截断。**无法通过请求参数关闭**。建议 max_tokens ≥ 8192，后处理剥离 thinking 段落
- **独立权限控制**: 部分 API key 对此端点返回 401
- **平均响应时间**: ~79s（偏慢，含 thinking 额外开销）
- 不适合需要 tool use、vision、或干净输出（无 thinking）的场景

## 详细参考

Intern-S2-Preview 实测详情见 `references/intern-s2-test-2026-06-02.md`。

5 模型 SEI 膜科学问题评估（2026-06-03）见 `references/sei-model-evaluation-2026-06-03.md`。关键发现：Qwen3.6 的 `enable_thinking: false` 在华为端点完全无效（4 种方法均无法抑制 thinking 泄露）；GLM-5 和 DeepSeek-V4 是唯二无 thinking 泄露的模型。

API key 批量测试结果（2026-06-02，19 key）见 `references/api-key-batch-test-2026-06-02.md`。关键发现：Intern-S2 有独立 key 级权限控制（仅 3/19 key 可访问）。

## 文件位置

| 文件 | 用途 |
|------|------|
| `scripts/test_all_endpoints.py` | 全端点批量测试脚本 |
| `scripts/test_key_per_endpoint.py` | API key 逐端点验证脚本 |
| `scripts/batch_test_keys.py` | API key 批量测试脚本（从 xlsx 读取所有 key，逐一测试，结果写回新列） |
| `references/intern-s2-test-2026-06-02.md` | Intern-S2 实测详情 |
| `references/sei-model-evaluation-2026-06-03.md` | SEI 膜科学问题评估 |
| `references/api-key-batch-test-2026-06-02.md` | API key 批量测试结果 |
| `templates/endpoints-reference.html` | 暗色主题端点参考页（能力矩阵 + 坑点） |
