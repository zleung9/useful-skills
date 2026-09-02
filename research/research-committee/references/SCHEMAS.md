---
name: research-committee/schemas
description: 研究委员会 JSON Schema 定义 — 所有 Pack 的数据格式规范
category: research
---

# Research Committee — JSON Schema Contracts

所有 pack 均为**领域无关**的 JSON 格式。JSON key 始终为英文。每个 pack 携带：

- `schema` — pack 名称，格式：`"<PackName>/v1"`
- `idea_id` — slug，与文件夹中的所有文件共享
- `candidate` — `"A"` 或 `"B"`（idea 级别文件省略）
- `revision` — 整数，从 1 开始，每次重跑递增
- `author_agent` — 写入 agent 的 id
- `created_at` — ISO 8601 时间戳

---

## File → Writer 映射

| 文件 | 写入者 |
|------|--------|
| `state.json` | oracle |
| `00_idea_spec.json` | oracle |
| `01_candidate_A.json` | oracle |
| `02_candidate_B.json` | oracle |
| `10_literature_<cand>.json` | literature-scout |
| `11_feasibility_<cand>.json` | feasibility-analyst |
| `12_venue_<cand>.json` | venue-strategist |
| `20_critique_<cand>.json` | red-team-critic |
| `30_merge_<cand>.json` | oracle |
| `40_final_topic.json` | oracle |

---

## state.json

```json
{
  "schema": "IdeaState/v1",
  "idea_id": "string",
  "phase": "DRAFT|TRIAGED|EVALUATING|SYNTHESIZED|CRITIQUED|REVISING|APPROVED|REJECTED",
  "candidates": ["A", "B"],
  "revision_count": 0,
  "max_revisions": 1,
  "user_lang": "zh|en|...",
  "field_context": "string",
  "history": [
    {"ts": "ISO-8601", "phase": "string", "note": "string"}
  ],
  "updated_at": "ISO-8601"
}
```

---

## IdeaSpec (00_idea_spec.json)

```json
{
  "schema": "IdeaSpec/v1",
  "idea_id": "string",
  "revision": 1,
  "author_agent": "oracle",
  "created_at": "ISO-8601",
  "field_context": "一段话命名研究者的学科、子领域和问题风格",
  "researcher_resources": {
    "compute": "string (e.g. '8x A100 80GB', 'MacBook M3', 'no GPU')",
    "data_access": "string (e.g. '已有内部数据集 50k 条', '可爬取公开数据', '无标注数据')",
    "experimental_access": "string (e.g. '可做线上 A/B 测试', '有医院合作', '一个人单干')",
    "collaborators": "string (e.g. '无协作者', '有导师指导', '有3人团队')",
    "time_horizon_months": 36
  },
  "core_question": "单句，可测试，非「有人用X做了Y」格式",
  "target_system": "研究的具体系统 / 机制 / 数据集",
  "candidate_mechanisms": ["string — 用户提出的1-2个可能机制"],
  "success_criteria": {
    "minimum": "6个月交付物描述 — 同行能评估什么具体结果？",
    "ambitious": "3年愿景描述 — 如果一切顺利，论文的最终形态"
  },
  "venue_ambition": "top-tier general | top-tier specialised | solid field journal",
  "non_goals": ["string — 明确不做什么"],
  "open_questions_for_committee": ["string — 用户自己不确定的问题"]
}
```

### IdeaSpec 填写指南

| 字段 | 常见错误 | 正确写法 |
|------|---------|---------|
| `core_question` | "AI可以帮助学术写作" | "在大规模学术论文中，引用图的拓扑结构能否预测论文后续影响力？" |
| `target_system` | "学术写作" | "arXiv cs.AI 类目 2020-2024 年的 50k 篇论文的引用网络" |
| `researcher_resources.data_access` | "有数据" | "已有内部日志 10GB，涵盖 5000 用户的行为记录" |
| `six_month_deliverable` | "完成模型搭建" | "在 3 个公开基准上报告具体数字，准确率比基线提升 X%" |

---

