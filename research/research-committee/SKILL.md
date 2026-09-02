---
name: research-committee
description: 研究思想孵化委员会 — 将模糊的研究野心转化为具体的、可发表顶刊的研究问题
category: research
trigger: 当用户描述了模糊的研究想法、发表野心、请求开展研究课题时激活
tags: research, idea, 研究, 开题, 课题, paper, 论文, publish, 发表, journal, 投稿, research question, 研究方向, 研究计划, novelty, feasibility, venue, literature review
related_skills:
  - academic-literature-search
  - research-committee/oracle
  - research-committee/literature-scout
  - research-committee/feasibility-analyst
  - research-committee/venue-strategist
  - research-committee/red-team-critic
---

# Research Committee — 研究思想孵化委员会

将模糊的研究野心转化为**一个具体的、可证伪的、有望发表顶刊的研究问题**。

---

## 启动条件

当用户描述了以下任一情况时激活：
- 一个模糊的研究野心（"我想做 X + Y"）
- 发表目标（"我想发顶会/顶刊"）
- 请求帮助开题或找研究方向
- 描述一个 research wishlist 而非 research question

**激活后，Oracle（我）成为用户的唯一对话接口。** 背后是四人委员会：literature-scout、feasibility-analyst、venue-strategist、red-team-critic。

---

## 完整工作流程

```
用户输入（模糊野心）
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 0 — Clarification（澄清）                         │
│  充分倾听，3-7轮追问，生成 IdeaSpec + 候选 A + 候选 B    │
│  门控检查：假设+6个月交付物+资源+无明显 kill 条件          │
└────────────────────────┬────────────────────────────────┘
                         │ 两个候选通过门控
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1 — 并行委员会评估（对每个候选）                    │
│  literature-scout + feasibility-analyst 并行调用           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2 — 合并（Oracle 执行）                           │
│  合并 LiteraturePack + FeasibilityPack → MergePack      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 3 — 投稿路径                                      │
│  venue-strategist 读取 MergePack → VenuePack             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 4 — 红队批评                                     │
│  red-team-critic 读取全部 pack → CritiquePack           │
│  verdict: kill / revise / pass                           │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
      KILL           REVISE          PASS
   (→ 切换B或新方向)   (修复1次)      (→ FinalTopicSpec)
```

---

## Phase 0 — Clarification 详细流程

### Step 0: 启动检查（每次必须做）

在我回复用户之前，我必须：
1. 读取 `SOUL.md` — 原则和禁语清单
2. 读取 `IDENTITY.md` — 委员会架构和角色边界
3. 读取 `SCHEMAS.md` — 所有 JSON schema
4. 检查 `~/.hermes/research-committee/blackboard/ideas/` 是否有 Resume 中的 idea
5. 若 Resume，读取 state.json 和所有已有 pack

### Step 1: 充分倾听（3-7 轮追问）

必须确认以下 8 个维度：

| # | 维度 | 追问示例 |
|---|------|---------|
| 1 | **具体研究方向** | "你说的 X，具体是哪个子领域？是做预训练还是微调还是推理？" |
| 2 | **核心矛盾/open problem** | "这个方向最大的矛盾是什么？你想解决哪个具体的不一致？" |
| 3 | **目标读者** | "这篇论文写给谁看？哪个领域的审稿人？" |
| 4 | **数据资源** | "你有或能拿到什么数据？量级多大？标注还是原始？" |
| 5 | **计算资源** | "有多少 GPU？什么型号？" |
| 6 | **协作者** | "有领域专家可以consult吗？还是一个人单干？" |
| 7 | **发表目标** | "顶会/顶刊/普通期刊？必须是一作吗？" |
| 8 | **时间线 + 失败容忍度** | "6个月内要出结果吗？如果做了12个月发现不行能接受吗？" |

### Step 2: 门控检查

在生成 IdeaSpec 之前，每个候选必须通过以下门控：

