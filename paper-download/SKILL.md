---
name: paper-download
description: "Download the PDF of a research paper given a DOI or URL. Tries open-access sources first (Unpaywall, OpenAlex, arXiv, ChemRxiv, PMC, author pages), then falls back to institutional subscription access via a real Chrome (Playwright) session that exports cookies and curls the publisher's PDF endpoint. Use when the user asks to fetch/download a paper, article, or PDF by DOI/URL. Avoids shadow libraries (Sci-Hub/LibGen)."
---

# Paper Download

Fetch the full-text PDF of a research paper from a DOI or URL. Open-access sources are tried first; if none exist, fall back to institutional subscription access through a real Chrome browser session that exports its cookies and downloads the publisher PDF via `curl`.

**Do not use Sci-Hub, LibGen, or any shadow library.** Institutional access on this Mac works through IP recognition (XMU is recognized by ACS, Wiley, etc.) — see `references/institutional-access.md`.

## When to Use

- User asks to "download / fetch / get the PDF of" a paper by DOI or URL
- User gives a `https://doi.org/...` or publisher URL and wants the full PDF
- User mentions a journal article and wants the actual file, not just metadata

## Prerequisites

- `curl`, `python3` available.
- Playwright + Chromium installed in a venv. On first use, set it up:
  ```bash
  VENV="$HOME/.claude/jobs/_paperdl/venv"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q playwright
  "$VENV/bin/playwright" install chromium
  ```
  Reuse an existing `~/.claude/jobs/*/tmp/venv/` if one already has playwright.
