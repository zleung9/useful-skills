# Phase Reversal Protocol

当用户决定用根本不同的方法论重新做一个项目时，执行干净的阶段回退。

## 触发条件

- 用户在 DRAFT/REVISION 阶段说"我想重新做"、"换个方法重来"、"不用这个路线了"
- 用户提出全新的方法论方向（如 LSTM → 扩散模型）
- 现有阶段产出被判定为 dead end

## 执行步骤

1. **确认方向**：确保新路线与旧路线的区别是实质性的（不只是微调）
2. **记录决策**：在 MEMORY.md 的 Dead ends 下记录旧路线 + 为什么放弃
3. **更新 state.json**：
   - `phase` → `IDEATION`
   - `mode` → `research-committee`
   - `status` → `active`
   - `pause_reason` → null
   - `current_anchor` → 新方向的一句话描述
   - `history` 追加 reversal 条目
4. **归档旧 phase 产出**：在旧 phase 的 tracker.md 顶部加归档标记（如 `> ⚠️ Phase reversal → IDEATION`）
5. **重置 HEARTBEAT.md**：基于新 IDEATION 阶段写 checkpoints
6. **更新 MEMORY.md**：追加 Decisions 条目记录 reversal；Open questions 重置

## 反模式

- 别无声逆转 — 必须向用户确认状态变更
- 别覆盖旧 tracker — 归档标记保留审计追踪
- 别带着旧 phase 的假设进入新 phase

## 示例

本次会话：`single-mol-gen-2026-05` DRAFT → IDEATION（LSTM → 扩散模型）
