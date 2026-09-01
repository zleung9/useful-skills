#!/usr/bin/env python3
"""
web-search: Multi-backend web search via free JSON APIs.
Replaces the built-in WebSearch tool (US-only) for use from China.

Usage:
    python3 search.py "Polyimide properties" [--mode general|academic|all] [--limit 5]

Output: JSON array of results
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

# Local HTTP proxy (Clash)
PROXY_URL = "http://127.0.0.1:7890"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
MAILTO_USER_AGENT = f"{USER_AGENT} (mailto:zliang8@xmu.edu.cn)"


def _opener():
    proxy = urllib.request.ProxyHandler({"https": PROXY_URL, "http": PROXY_URL})
    return urllib.request.build_opener(proxy)


def _fetch_json(url, timeout=10, user_agent=None):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent or USER_AGENT})
    opener = _opener()
    resp = opener.open(req, timeout=timeout)
    return json.loads(resp.read().decode("utf-8"))


def _clean_html(text):
    return re.sub(r"<[^>]+>", "", text).strip()


def search_wikipedia(query, limit=5):
    try:
        q = query.replace(" ", "+")
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit={limit}"
        data = _fetch_json(url)
        results = []
        for r in data.get("query", {}).get("search", []):
            title = r.get("title", "")
            results.append({
                "source": "wikipedia",
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "snippet": _clean_html(r.get("snippet", ""))[:300],
            })
        return results
    except Exception as e:
        return [{"source": "wikipedia", "error": str(e)[:200]}]


def search_duckduckgo(query, limit=5):
    try:
        q = query.replace(" ", "+")
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1"
        data = _fetch_json(url)
        results = []
        abstract = data.get("Abstract", "")
        if abstract:
            results.append({
                "source": "duckduckgo",
                "title": data.get("Heading", ""),
                "url": data.get("AbstractURL", ""),
                "snippet": abstract[:300],
            })
        for t in data.get("RelatedTopics", []):
            if len(results) >= limit:
                break
            if isinstance(t, dict) and "Text" in t:
                results.append({
                    "source": "duckduckgo",
                    "title": t.get("Text", "")[:80],
                    "url": t.get("FirstURL", ""),
                    "snippet": t.get("Text", "")[:300],
                })
        return results
    except Exception as e:
        return [{"source": "duckduckgo", "error": str(e)[:200]}]


def search_crossref(query, limit=5):
    try:
        q = query.replace(" ", "+")
        url = f"https://api.crossref.org/works?query={q}&rows={limit}&sort=relevance"
        data = _fetch_json(url, timeout=15, user_agent=MAILTO_USER_AGENT)
        results = []
        for item in data.get("message", {}).get("items", []):
            title = item.get("title", [""])[0]
            year_pub = item.get("published-print", item.get("published-online", {}))
            year = year_pub.get("date-parts", [[""]])[0][0] if year_pub else ""
            doi = item.get("DOI", "")
            authors = ", ".join(
                a.get("family", "") for a in (item.get("author", []) or [])[:3]
            )
            if len(item.get("author", []) or []) > 3:
                authors += " et al."
            results.append({
                "source": "crossref",
                "title": title,
                "url": f"https://doi.org/{doi}" if doi else "",
                "snippet": f"[{year}] {authors}",
                "year": year,
                "doi": doi,
            })
        return results
    except Exception as e:
        return [{"source": "crossref", "error": str(e)[:200]}]


def search_semantic_scholar(query, limit=5, retries=2):
    for attempt in range(retries + 1):
        try:
            q = query.replace(" ", "+")
            url = (
                f"https://api.semanticscholar.org/graph/v1/paper/search?"
                f"query={q}&limit={limit}&fields=title,url,year,citationCount,abstract"
            )
            data = _fetch_json(url, timeout=10)
            results = []
            for p in data.get("data", []):
                abstract = (p.get("abstract") or "")[:200]
                results.append({
                    "source": "semantic_scholar",
                    "title": p.get("title", ""),
                    "url": p.get("url", ""),
                    "snippet": f"[{p.get('year', '')}] cited {p.get('citationCount', 0)}x. {abstract}",
                    "year": p.get("year"),
                    "citations": p.get("citationCount", 0),
                })
            return results
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            return [{"source": "semantic_scholar", "error": f"HTTP {e.code}: {str(e)[:150]}"}]
        except Exception as e:
            return [{"source": "semantic_scholar", "error": str(e)[:200]}]


def search(query, mode="all", limit=5):
    all_results = []
    backends = {
        "general": [search_wikipedia, search_duckduckgo],
        "academic": [search_crossref, search_semantic_scholar],
        "all": [search_wikipedia, search_duckduckgo, search_crossref, search_semantic_scholar],
    }
    for func in backends.get(mode, backends["all"]):
        try:
            results = func(query, limit=limit)
            all_results.extend(results)
        except Exception as e:
            all_results.append({"source": func.__name__, "error": str(e)[:200]})
        time.sleep(0.5)
    real = [r for r in all_results if "error" not in r]
    errors = [r for r in all_results if "error" in r]
    return real + errors


def main():
    parser = argparse.ArgumentParser(description="Web search via free JSON APIs")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--mode", choices=["general", "academic", "all"], default="all",
                        help="Search mode (default: all)")
    parser.add_argument("--limit", type=int, default=5, help="Results per backend (default: 5)")
    args = parser.parse_args()
    results = search(args.query, mode=args.mode, limit=args.limit)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
