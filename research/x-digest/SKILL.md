---
name: x-digest
description: Daily digest of X.com (Twitter) following feed, filtered to AI / LLM / agent topics. Captures the feed with a dedicated Playwright Chromium persistent profile (no extensions, login persists), writes a Chinese digest, maintains a dedup store, and emails it to zleung9@outlook.com. Run headless via `pi -p "/skill:x-digest"`.
---

# X AI · LLM · Agent 日报

You are running an **automated, headless** daily digest. Do **not** ask the user
any questions — make reasonable decisions and proceed to completion. Output a
concise one-line summary at the very end.

All paths below are relative to the skill directory. **First, always run:**

```bash
cd /Users/zliang/.pi/agent/skills/x-digest
DATE=$(date +%F)
```

(The real directory is `~/Nutstore Files/skills/research/x-digest`; the
`.pi/agent/skills/...` path is a symlink to it.)

## Browser: Playwright Chromium (NOT the user's Chrome)

The pipeline uses Playwright's own Chromium with a **dedicated persistent
profile** at `browser-profile/`:

- **No user extensions are ever loaded** → the X.com "Something went wrong …
  privacy related extensions" error cannot happen. (This was the old failure
  mode when we drove the user's Chrome/CDP profile, where the Zotero
  Connector content script broke X's SPA bootstrap.)
- **Login cookies persist to disk** in `browser-profile/` → log in once, no
  re-login on later runs (until X expires the session).
- No `:9222` CDP port, no dependency on the user's running Chrome.
- Network egress uses the macOS system proxy (Clash at 127.0.0.1:7890)
  automatically — X.com is reachable from China.

Setup (already done — only if `node_modules` is missing):
`npm install` in the skill dir (pins playwright 1.62.x, which matches the
installed Chromium in `~/Library/Caches/ms-playwright/chromium-1234`).

## Pipeline

### 1. Check login state

```bash
node scripts/x-status.mjs
```

- `loggedIn: true` → continue.
- `loggedIn: false` → run `node scripts/x-login.mjs --timeout-minutes 15`.
  This opens a **visible Chromium window** at x.com/login; the user signs in
  (Google/Apple/email). The script polls every 5s and exits 0 on
  `LOGGED_IN`, 1 on `LOGIN_TIMEOUT`. If you're running unattended, tell the
  user to look at the window. Never proceed to step 2 without `loggedIn`.

### 2. Capture the following feed (deterministic)

```bash
node scripts/fetch_feed.mjs --scrolls 16 --wait 2200 --out data/feed_$DATE.json --merge
```

Opens x.com/home in the persistent profile, switches to the **Following**
tab, scrolls (X virtualizes the DOM, so the script extracts incrementally
while scrolling), and saves
`{fetchedAt, count, tweets:[{id,handle,name,text,time,link,rt}]}`.
Exit code 2 = not logged in → go back to step 1.
Read stderr for progress. Keep scrolling (bump `--scrolls`) until the feed
reaches ~24h back, or until it stops yielding new tweets.

### 3. Select the day's window

Keep tweets with `time >= fetchedAt - 24h`. List them newest-first
(handle + first 150 chars) and review them.

### 4. Relevance filter (use your judgment)

Keep ONLY tweets clearly about **AI / LLM / agents**:

- LLMs, model releases/benchmarks, quantization, local inference
- agents, agentic tools/frameworks, coding agents, agent ops/cost
- AI research (papers, RL/alignment/safety, world models, AI for science)
- notable AI industry news/opinion (labs, products like Grok/Codex/Claude)

**Skip**: crypto/finance, sports, politics, personal life, food/travel,
generic tech not about AI, vague one-liners without context.
Retweets of relevant content count (mark `RT`, keep original author in link).
When uncertain and clearly AI-adjacent, **keep it**.

### 5. Write the digest (Chinese, Markdown)

Write to `data/digests/$DATE.md`:

```markdown
# X AI · LLM · Agent 日报
**日期**: <DATE>（<weekday>）
**范围**: Following 时间线，最近 24 小时（<start> → <end> 北京时间）
**抓取**: <M> 条推文，其中 AI/LLM/Agent 相关 **<N> 条**

---

## 今日要点
- (5–6 条最重要的 bullet)

---

## 一、Agent 框架与工具   (group as appropriate)
### 1. <一句话标题>
- **作者**: @handle
- **时间**: MM-DD HH:MM (北京时间)   (convert UTC +8h)
- **链接**: https://x.com/...
- **内容**: 1–3 句中文摘要，关键引文可加引号。

(repeat for each relevant tweet; group into themed sections:
 Agent 框架与工具 / 模型发布与横评 / 行业动态与观点 / 实操观察 —
 drop a section if empty; merge multi-tweet threads into one item)
```

Times: tweet `time` is UTC — convert to 北京时间 (UTC+8).

### 6. Update the dedup store (do this every run)

`data/seen.json`: `{ lastRun, tweets: { "<id>": {firstSeen, handle, time, snippet, relevant} } }`.
Add every tweet id from `data/feed_$DATE.json` (relevant or not). On later
runs you may skip already-seen ids in the digest, but keep listing them in
the store. Set `lastRun = $DATE`.

### 7. Email the digest

Recipient fixed: `zleung9@outlook.com`. Sent via msmtp (account `163`,
sender `zleung9@163.com`, config `~/.config/msmtp/config`) using
`scripts/send_email.mjs` (markdown→HTML, falls back to Resend, else dry-run).

- If **no relevant tweets** today: do **not** email. Print
  `No relevant tweets today; email skipped.`
- Otherwise:

```bash
node scripts/send_email.mjs --subject "X AI · LLM · Agent 日报 — $DATE" --html-file data/digests/$DATE.md --to zleung9@outlook.com
```

Treat a successful msmtp send (exit 0) as success. Never block on email config.

### 8. Final summary line

Print exactly one line:

```
Done: <N> relevant items, <M> tweets in 24h (<K> captured), <K2> in store. Digest: data/digests/<DATE>.md [email sent|email dry-run|email skipped]
```

## Scripts

| Script | Purpose |
|---|---|
| `scripts/pw-common.mjs` | shared Playwright helpers (persistent profile `browser-profile/`, login check) |
| `scripts/x-status.mjs` | print `{loggedIn, hasAuthToken, cookieCount}` JSON |
| `scripts/x-login.mjs` | open visible login window, poll until auth_token appears |
| `scripts/fetch_feed.mjs` | scroll-capture the Following feed → JSON |
| `scripts/send_email.mjs` | markdown digest → HTML email via msmtp |

## Notes

- Only **one** process may hold `browser-profile/` at a time (SingletonLock) —
  run the scripts sequentially (the pipeline already does).
- `browser-profile/` may grow; deleting it only forces a re-login, nothing
  else is stored there.
- If X expires the session (x-status says not logged in mid-pipeline), run
  `x-login.mjs` and retry — do not skip the day silently.
- If Chromium fails to launch (missing browser binary): `npx playwright install chromium`.
- Never block on missing email config — dry-run is success.