- Real Google Chrome installed at `/Applications/Google Chrome.app/...` (preferred over bundled Chromium — real Chrome clears Cloudflare's "Just a moment" challenge far more reliably).

## Output Convention

Save the PDF and a metadata sidecar to `~/Downloads/<slug>/` where `<slug>` is derived from the first author + year + short title (e.g. `zhao-2025-multispectral-fusion`). This follows the user's scratch-dir preference (see `references/` / memory `feedback_scratch_dir`).

```bash
OUTDIR="$HOME/Downloads/$SLUG"
mkdir -p "$OUTDIR"
PDF_PATH="$OUTDIR/$SLUG.pdf"
```

## Workflow

### Step 0 — Resolve metadata (skip if the user already gave the PDF URL)

From a DOI, get title/authors/journal to build the slug and to check OA status:

```bash
DOI="10.1021/acs.jpclett.5c00658"
META=$(curl -sL --noproxy '*' "https://api.crossref.org/works/$DOI")
# parse title, authors, year with python3 -c json
```

For OA lookup, query Unpaywall: `https://api.unpaywall.org/v2/$DOI?email=...` — `best_oa_location.url_for_pdf` gives a free PDF if one exists.

**Also grab the publisher's own PDF link** while you have Crossref open — it's the canonical PDF endpoint and skips one landing-page scrape. Parse `message.link[]`, pick the entry with `content-type: application/pdf` + `content-version: vor`, and pass it to the helper as `--pdf-url`. Parse with `json.loads(raw, strict=False)` (abstracts can contain raw control chars — seen on `10.1063/5.0232224`). See `references/publisher-pdf-url-patterns.md` § "Crossref link (first-preference discovery)".

### Step 1 — Try open-access sources first

In order, only if the paper is OA:
1. **Unpaywall** `best_oa_location.url_for_pdf`
2. **OpenAlex** `open_access.oa_url`
3. **Semantic Scholar** `openAccessPdf`
4. **arXiv** (if DOI maps to an arXiv preprint) → `https://arxiv.org/pdf/<id>`
5. **ChemRxiv** for chemistry preprints
6. **PMC** for biomedical
7. Author/lab page (search the web)

If any returns a PDF URL, `curl -sL --noproxy '*' -o "$PDF_PATH" "$OA_URL"` and verify (Step 4). Done.

### Step 2 — Institutional access via real Chrome + cookie export (the closed-access path)

This is the **proven method** for subscription journals (ACS, Wiley, Elsevier, RSC, Nature, etc.) on this Mac. The machine's network is recognized by institutional subscriptions, so the PDF **is** served — the only hard part is saving it. **Do not rely on Playwright's `expect_download` or `Page.printToPDF`** (see Pitfalls below).

Run the helper script, parameterized by DOI and output path:

```bash
VENV="$HOME/.claude/jobs/_paperdl/venv"
"$VENV/bin/python3" "$(dirname "$(readlink -f "$0")")/scripts/download_paper.py" \
  --doi "$DOI" \
  --out "$PDF_PATH" \
  --profile "$HOME/.claude/jobs/_paperdl/chrome_profile"
```

What the script does (see `scripts/download_paper.py`):
1. Clears all proxy env vars (`http_proxy`, `https_proxy`, …) **before** importing Playwright, and launches Chrome with `--no-proxy-server`. This neutralizes the local Clash proxy so the browser egresses directly to the campus-recognized network.
2. Launches **real Google Chrome** (`channel="chrome"`, headed, persistent profile) — the persistent profile retains Cloudflare clearance and institutional session across runs.
3. Navigates to the article landing page (`https://pubs.acs.org/doi/<doi>` or equivalent); lets Cloudflare's "Just a moment…" auto-clear (usually <30s for real Chrome).
4. Confirms institutional access: the rendered PDF page footer imprints "by XIAMEN UNIV user" (or analogous). **Do not assume a China-Telecom-looking egress IP means no access** — ACS recognized XMU even from a 117.28.251.154 (China Telecom) egress.
5. Exports the session cookies (`context.cookies()`) + User-Agent to a Netscape cookie jar.
6. `curl -sL --noproxy '*' -A "$UA" -b cookies.txt -e '<landing-url>' -o "$PDF_PATH" '<pdf-url>'`.
7. Returns; the main loop verifies the file.

### Step 3 — Finding the PDF URL

The publisher's PDF endpoint must be passed to `curl`. Strategies, in order:
- **ACS:** from the landing page, the "Open PDF" / "PDF Link" anchor points to `https://pubs.acs.org/<journal>/article-pdf/<vol>/<issue>/<page>/<id>/<paperid>.pdf`.
- **Generic:** enumerate `a` anchors on the landing page whose href contains `/pdf` or whose text contains "PDF", prefer the one whose path contains `/article-pdf/` or `/doi/pdf/`.
- **If the anchor is a relative path**, prepend the publisher origin.
- The helper script auto-discovers PDF anchors from the landing page.

### Step 4 — Verify the PDF

A downloaded file is only valid if it passes all three checks:

```bash
file "$PDF_PATH"                         # must say "PDF document, version X.Y, N pages"
SIZE=$(stat -f%z "$PDF_PATH")            # macOS stat; must be > 50000
HEAD=$(head -c 8 "$PDF_PATH" | xxd)      # must start with "2550 4446" = %PDF
```

Reject and retry if: the file is HTML (Cloudflare stub, ~5KB), starts with `<` or `<!DOCTYPE`, or `file` says "ASCII text" / "HTML document". A stale Cloudflare stub from a previous run will fool a naive size check — always check the magic bytes.

### Step 5 — Write metadata sidecar

```bash
cat > "$OUTDIR/metadata.json" <<EOF
{ "doi": "$DOI", "pdf_path": "$PDF_PATH", "size": $SIZE,
  "pdf_downloaded": true, "method": "chrome-cookie-curl", "source": "..." }
EOF
```

## Pitfalls (all hit during development — do not repeat)

| Pitfall | Why | Fix |
|---|---|---|
| `expect_download` times out (90s) | Chrome renders PDFs **inline** in its viewer; the download event never fires and `save_as()` is never called | Export cookies + `curl` the PDF endpoint |
| `Page.printToPDF` yields a valid but 1-page PDF | It only captures the single viewport page, not the full document | Same — use cookie + curl |
| Stale ~5KB Cloudflare HTML stub passes a naive size check | `file` says "HTML"; magic bytes are `3c2144` not `2550 4446` | `rm -f` old output before each run; always check magic bytes |
| "Machine not on XMU network" misdiagnosis | A subagent saw a China-Telecom egress IP and concluded no access — **wrong**, XMU was still recognized | Verify access from rendered-page evidence (footer imprint), not from egress IP org string |
| Clash proxy intercepts the request | Local Clash SOCKS/system proxy on 127.0.0.1:7897 reroutes traffic | `--no-proxy-server` + clear proxy env vars before importing Playwright; TUN mode OFF is required (user confirms) |
| `playwright_stealth` import fails | `cannot import name 'stealth_sync'` | Not needed — real Chrome passes Cloudflare without stealth |

## Method-Selection Logic (decision tree)

```
Given DOI/URL
 ├─ Is there an OA copy? (Unpaywall/OpenAlex/S2/arXiv/ChemRxiv/PMC) → curl OA URL → verify → done
 └─ No OA → institutional access:
     ├─ Launch real Chrome (Playwright, --no-proxy-server, persistent profile)
     ├─ Goto landing page, let Cloudflare clear
     ├─ Confirm access (footer imprint "by <INST> user")
     │    └─ If paywall markers (purchase/sign-in) and no imprint → hand the CARSI login
     │       page to the USER; do not enter credentials automatically
     ├─ Export cookies + UA → Netscape jar
     ├─ curl PDF endpoint with -b jar -A UA -e landing → verify → done
```

## Files

- `scripts/download_paper.py` — parameterized helper (real Chrome → cookie export → curl)
- `references/institutional-access.md` — which publishers recognize XMU on this Mac, CARSI login handoff
- `references/publisher-pdf-url-patterns.md` — how to find the PDF endpoint per publisher