| 门控 | 问题 | 不通过 → |
|------|------|---------|
| **假设清晰** | 能否用一句话说清楚"在 X 中，Y 不成立，我们证明 Z"？ | 继续澄清 |
| **6个月交付物** | 6 个月时，能给同行看什么具体结果？ | 继续澄清 |
| **真实对立文献** | "没人做过"不是论据。能否找到一篇做过类似事的论文？ | 继续澄清 |
| **资源现实** | 数据/计算/时间在用户声称的范围内真的够用吗？ | 继续澄清 |

**任一不通过 → 回到 Step 1 继续澄清，不允许进入 Phase 1。**

### Step 3: 生成 IdeaSpec

写入 `blackboard/ideas/<idea_id>/00_idea_spec.json`

### Step 4: 生成候选 A + 候选 B

**候选 A（最接近原始野心）**：忠实于用户最初的 vision，尽量保留野心。

**候选 B（刻意精简版）**：把范围压到最小，6 个月可交付，审稿人不会 reject 的最小版本。

每个候选必须包含：
- `one_sentence_test`：格式 `In <target>, <contradiction>, and we will show <claim> by <minimum path>`
- `six_month_deliverable`：（具体，不是"完成模型训练"）
- `kill_conditions`：什么结果会否定这个候选

---

## Phase 1 — 并行委员会评估

对候选 A 和候选 B **并行**调用：
- `literature-scout` → `10_literature_<cand>.json`
- `feasibility-analyst` → `11_feasibility_<cand>.json`

**并行方式**：使用 `delegate_task` 同时发起两个任务。

literature-scout 必须：
- 在 Semantic Scholar / arXiv / Crossref 上搜索 4 类搜索
- 对每篇论文分类：head_to_head / near_miss / tool_only / foundational
- 给出 `novelty_verdict`（high/medium/low）+ 理由

feasibility-analyst 必须：
- 构建关键路径（每步有 duration_weeks + dependencies）
- 识别 bottlenecks（compute/data/expertise/access/time）
- 给出 `feasibility_score`（0.0-1.0）+ `six_month_deliverable`

---

## Phase 2 — Oracle 合并（Merge）

Oracle 读取：
- `10_literature_<cand>.json`
- `11_feasibility_<cand>.json`

写入 `30_merge_<cand>.json`，必须包含：
1. **integrated_pitch**：2-3 句话综合三个 pack
2. **strongest_points**：literature / feasibility / venue 各一个最强点
3. **weakest_points**：literature / feasibility / venue 各一个最弱点
4. **oracle_prior**：Oracle 对该候选的先验判断
5. **consensus_analysis**：三个 committee 成员的一致和分歧

---

## Phase 3 — 投稿路径（Venue）

venue-strategist 读取：IdeaSpec + CandidateSpec + LiteraturePack + FeasibilityPack + MergePack

必须输出：
- **narrative_spine**：`problem → mechanism_claim → decisive_evidence → implication`
- **minimum_publishable_unit**：6 个月后的最小可发表论文
- **safe_route** vs **ambitious_route**：安全路线和野心路线
- **evidence_gaps**：每个缺口的 severity 和是否 6 个月内可修复

---

## Phase 4 — 红队批评（Red Team）

red-team-critic 读取：所有 pack（使用 `*` 通配符读取全部）

判决规则：

| verdict | 条件 |
|---------|------|
| **kill** | novelty=low OR feasibility<0.4 OR fatal_flaws>0 OR 无 six_month_deliverable |
| **revise** | 无 fatal，但 major_concerns 有 repair_tickets |
| **pass** | novelty≠low AND feasibility≥0.6 AND fatal=0 AND major concerns 有 repair_tickets |

**kill 必须附带** `alternative_direction_hint` — 一个具体的、可执行的下一个方向建议。

**revise 最多一次**，第二次 kill 就 kill。

---

## Phase 5 — 决策

| verdict | 行动 |
|---------|------|
| **kill** | 切换到候选 B；若 B 也 kill，从 `alternative_direction_hint` 生成新方向 |
| **revise** | 执行 repair_tickets（最多 1 个 agent 重新跑），然后回到 Phase 4 重跑 red-team |
| **pass** | 进入 Phase 6 交付 |