## CandidateSpec (01/02_candidate_*.json)

```json
{
  "schema": "CandidateSpec/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "oracle",
  "created_at": "ISO-8601",
  "title": "简短工作标题（10-15词）",
  "one_sentence_test": "In <target>, <contradiction>, and we will show <claim> by <minimum path>",
  "hypothesis": "string — 可证伪的假设陈述",
  "target_system": "string — 与 IdeaSpec.target_system 一致或更窄",
  "claimed_novelty": "什么是新的，为什么重要（1-2句）",
  "proposed_approach": "string — 具体方法，不是「用AI」这种泛指",
  "key_assumptions": [
    "string — 这个方法成立所依赖的关键假设"
  ],
  "kill_conditions": [
    "string — 会否定该候选成立的结果（例如：如果消融实验显示 X 没有贡献）"
  ],
  "distinct_from_other_candidate": "string — 与候选 B 的核心区别（若只有 A/B 一个候选则省略）",
  "why_now": "string — 为什么是现在？什么外部条件使得这个研究时机成熟？",
  "references": [
    {
      "id": "string — 可验证的 ID",
      "type": "head_to_head|near_miss|foundational",
      "relationship": "与本候选的关系"
    }
  ]
}
```

### one_sentence_test 模板

格式：`In <target>, <contradiction>, and we will show <claim> by <minimum path>`

| 填槽 | 例子 |
|------|------|
| `<target>` | "cross-domain sentiment classification" |
| `<contradiction>` | "prior work assumes label consistency across domains, which fails when source labels are noisy" |
| `<claim>` | "we can recover robust sentiment signals by learning domain-invariant embeddings" |
| `<minimum path>` | "a controlled experiment on 6 domain pairs with synthetic label noise" |

---

## LiteraturePack (10_literature_*.json)

literature-scout 写入。

```json
{
  "schema": "LiteraturePack/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "literature-scout",
  "created_at": "ISO-8601",
  "gap_statement": "一段真正的空白，不是泛泛的「研究空白」套话。必须具体到：本候选做了什么，而先前工作没做。",
  "novelty_verdict": {
    "level": "high|medium|low",
    "reason": "为什么 novelty 是这个等级"
  },
  "papers": [
    {
      "id": "string — DOI 或 arXiv ID 或 Semantic Scholar ID（必须可验证）",
      "title": "string",
      "venue": "string",
      "year": number,
      "classification": "head_to_head|near_miss|tool_only|foundational",
      "relevance_summary": "2-3句话说明这篇论文做什么",
      "gap_addressed": "本候选填补了该论文未覆盖的方面（1-2句）"
    }
  ],
  "head_to_head_count": 0,
  "near_miss_count": 0,
  "tool_only_count": 0,
  "foundational_count": 0,
  "search_queries_used": ["string — 实际使用的搜索关键词"]
}
```

### Classification 判断标准

| 类型 | 定义 | 应对策略 |
|------|------|---------|
| `head_to_head` | 正面竞争——与你回答同一个问题 | 必须找到差异化角度，否则 kill |
| `near_miss` | 差一点——做了A但没做B | 找到那个 B，明确声称可以补全 |
| `tool_only` | 用了你的技术，但问题不同 | 不威胁 novelty，但要引用 |
| `foundational` | 基础工作，必须引用 | 引用但不承认是你的竞争对手 |

---

## FeasibilityPack (11_feasibility_*.json)

feasibility-analyst 写入。

```json
{
  "schema": "FeasibilityPack/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "feasibility-analyst",
  "created_at": "ISO-8601",
  "critical_path": [
    {
      "step": "string — 具体步骤名称",
      "duration_weeks": number,
      "dependencies": ["其他步骤名称"],
      "can_fail": boolean,
      "failure_mode": "如果失败，是什么出了问题",
      "failure_mitigation": "如何降低失败风险"
    }
  ],
  "six_month_deliverable": "具体描述：6个月时同行能评估什么结果",
  "feasibility_score": "0.0-1.0（0.4 以下 = 高风险）",
  "feasibility_reason": "评分理由",
  "bottlenecks": [
    {
      "type": "compute|data|expertise|access|time",
      "severity": "critical|major|minor",
      "description": "具体瓶颈描述",
      "mitigation": "缓解方案或 null（如果无法缓解）"
    }
  ],
  "red_flags": ["string — 严重警告项"],
  "total_weeks": "number — 关键路径总周数",
  "within_6_months": "boolean — total_weeks <= 26"
}
```

