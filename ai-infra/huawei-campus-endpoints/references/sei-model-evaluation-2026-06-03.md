# 华为 5 模型 SEI 膜评估（2026-06-03）

同一科学问题（锂离子电池 SEI 膜的组成、形成机理及对电池性能的影响），5 个模型逐个测试，统一评分标准。

## 评分标准（6 维度 × 10 分 = 满分 60）

| 维度 | 说明 |
|------|------|
| 准确性 | 事实正确性，无错误 |
| 完整性 | 覆盖主要知识点 |
| 深度 | 机理层面的解释 |
| 结构 | 逻辑组织、层次清晰 |
| 可读性 | 语言流畅、专业术语得当 |
| 效率 | 有用信息密度，thinking 泄露扣分 |

## 结果

| 排名 | 模型 | 得分 | 响应时间 | 备注 |
|------|------|------|----------|------|
| 1 | GLM-5 | 43/60 | 67s | 无 thinking 泄露，结构清晰，深度好 |
| 2 | DeepSeek-V4 | 41/60 | 65s | 无 thinking 泄露，速度快，深度略浅 |
| 3 | Qwen3.6-std | 39/60 | 258s | thinking 泄露严重，实际回答质量不错但效率极低 |
| 4 | Qwen3.6-128K | 38/60 | 297s | 同上，更慢 |
| 5 | Intern-S2 | 37/60 | 81s | thinking 泄露 + 内容截断，实际能力可能更高但输出质量受损 |

## 关键发现

1. **GLM-5 和 DeepSeek-V4 是唯二无 thinking 泄露的模型**，输出干净，可直接使用
2. **Qwen3.6 两个版本均有严重 thinking 泄露**（与之前认知不同——之前认为 `enable_thinking: false` 可抑制），4 种参数尝试全部无效
3. **Thinking 泄露对评分影响大**：Qwen3.6 实际回答质量与 GLM-5 相近，但 thinking 占 30-60% 输出 token，拉低效率和可读性
4. **Qwen3.6 响应极慢**（4-5 分钟），主因 thinking 生成开销
5. **Intern-S2 不适合需要干净输出的场景**，除非后处理剥离 thinking

## 根因分析：Qwen3.6 thinking 无法关闭

华为端点的 vLLM 部署**未配置正确的 chat_template** 来隔离 `<arg_key>` 标签。Qwen3.6 模型内部生成 thinking 后，vLLM 直接将其塞入 `message.content` 而非路由到 `reasoning_content` 字段。

**尝试过的 4 种方法（全部无效）**：
1. `chat_template_kwargs: {enable_thinking: false}` — 无效
2. `thinking: false`（顶层参数）— 无效
3. `chat_template_kwargs: {thinking: false}` — 无效  
4. System prompt 指令 "不要输出思考过程" — 无效

**根本修复**：需要服务器管理员在 vLLM 启动配置中指定 Qwen3.6 官方 chat-template（支持 thinking/reasoning_content 分离），或在 serving 配置中全局禁用 thinking。

## 评估报告文件

完整评估报告：`~/Documents/huawei-sei-evaluation.md`