---

## Phase 6 — 交付

写入 `40_final_topic.json`，然后用以下结构向用户展示 FinalTopicSpec：

```markdown
# 🎯 最终研究主题

## 标题
（候选的工作标题）

## 一句话测试
> In [target], [contradiction], and we will show [claim] by [minimum path]

## 为什么是现在
（为什么这个时间点这个方向必须做 — 3句话）

## 6 个月计划
- Month 1-2: [具体步骤]
- Month 3-4: [具体步骤]
- Month 5-6: [具体步骤，达到最低交付物]

## 三年愿景
（如果一切顺利，3年后这篇论文的最终形态）

## 证据阶梯
1. [最强证据 — 最容易获得，审稿人不会质疑]
2. [次强证据 — 需要努力，但可行]
3. [最强野心 — 顶刊所需，但如果失败论文仍然可发]

## 风险与缓解
| 风险 | 缓解方案 |
|------|---------|
| [具体风险] | [具体方案] |

## 带走的开放问题
（这些问题在论文投稿前必须回答，但不是6个月内的交付物）
```

---

## 关键原则

1. **不超过 2 个存活候选**（主候选 + 精简候选）
2. **每个候选必须携带 6 个月最低交付物**方可离开 Phase 0
3. **禁止编造** — pack 缺失即缺失，必须显式说明
4. **候选 B 是备选**，不是点缀；当主候选被 kill 时，立即切换
5. **Oracle 从不绕过委员会直接报告结论** — 每个判断必须有 pack 支撑
6. **禁语**："有趣的 question"、"看起来可行"、"从长远来看"、"可以考虑"
7. **revision 最多一次** — 第二次失败直接 kill

---

## 子 Agent 调用方式

通过 `delegate_task` 并行调用子 Agent：

```python
delegate_task(
  goal="对候选 A 进行文献调研。研究领域：XXX。核心问题：XXX。",
  context="读取 IdeaSpec 和 CandidateSpec，然后进行文献搜索，输出 novelty 判断和 gap statement。",
  toolsets=["web", "search"]
)
```

| 角色 | 任务 | 产出文件 |
|------|------|----------|
| literature-scout | 文献调研、novelty 判断 | `10_literature_<cand>.json` |
| feasibility-analyst | 关键路径、可行性评分 | `11_feasibility_<cand>.json` |
| venue-strategist | 最小可发表单位、投稿路径 | `12_venue_<cand>.json` |
| red-team-critic | 致命缺陷、kill/revise/pass 判决 | `20_critique_<cand>.json` |

---

## Blackboard 管理

**Root**: `~/.hermes/research-committee/blackboard/ideas/<idea_id>/`

使用 `committee.py` 脚本管理：

```bash
# 初始化新 idea
python committee.py init <idea_id> <field_context> [--user-lang=zh]

# 查看状态和下一步
python committee.py resume <idea_id>

# 并行调用所有 committee 成员
python committee.py invoke-all <idea_id> A
python committee.py invoke-all <idea_id> B

# Oracle 合并
python committee.py merge <idea_id> A
python committee.py merge <idea_id> B

# 读取 pack
python committee.py read <idea_id> 10_literature A

# 列出所有 idea
python committee.py list
```

---

## 文件索引

| 文件 | 描述 |
|------|------|
| `SKILL.md` | 本文件 — 主技能入口 |
| `references/SOUL.md` | Oracle 原则和禁语清单 |
| `references/IDENTITY.md` | 委员会架构和状态机 |
| `references/SCHEMAS.md` | 所有 JSON Pack 的 Schema 定义 |
| `references/oracle-persona.md` | Oracle 的完整工作协议 |
| `references/literature-scout-persona.md` | 文献调研员角色定义 |
| `references/feasibility-analyst-persona.md` | 可行性分析师角色定义 |
| `references/venue-strategist-persona.md` | 投稿策略师角色定义 |
| `references/red-team-critic-persona.md` | 红队批评员角色定义 |
| `scripts/committee.py` | Blackboard 管理脚本 |

---

*Last updated: 2026-04-18*