### feasibility_score 参考标准

| 分数 | 含义 | 行动 |
|------|------|------|
| 0.8-1.0 | 非常可行 | pass |
| 0.6-0.8 | 可行，有小风险 | pass（带 major concerns）|
| 0.4-0.6 | 可行，但有重大风险 | revise |
| < 0.4 | 高风险，6个月内无法交付 | kill |

---

## VenuePack (12_venue_*.json)

venue-strategist 写入。

```json
{
  "schema": "VenuePack/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "venue-strategist",
  "created_at": "ISO-8601",
  "narrative_spine": {
    "problem": "string — 清晰的问题陈述，不是「X很重要」",
    "mechanism_claim": "string — 核心机制主张",
    "decisive_evidence": "string — 决定性证据是什么",
    "implication": "string — 超越单一系统的启示"
  },
  "minimum_publishable_unit": {
    "description": "最小完整论文的描述",
    "key_claim": "一句话核心主张",
    "what_reviewers_will_criticize": [
      "具体批评1",
      "具体批评2"
    ]
  },
  "safe_route": {
    "target": "string — 期刊/会议类型（不指具体期刊名）",
    "narrative_requirements": [
      "在这个级别发表需要的叙事元素"
    ],
    "missing_evidence": [
      "目前还缺的证据"
    ]
  },
  "ambitious_route": {
    "target": "string — 顶刊/顶会类型",
    "gap_to_ambitious": [
      "从当前证据到顶刊级别还缺什么"
    ]
  },
  "evidence_gaps": [
    {
      "gap": "string — 具体证据缺口",
      "severity": "critical|major|minor",
      "fixable_in_6_months": "boolean"
    }
  ],
  "narrative_risks": [
    "string — 即使有证据审稿人也会发现的叙事漏洞"
  ]
}
```

---

## CritiquePack (20_critique_*.json)

red-team-critic 写入。

```json
{
  "schema": "CritiquePack/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "red-team-critic",
  "created_at": "ISO-8601",
  "verdict": "kill|revise|pass",
  "kill_reason_if_kill": "string or null",
  "alternative_direction_hint": "string or null — if kill, suggest a concrete neighbour direction",
  "confidence": "high|medium|low — 红队对本次判决的置信度",
  "fatal_flaws": [
    {
      "id": "F1",
      "type": "scientific_rigor|novelty|mechanism|feasibility|narrative|venue",
      "statement": "具体致命缺陷描述",
      "evidence": "来自哪个 pack 和字段",
      "fix_direction": "如何修复（如果可以）"
    }
  ],
  "major_concerns": [
    {
      "id": "M1",
      "type": "string",
      "statement": "描述",
      "severity": "major",
      "fix_direction": "修复方向"
    }
  ],
  "minor_concerns": [
    {
      "id": "m1",
      "statement": "描述"
    }
  ],
  "repair_tickets": [
    {
      "agent": "literature-scout|feasibility-analyst|venue-strategist|oracle",
      "instruction": "具体的修复指令",
      "target_file": "需要重写的 pack 文件"
    }
  ]
}
```

### verdict 判断规则

| verdict | 条件 |
|---------|------|
| **kill** | novelty=low OR feasibility<0.4 OR fatal_flaws>0 OR 无 six_month_deliverable |
| **revise** | 无 fatal，但 major_concerns 有 repair_tickets，且 novelty+feasibility 均达标 |
| **pass** | 无 fatal，major concerns 全部有 repair_tickets，feasibility≥0.6，novelty≠low |

---

## MergePack (30_merge_*.json)

Oracle 合并后写入。

