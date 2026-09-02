# nature-digest

A pi-agent skill that produces a **daily digest** of Nature papers about
**AI 智能体 / LLM agents** and **AI for Science**, with Chinese summaries,
emailed to you each morning. Already-seen papers are never re-sent.

## How it works

```
cron 03:00 dispatcher (~/.local/cron/run-0300.sh)
   └▶ pi -p "/skill:nature-digest"
                          │
                          ├─ scripts/fetch_papers.mjs   (抓 RSS + DOI 去重 + 比对 seen.json)
                          ├─ SKILL.md                   (LLM 筛相关 + 写中文摘要 + 生成 digest)
                          ├─ data/seen.json             (去重仓库)
                          ├─ data/digests/YYYY-MM-DD.md (当日归档)
                          └─ scripts/send_email.mjs     (msmtp 163 / Resend / dry-run)
```

- **Deterministic parts** (fetch, dedup, email) live in `scripts/`.
- **Fuzzy parts** (relevance filtering, Chinese summaries) are done by the LLM
  following `SKILL.md`.
- Dedup key = **DOI**. Every processed DOI is recorded in `data/seen.json`, so
  only genuinely new papers are handled each run.

## Setup

### 1. Email backend (pick one; all optional — dry-run works without any)

**Resend** (easiest, free tier):
```bash
export RESEND_API_KEY="re_..."
export DIGEST_EMAIL_TO="you@example.com"
# optional:
export DIGEST_EMAIL_FROM="Nature Digest <you@yourdomain.com>"
```

**Shell command** (msmtp / sendmail / mail):
```bash
export MAIL_CMD="msmtp"          # or "sendmail -t"
export DIGEST_EMAIL_TO="you@example.com"
```

With **no backend** configured, `send_email.mjs` prints the digest to stdout
(dry-run) — useful for testing the pipeline end-to-end before wiring email.

### 2. Make sure pi is authenticated

```bash
pi -p "say ok"   # should respond; if not, run: pi /login
```

### 3. Test one run manually

The skill is global, so `/skill:nature-digest` works from any directory:

```bash
pi -p "/skill:nature-digest"
# then inspect:
cat data/digests/$(date +%F).md
cat data/seen.json | python3 -m json.tool | head
```

### 4. Schedule with cron (daily 03:00, via the shared dispatcher)

The crontab only knows about the dispatcher:
`0 3 * * * /bin/sh ~/.local/cron/run-0300.sh`. The nature-digest job lives
inside that script — just run pi, no wrapper needed:

```sh
run_job nature-digest pi -p "/skill:nature-digest"
```

Logs land in `~/.local/cron/logs/nature-digest-YYYY-MM-DD.log`.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | Orchestration instructions the LLM follows |
| `config/feeds.json` | Nature RSS feeds to scan (add journals here) |
| `scripts/fetch_papers.mjs` | Fetch + parse + dedup → `data/new_candidates.json` |
| `scripts/send_email.mjs` | Email backend (msmtp 163 / Resend / dry-run) |
| `data/seen.json` | Dedup store of all seen DOIs |
| `data/digests/YYYY-MM-DD.md` | Per-day digest archive |

## Tuning

- **Add journals**: append to `config/feeds.json`. Examples:
  - Nature Computational Science: `https://www.nature.com/natcompintell.rss`
  - Nature Chemistry: `https://www.nature.com/nchem.rss`
  - Nature Methods: `https://www.nature.com/nmeth.rss`
- **First-run backfill**: `fetch_papers.mjs` caps new candidates at 60 per run
  (`--max-new`). On the very first run everything is "new"; the cap keeps the
  payload small. The backlog naturally clears over the next few runs.
- **Relevance criteria / summary style**: edit `SKILL.md` (steps 3–5). No code.
- **Switch model / thinking**: `pi -p --model sonnet:high "/skill:nature-digest"`.

## Upgrading later (optional)

This MVP is a **skill**. When you outgrow it, promote the same logic to a pi
**extension** to gain: a custom `/digest` command, a registered `nature_search`
tool, in-pi scheduling, richer HTML email templates, etc. The scripts and
`SKILL.md` prompts transfer directly — only the thin orchestration layer changes.
