---
name: nature-digest
description: Daily automated digest of Nature papers about AI agents / LLM agents and AI for Science. Fetches Nature RSS feeds, filters new relevant papers, writes Chinese summaries, maintains a dedup store, and emails a daily digest. Run headless via `pi -p "/skill:nature-digest"`.
---

# Nature 智能体 & AI for Science 日报

You are running an **automated, headless** daily digest. Do **not** ask the user
any questions — make reasonable decisions and proceed to completion. Output a
concise one-line summary at the very end.

All paths below are relative to the skill directory. **First, always run:**

```bash
cd /Users/zliang/.pi/agent/skills/nature-digest
```

(The real directory is `~/Nutstore Files/skills/research/nature-digest`; the
`.pi/agent/skills/...` path is a symlink to it.)

Today's date:

```bash
DATE=$(date +%F)   # e.g. 2026-08-26
```

## Pipeline

### 1. Fetch new candidate papers (deterministic)

```bash
node scripts/fetch_papers.mjs --out data/new_candidates.json
```

This fetches all feeds in `config/feeds.json`, parses them, dedups by DOI across
feeds, drops DOIs already recorded in `data/seen.json`, and writes the remaining
**new** candidates to `data/new_candidates.json`. Read its stderr to get counts.
If it reports `new candidates=0`, skip to step 6 (no new papers today).

### 2. Read the new candidates

Use `read` on `data/new_candidates.json`. Each record is:

```json
{ "doi": "10.1038/...", "title": "...", "link": "https://www.nature.com/articles/...",
  "authors": "A, B, et al.", "journal": "Nature Machine Intelligence",
  "date": "2026-08-26", "type": "research", "abstract": "..." }
```

### 3. Relevance filter (use your judgment)

Keep ONLY papers clearly matching **either** theme:

- **(A) AI 智能体 / agents** — LLM agents, autonomous agents, multi-agent
  systems, agentic AI, tool use, agent benchmarks, agent frameworks, etc.
- **(B) AI for Science** — using ML/AI to advance scientific discovery
  (biology, chemistry, physics, materials, drug discovery, genomics, climate,
  math/theorem proving, scientific simulation, etc.).

**Skip** (even if vaguely AI-adjacent): news (`type == "news"`), editorials,
correspondence, comments, perspectives that are not research, author profiles,
obituaries, podcasts, career articles, and research clearly unrelated to both
themes. When uncertain about a borderline paper, **keep it** (better to include
than miss).

### 4. Write a Chinese summary for each relevant paper

For each kept paper, write a **2–4 句中文摘要** based on `abstract`, covering:
论文做了什么 + 方法/关键点 + 为什么重要。Keep it factual and concise.

### 5. Build the digest (Markdown)

Write to `data/digests/$DATE.md` with this structure:

```markdown
# Nature 智能体 & AI for Science 日报
**日期**: 2026-08-26
**新增相关论文**: 5 篇
**数据源**: (list the `name` values from config/feeds.json — currently: nature, natmachintell, ncomms, nmeth)

---

### 1. <原英文标题>
- **期刊**: Nature Machine Intelligence
- **作者**: Felix Radford, Nayan Sapers, et al.
- **类型**: research
- **链接**: https://www.nature.com/articles/s42256-026-01296-8
- **DOI**: 10.1038/s42256-026-01296-8
- **中文摘要**: 本文提出了一种……方法，能够……。该工作的重要性在于……。

### 2. <原英文标题>
...
```

If zero relevant papers, still write the file with body `**今日无新增相关论文。**`

### 6. Update the dedup store (important — do this every run)

Read `data/seen.json` (`{ lastRun, dois: { "10.1038/...": { firstSeen, title, relevant } } }`).
Add **every** DOI from `data/new_candidates.json` (relevant or not — so irrelevant
ones are never re-evaluated), with `firstSeen = $DATE`, the paper's `title`, and
`relevant = true|false`. Set `lastRun = $DATE`. Write `data/seen.json` back.

> Rationale: recording all seen DOIs (not just relevant ones) means only truly
> new papers get processed next time. This is the "已经搜寻到的论文就不再去整理" rule.

### 7. Email the digest

Recipient is fixed: `zleung9@outlook.com`. Sending uses the **local email
skill** (msmtp, account `163`, sender `zleung9@163.com`) — already configured
at `~/.config/msmtp/config`. The script `send_email.mjs` auto-detects msmtp and
converts the Markdown digest to HTML.

- If **no relevant papers** today: do **not** email. Print
  `No new relevant papers; email skipped.`
- If relevant papers exist:
  ```bash
  node scripts/send_email.mjs --subject "Nature 智能体 & AI for Science 日报 — $DATE" --html-file data/digests/$DATE.md --to zleung9@outlook.com
  ```
  The script sends via msmtp (`-a 163`) if available; falls back to Resend if
  `RESEND_API_KEY` is set; otherwise it **dry-runs** (prints body, exits 0).
  Treat a successful msmtp send (exit 0) as success. Never block on email config.

### 8. Final summary line

Print exactly one line:

```
Done: <N> new relevant, <M> total new candidates, <K> DOIs in store. Digest: data/digests/<DATE>.md [email sent|email dry-run|email skipped]
```

## Notes

- Never block on missing email config — dry-run is success.
- Email is sent via the **local email skill** (msmtp, account `163`). See
  `/Users/zliang/.pi/agent/skills/email/SKILL.md` for details. Recipient:
  `zleung9@outlook.com`.
- Scheduled daily by the 03:00 cron dispatcher (`~/.local/cron/run-0300.sh`):
  `run_job nature-digest pi -p "/skill:nature-digest"`.
- Summaries are always in **中文**; keep paper titles in the original English.
- If a feed fails, `fetch_papers.mjs` still produces candidates from the others.
- To add more journals later, edit `config/feeds.json` (e.g. Nature Computational
  Science: `https://www.nature.com/natcompintell.rss`).
