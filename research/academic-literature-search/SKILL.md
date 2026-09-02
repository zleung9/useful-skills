---
name: academic-literature-search
description: "Academic literature search tool integrating Semantic Scholar, Crossref, arXiv, and PubMed. Use when: user asks to search for academic papers, research articles, or scientific literature. NOT for: non-academic web searches, full-text PDF downloads requiring subscriptions. Supports natural language queries, Boolean operators (AND/OR/NOT), field filters (title:, author:, year:), citation sorting, and multiple output formats (Markdown, JSON, CSV, BibTeX)."
homepage: https://github.com/jibeilindong/academic-literature-search
metadata:
  {
    "openclaw":
      {
        "emoji": "📚",
        "requires": { "bins": ["python3", "curl"] },
        "install":
          [
            {
              "id": "pip",
              "kind": "pip",
              "formula": "requests aiohttp pandas pyyaml aiofiles",
              "label": "Install Python dependencies",
            },
          ],
      },
  }
---

# Academic Literature Search Skill

Search academic papers across Semantic Scholar, Crossref, arXiv, and PubMed.

## When to Use

✅ **USE this skill when:**

- "Search for papers on [topic]"
- "Find research about [subject]"
- "Look up [author]'s publications"
- "Search PubMed/arXiv for [topic]"
- "Find citations for a paper"
- "Do a literature review on [topic]"

❌ **DON'T use this skill when:**

- Non-academic web searches → use web search
- Full-text PDF download behind paywalls → use gs-fulltext skill
- Historical weather, news, or general knowledge

## Database Coverage

| Database | Records | Best For | Rate Limit |
|---|---|---|---|
| Semantic Scholar | 233M+ | AI, CS, multidisciplinary | 100 req/5min (no key) |
| Crossref | 140M+ | Journal articles, DOI | Unlimited (polite use) |
| arXiv | 2.2M+ | Preprints, CS, physics, math | Unlimited |
| PubMed | 35M+ | Biomedical, life sciences | 10 req/sec |

## Usage

### Basic Search

```bash
python3 ~/.openclaw/workspace/skills/academic-literature-search/agent.py \
  '{"query": "deep learning medical imaging", "databases": ["semantic_scholar"], "max_results": 10}'
```

### Multi-Database Search

```bash
python3 ~/.openclaw/workspace/skills/academic-literature-search/agent.py \
  '{"query": "transformer attention mechanism", "databases": ["semantic_scholar", "crossref", "arxiv"], "max_results": 20, "sort_by": "citations"}'
```

### Filtered Search

```bash
python3 ~/.openclaw/workspace/skills/academic-literature-search/agent.py \
  '{"query": "CRISPR gene editing", "databases": ["pubmed"], "year_range": "2020-2024", "min_citations": 50, "open_access_only": true}'
```

## Query Syntax

- **Natural language**: `"deep learning in medical imaging"`
- **Boolean**: `"attention AND transformer"`
- **Field filters**: `title:transformer author:"Andrew Ng" year:2023`
- **Range**: `year:2020-2024 citations:>100`

## Output Formats

`output_format`: `markdown` (default) | `json` | `csv` | `bibtex` | `ris` | `html`

## API Keys (Optional)

Without API keys, rate limits apply. Get free keys:
- **Semantic Scholar**: https://www.semanticscholar.org/product/api
- **PubMed**: https://www.ncbi.nlm.nih.gov/account/

Set environment variables:
```bash
export SEMANTIC_SCHOLAR_API_KEY="your_key"
export CROSSREF_API_EMAIL="your@email.com"
export PUBMED_API_KEY="your_key"
```

## Caching

Results are cached at `~/.cache/openclaw/literature/`. Set `cache: false` in params to disable.

## Notes

- Semantic Scholar API works without a key (limited rate)
- Crossref works without a key (uses default email, polite mode)
- arXiv is always unlimited
- PubMed works without a key (limited rate)
