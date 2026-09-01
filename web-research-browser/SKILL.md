---
name: web-research-browser
description: Web research using browser_navigate + browser_snapshot when no web_search tool is available. Tested approach discovered through trial and error.
---

# Web Research with Browser Tools

## When to Use

Use this skill when you need to search the web or access online information and `web_search` is not available. This skill covers how to use `browser_navigate` + `browser_snapshot` as a working web research pipeline.

## Prerequisites

- `browser_navigate`, `browser_snapshot`, `browser_vision` tools available

## Core Workflow

### 1. Direct Navigation (Best for Known Sources)

Go straight to authoritative source sites — faster and more reliable than search engines:

```
browser_navigate(url="https://www.nobelprize.org/prizes/chemistry/2024/summary/")
browser_snapshot(full=True)  # Get full page text
```

**Best direct-access targets:**
- `nobelprize.org` — Nobel Prize official information
- `nature.com`, `science.org`, `arxiv.org` — academic papers
- Official organization websites for factual data

### 2. Search Engine (When You Don't Know the URL)

Use Bing with careful query construction:

```
browser_navigate(url="https://www.bing.com/search?q=your+search+terms+site:nobelprize.org")
browser_snapshot(full=True)
```

**Caveats:**
- Bing Chinese (`cn.bing.com`) often returns low-quality or site-matched results
- Try international Bing: `www.bing.com/search`
- Google (`google.com`) frequently triggers CAPTCHA/robot detection
- Bing Academic (`academic.bing.com`) useful for scholarly content

### 3. Using Vision for Visual Pages

When `browser_snapshot` returns sparse text (dynamic pages, JS-heavy):

```
browser_vision(question="What is the main content and key information on this page?")
```

### 4. Extracting Specific Content

After getting a snapshot, navigate to sub-pages using `browser_click`:

```
browser_click(ref="e25")  # Click a link in the page
browser_snapshot()        # Get the new page
```

## Known Limitations Found Through Trial

| Approach | Result | Lesson |
|----------|--------|--------|
| `curl` via terminal to Google | Timeout | Network-level blocking |
| `web_search` tool | Not available | Doesn't exist in this env |
| Google.com | CAPTCHA block | Bot detection |
| Bing Chinese | Low-quality results | Search pollution |
| Dynamic pages (no JS render) | Empty snapshot | Use `browser_vision` instead |

## Troubleshooting

- **Empty snapshot**: Page is JS-rendered — use `browser_vision`
- **CAPTCHA block**: Try Bing instead, or direct navigation
- **Slow load**: Use `browser_snapshot()` right after `browser_navigate` (no separate wait needed)
- **Results truncated**: Use `browser_snapshot(full=True)` for complete content

## Scraping Django / Server-Rendered Sites

For sites like polydatabase.com that use Django with server-rendered HTML (no JS API):

1. **Discover pagination**: Navigate to `?search=<broad_term>&page=1`, increment page until empty.
2. **Batch with curl**: Faster than browser for bulk page fetching:
   ```bash
   for p in $(seq 1 10); do
     curl -s "https://SITE/?search=a&page=$p" --proxy "$PROXY" > "page_$p.html"
   done
   ```
3. **Extract detail links**: Parse list pages for detail-page URLs (e.g., DOI links).
4. **Batch fetch details**: Curl each detail page, parse with Python (BeautifulSoup or regex).
5. **Save structured data**: Write JSON + CSV for downstream use.

This is 10–50x faster than clicking through pages with `browser_click`.

## Verification Steps

After getting information, cite the source URL in your response so the user knows where it came from.

## Related Skills

- `academic-literature-search` — for paper discovery specifically
- `arxiv` — for arXiv paper search and retrieval