```json
{
  "schema": "MergePack/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "oracle",
  "created_at": "ISO-8601",
  "integrated_pitch": "string — 2-3句话综合三个 pack 的核心论点",
  "strongest_points": [
    {
      "source": "literature|feasibility|venue",
      "point": "具体最强点"
    }
  ],
  "weakest_points": [
    {
      "source": "literature|feasibility|venue",
      "point": "具体最弱点"
    }
  ],
  "oracle_prior": {
    "novelty": "high|medium|low",
    "feasibility": "high|medium|low",
    "publishability": "high|medium|low",
    "reason": "string — Oracle 的独立先验判断"
  },
  "consensus_analysis": {
    "agreed": ["三个 committee 成员一致同意的点"],
    "disagreed": [
      {
        "aspect": "分歧点",
        "literature_view": "literature-scout 的观点",
        "feasibility_view": "feasibility-analyst 的观点",
        "venue_view": "venue-strategist 的观点"
      }
    ]
  }
}
```

---

## FinalTopicSpec (40_final_topic.json)

Oracle 仅在 APPROVED 后写入。

```json
{
  "schema": "FinalTopicSpec/v1",
  "idea_id": "string",
  "candidate": "A|B",
  "revision": 1,
  "author_agent": "oracle",
  "created_at": "ISO-8601",
  "approved_at": "ISO-8601",
  "title": "string — 工作标题",
  "one_sentence_test": "In <target>, <contradiction>, and we will show <claim> by <minimum path>",
  "why_now": "string — 为什么是现在？3句话",
  "six_month_plan": [
    {
      "phase": "Month 1-2",
      "goals": ["具体目标"],
      "deliverable": "具体可交付物"
    },
    {
      "phase": "Month 3-4",
      "goals": ["具体目标"],
      "deliverable": "具体可交付物"
    },
    {
      "phase": "Month 5-6",
      "goals": ["具体目标"],
      "deliverable": "具体可交付物"
    }
  ],
  "three_year_vision": "string — 如果一切顺利，3年后的论文最终形态",
  "evidence_ladder": [
    {
      "level": 1,
      "label": "最强证据",
      "description": "最容易获得、审稿人不会质疑的基础证据",
      "examples": ["具体数据/实验类型"]
    },
    {
      "level": 2,
      "label": "次强证据",
      "description": "需要努力但可行",
      "examples": ["具体数据/实验类型"]
    },
    {
      "level": 3,
      "label": "最强野心",
      "description": "顶刊所需，但如果失败论文仍然可发表",
      "examples": ["具体数据/实验类型"]
    }
  ],
  "risks_and_mitigations": [
    {
      "risk": "string",
      "likelihood": "high|medium|low",
      "impact": "high|medium|low",
      "mitigation": "string or null"
    }
  ],
  "open_questions_carried_forward": [
    "这些问题在论文投稿前必须回答，但不是6个月内的交付物"
  ],
  "venue_targets": {
    "minimum": "solid field journal 级别的描述",
    "stretch": "top-tier specialised 级别的描述",
    "dream": "top-tier general 级别的描述"
  }
}
```

### evidence_ladder 填写原则

- **Level 1（必须做到）**：没有这个论文不能发表。审稿人不会质疑的基线。
- **Level 2（应该做到）**：增加论文厚度的实验，有了 Level 1 之后力所能及的。
- **Level 3（顶刊野心）**：如果成功论文可以冲击顶刊，但失败也不致命。

---

## Phase Transition Rules

```
DRAFT
  └─→ TRIAGED: IdeaSpec + both CandidateSpecs written
          └─→ EVALUATING: literature + feasibility invoked in parallel
                  └─→ SYNTHESIZED: MergePack written for all candidates
                          └─→ CRITIQUED: venue + red-team-critic complete
                                  ├─→ REVISING: if verdict=revise (max 1 cycle)
                                  ├─→ APPROVED: if verdict=pass
                                  └─→ REJECTED: if all candidates killed
                                          └─→ new candidate from alternative_direction_hint
```

---

*Last updated: 2026-04-18*
