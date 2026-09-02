# Intern-S2-Preview 端点测试（2026-06-02）

## 端点信息
- Hash: `784fa5165cd6424fa19764c8c6b95274`
- URL: `http://10.26.15.52:30081/784fa5165cd6424fa19764c8c6b95274/v1`

## 能力矩阵

| 能力 | 结果 | 备注 |
|------|------|------|
| Chat | ✅ | 正常响应，但泄露 thinking chain |
| Tool Call | ❌ | 返回 500 Internal Server Error |
| Streaming | ✅ | SSE 正常 |
| Vision | ❌ | 接受请求但返回 "prompt processing error" |
| Context | ~200K | 用户确认（2026-06-02） |

## Thinking Chain 泄露（详细）

这是该端点最严重的问题。每次请求的响应中，模型会先输出完整的英文推理过程（以 "Here's a thinking process that leads to..." 开头），然后才输出正式回答。

### 泄露模式
- **格式**: 正式回答前会有一大段英文 thinking，描述模型的自我推理、规划、自我纠正过程
- **语言**: 正式回答为中文，但 thinking chain 始终为英文
- **长度**: thinking chain 可占数百到数千字符，严重消耗输出 token 额度
- **位置**: thinking 内容出现在 `message.content` 的开头，不是 `reasoning_content` 字段
- **与 Qwen3.6 的区别**: Qwen3.6 的 thinking 可通过 `enable_thinking: false` 控制，Intern-S2 无法通过请求参数关闭

### 影响
1. **token 浪费**: max_tokens=4096 时，thinking 可能占用 30-50%，实际有效输出被截断
2. **输出截断**: 在 4096 token 限制下，5 个科学问题中有 3 个因长度不足被截断（finish_reason=length）
3. **不适合生产**: 任何需要干净输出的场景都受影响
4. **无法通过请求参数控制**: 不同于 Qwen3.6，未发现可关闭 thinking 的参数

## 科学问题测试（2026-06-02）

使用 5 个跨学科科学问题测试，max_tokens=4096，temperature=0.7。

| # | 领域 | 耗时 | 输出 tokens | finish_reason | 有效输出字符 |
|---|------|------|-------------|---------------|-------------|
| 1 | 物理学（贝尔不等式） | 87s | 4096 | length（截断） | 10646 |
| 2 | 数学（费马大定理） | 86s | 4096 | length（截断） | 13318 |
| 3 | 生物学（CRISPR-Cas9） | 69s | 3412 | stop（完整） | 8783 |
| 4 | 化学（SEI 膜） | 71s | 3552 | stop（完整） | 9702 |
| 5 | 计算机科学（MHA+FlashAttn2） | 82s | 4096 | length（截断） | 11805 |

### 科学准确性评估

- **Q1 贝尔不等式**: ✅ 准确 — 物理含义、CHSH 公式（S ≤ 2 vs 2√2）、2022 诺奖三人贡献、无漏洞实验描述均正确
- **Q2 费马大定理**: ✅ 准确 — Frey 曲线→Ribet 定理→Wiles 证明逻辑链、谷山-志村猜想与模性定理联系、Langlands 纲领意义均正确
- **Q3 CRISPR-Cas9**: ✅ 准确 — gRNA 引导、PAM（5'-NGG-3'）、R-loop 形成、NHEJ vs HDR、脱靶来源与降低策略均专业
- **Q4 SEI 膜**: ✅ 准确 — 双层结构、EC/LiPF6 分解路径、厚度与内阻正相关、FEC/HCE/人工 SEI 策略均正确
- **Q5 Transformer+FA-2**: ✅ 准确 — QKV 变换、缩放点积、多头拼接投影、FA-2 IO 感知分块、内核融合、Tensor Core 优化均正确；正确澄清了 FLOPs 仍为 O(N²) 但 IO 降低

### 性能评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 科学准确性 | ★★★★☆ | 5 题均无事实错误，专业术语准确 |
| 内容深度 | ★★★★☆ | 覆盖所有子要求，有公式和具体数字 |
| Thinking 泄露 | ★☆☆☆☆ | 严重缺陷，每次暴露完整推理，浪费大量 token |
| 输出完整性 | ★★★☆☆ | 3/5 被截断，需提高 max_tokens 或关闭 thinking |
| 响应速度 | ★★★☆☆ | 平均 79s，偏慢（thinking 额外开销） |
| 中文能力 | ★★★★☆ | 正式回答全中文、术语地道，但 thinking 全英文 |

### 建议
- 使用时建议将 max_tokens 提高到 8192+，以补偿 thinking chain 占用的空间
- 后处理需剥离 thinking chain 内容（以 "Here's a thinking process" 开头到第一个正式段落前的部分）
- 如发现可关闭 thinking 的参数，应优先启用

## 不适合的生产场景
- 需要工具调用的 agent workflow（tool call 返回 500）
- 需要视觉理解的任务（vision 返回 error）
- 需要干净输出（无 thinking 泄露）的场景
- 对输出 token 成本敏感的场景（thinking 浪费 30-50%）
