---
name: proxy-network-access
description: Terminal network access via with_proxy() function — accessing crossref, nobelprize, arxiv etc. from Mac terminal with ClashX proxy
---

# Proxy Network Access in Terminal

## Problem
Terminal commands (curl, wget, etc.) fail to access certain sites (Google, arXiv, NobelPrize, etc.) due to network restrictions. The browser tools work because they use Browserbase cloud proxy.

## Solution
The user's ~/.bashrc defines a `with_proxy()` function that sets proxy environment variables for specific commands. Use it like this:

```bash
source ~/.bashrc && with_proxy curl -sL --max-time 15 "https://example.com" | python3 -c "..."
```

## What to proxy and what not to

| Site | Needs proxy | Notes |
|------|-----------|-------|
| Nobel Prize (nobelprize.org) | YES | Works with proxy |
| Wikipedia | YES | Works with proxy |
| arXiv | YES | Times out without proxy |
| Crossref API | YES | Works with proxy |
| Nature.com | YES | Returns minimal content |
| Science.org | YES | Blocked by Cloudflare (even with proxy) |
| Google Scholar | YES | Anti-scraping |
| Semantic Scholar API | YES | Rate limited (429 without API key) |
| Bing | NO | Browser tools already work |
| HuggingFace | YES | `https_proxy=http://127.0.0.1:7890 hf download ...` or `--proxy` flag |
| Figshare API | NO | 403 even with proxy — network-layer block, requires manual browser download |
| polydatabase.com | YES | Django-based polymer MD database, works with `curl --proxy` |
| data.matr.io | YES | HTP-MD portal, works with proxy; data requires AWS Cognito auth |
| materials.colabfit.org | YES | ColabFit Exchange / OPoly26, works with proxy |
| nanomine.org / materialsmine.org | PARTIAL | REST/GraphQL/SPARQL all return "Contact Administrator" — data requires registration + admin |
| polyid.nrel.gov | NO | Site unreachable; use GitHub repo `NatLabRockies/polyID` instead |

## Scientific dataset sites — access patterns
Many scientific databases have web portals but restricted API access. Common patterns:
1. **Check GitHub first** — many projects publish data on GitHub (e.g., PolyID at `NatLabRockies/polyID`).
2. **HuggingFace mirrors** — some datasets are on HF (e.g., PolyOmics at `yhayashi1986/PolyOmics`, OPoly26 at `colabfit/OPoly26-train`).
3. **Django sites** (like polydatabase.com) — server-rendered HTML, scrape via `curl` + pagination or browser automation. REST endpoints often at `/<model>/` and `/<model>/<pk>/`.
4. **Auth-gated sites** (HTP-MD, NanoMine) — save metadata/README and note registration requirements for the user.
5. **Figshare** — API returns 403 from China even with proxy; must use browser manually.

## References
- `references/scientific-dataset-access.md` — Detailed site-by-site guide for 19 polymer/scientific databases: access methods, auth requirements, data formats, workarounds, and general harvesting workflow.

## Key pattern
```bash
source ~/.bashrc && with_proxy curl -sL --max-time 15 "URL" | python3 -c "
import sys,json
data=json.load(sys.stdin)
# process...
"
```

## Crossref API tips
- Use `rows=N` not `limit=N` for pagination
- container-title can be a string or list — always check with `type()` before calling `.get()`
- Filter by journal: `filter=type:journal-article,container-title:Nature`

## Anti-patterns
- Do NOT add global proxy to ~/.bashrc (user explicitly rejected this)
- Do NOT use `web_search` tool — it doesn't exist
- Do NOT pipe directly to `python3` without the inline script approach shown above
