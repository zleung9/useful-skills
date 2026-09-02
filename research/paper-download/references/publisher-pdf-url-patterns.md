# Publisher PDF-URL Patterns

To `curl` the PDF endpoint you need its direct URL. Discovery strategies per publisher. The helper script's `find_pdf_url()` handles the generic cases; supplement with these when it fails.

## ACS (pubs.acs.org)

- Landing: `https://pubs.acs.org/doi/<doi>`
- PDF endpoint pattern: `https://pubs.acs.org/<journal-path>/article-pdf/<vol>/<issue>/<startpage>/<article-id>/<paper-id>.pdf`
  - e.g. `https://pubs.acs.org/jpclcd/article-pdf/16/18/4382/42037901/jz5c00658.pdf`
- On the landing page, the "Open PDF" / "PDF Link" anchor points at it. The `<journal-path>` differs per journal (jpclcd, jacsat, etc.) so derive it from the anchor, not by guessing.

## AIP (pubs.aip.org) — Physics of Fluids, J. Appl. Phys., etc.

- Landing: `https://pubs.aip.org/aip/<journal>/article-landing?doi=<doi>`
  - e.g. `https://pubs.aip.org/aip/pof/article-landing?doi=10.1063/5.0232224`
- PDF endpoint pattern: `https://pubs.aip.org/aip/<journal>/article-pdf/doi/<doi>/<vol-id>/<page-id>_<n>_<doi>.pdf`
  - e.g. `https://pubs.aip.org/aip/pof/article-pdf/doi/10.1063/5.0232224/20206928/103114_1_5.0232224.pdf`
- **Don't try to construct the `<vol-id>`/`<page-id>` yourself** — grab the full URL from Crossref (see "Crossref link (first-preference)" below) or from the landing-page anchor. The helper script's `find_pdf_url()` already matches `/article-pdf/`, so passing `--landing` is enough; supply `--pdf-url` too if you already have it from Crossref to skip discovery.
- **Cloudflare gate:** the landing page (and a bare `curl` of the PDF URL) returns a ~6 KB "Just a moment…" HTML stub. `curl --noproxy` alone cannot clear it — you **must** go through the real-Chrome + cookie-export path. This is the AIP-specific instance of the SKILL.md "Just a moment" pitfall.
- **XMU access:** confirmed by IP recognition (verified 2026-08-16 on `10.1063/5.0232224`, Physics of Fluids). No CARSI login needed; the Chrome session gets the full PDF via cookie'd curl. The `has_access()` footer-imprint heuristic is tuned for ACS's `by XIAMEN UNIV user` phrasing and may read `ACCESS_OK=False` on AIP even when access is fine — **if `find_pdf_url` returns a URL and the final curl yields a real `%PDF`, treat it as success regardless of the ACCESS_OK flag** (that's what happened here: ACCESS_OK=False but RESULT=PDF_OK, 5.2 MB).

## Crossref link (first-preference discovery, any publisher)

Before scraping landing-page anchors, ask Crossref for the publisher's own PDF link — it's canonical and skips one Cloudflare round-trip:

```bash
DOI="10.1063/5.0232224"
curl -sL --noproxy '*' "https://api.crossref.org/works/$DOI" \
  | python3 -c "import sys,json; d=json.loads(sys.stdin.read(),strict=False)['message']; [print(l['URL']) for l in d.get('link',[]) if l.get('content-type')=='application/pdf']"
```

- Pick the entry with `content-type: application/pdf` and `content-version: vor` (the "syndication" / "similarity-checking" `intended-application` variants point at the same file).
- This is **also the fastest OA-status probe** — if Crossref returns no `link[]` at all, the publisher exposes no PDF endpoint and you're looking at an HTML-only article.
- Gotcha: the response can contain raw control characters (e.g. in abstracts); parse with `json.loads(raw, strict=False)` or you'll hit `JSONDecodeError: Invalid control character` (seen on this very DOI).

## Wiley (onlinelibrary.wiley.com)

- Landing: `https://onlinelibrary.wiley.com/doi/<doi>`
- PDF: `https://onlinelibrary.wiley.com/doi/pdfdirect/<doi>?download=true`
  - or `https://onlinelibrary.wiley.com/doi/epdf/<doi>`
- The `pdfdirect` endpoint returns the raw PDF; `epdf` returns the viewer HTML — prefer `pdfdirect`.

## Elsevier / ScienceDirect (sciencedirect.com)

- Landing: `https://www.sciencedirect.com/science/article/pii/<PII>`
- PDF: `https://www.sciencedirect.com/science/article/pii/<PII>/pdfft?isDTLRedir=true&download=true`
- Elsevier sometimes requires a `sd-session` cookie + specific headers; if curl returns HTML, fall back to the in-page `fetch()` method (same-origin, carries auth).

## RSC (pubs.rsc.org)

- Landing: `https://pubs.rsc.org/en/content/articlelanding/<year>/<journal>/<doi>`
- PDF: `https://pubs.rsc.org/en/content/articlepdf/<year>/<journal>/<doi>`

## Springer / Nature

- Landing: `https://link.springer.com/article/<doi>` or `https://www.nature.com/articles/<id>`
- PDF: append `/pdf` to the article URL — `https://link.springer.com/content/pdf/<doi>.pdf`

## Generic discovery (any publisher)

1. On the landing page, enumerate all `<a>` elements.
2. Score each by href/text:
   - href contains `/article-pdf/` or `/doi/pdf` or `/pdfdirect/` or `/pdfft` → high
   - href ends in `.pdf` → high
   - text matches `Open PDF` / `PDF` / `Download PDF` → medium
3. Resolve relative hrefs against the publisher origin.
4. Prefer the highest-scored href whose path looks like a PDF endpoint over a generic "Download to Slide" image link (the ACS landing page has many decoy silverchair-cdn image anchors — ignore any `DownloadFile/DownloadImage.aspx` href).

## When discovery fails

- Use the in-page `fetch()` fallback in the helper script: it issues `fetch(pdfUrl, {credentials:'include'})` from the authenticated page context, so it carries the session even without a known cookie jar format.
- Or open the PDF viewer page in Chrome, read its final URL from `page.url` after navigation settles, and curl that.
