---
name: mineru-pdf
description: "Convert documents (PDF, DOCX, PPTX, images, HTML) to Markdown using the MinerU cloud API. Produces markdown text with extracted figures. Use when the user wants to parse, convert, or extract content from PDF papers or other supported document formats."
---

# MinerU Document-to-Markdown Converter

Convert documents to Markdown with extracted figures using the MinerU cloud API.

## Prerequisites

- A MinerU API token stored in `~/.mineru_token`. On first use, ask the user for their token and save it:
  ```bash
  echo "TOKEN_HERE" > ~/.mineru_token && chmod 600 ~/.mineru_token
  ```
- `curl`, `unzip`, and `python3` must be available.

## When to Use

- User asks to convert a PDF paper to Markdown
- User wants to extract text and figures from a scientific paper
- User mentions MinerU or PDF parsing/extraction
- User wants to convert DOCX, PPTX, images, or HTML to Markdown

## Supported Formats

PDF, DOC, DOCX, PPT, PPTX, images (PNG/JPG/JPEG/JP2/WEBP/GIF/BMP), HTML

## API Overview

MinerU offers two APIs:

| Feature | Precision Extract API | Agent Lightweight API |
|---------|----------------------|----------------------|
| Auth | Bearer token required | Free, IP-rate-limited |
| Max file size | 200MB | 10MB |
| Max pages | 600 | 20 |
| Batch support | Yes (up to 200 files) | No |
| Output | ZIP (MD + images + JSON); optional DOCX/HTML/LATEX | Markdown URL only |
| Models | `pipeline` (default), `vlm` (recommended), `MinerU-HTML` | `pipeline` (fixed) |

**Use Precision API** for scientific papers (the common case). **Use Agent Lightweight API** only for quick, small-file conversions without a token.

## Workflow

### Determining the Output Directory

Before creating any folder, check whether the PDF already lives inside its own output folder (i.e. a redo/re-conversion). The rule:

- If the PDF's **parent directory** already contains a `full.md` file, the PDF has been processed before. Use the parent directory as `OUTPUT_DIR` directly — do **not** create a new subfolder. The new results will overwrite the old ones in place.
- Otherwise, create a sibling directory named after the PDF (without extension) and use that.

```bash
PDF_PATH="/absolute/path/to/paper.pdf"
PDF_NAME=$(basename "$PDF_PATH" .pdf)
PARENT_DIR=$(dirname "$PDF_PATH")

if [ -f "$PARENT_DIR/full.md" ]; then
  # Redo: PDF is already inside its output folder
  OUTPUT_DIR="$PARENT_DIR"
else
  # Fresh conversion: create sibling folder
  OUTPUT_DIR="$PARENT_DIR/$PDF_NAME"
fi
```

### For Local PDF Files (Precision API)

Run the entire conversion as a single script. This is the proven, tested workflow:

```bash
MINERU_TOKEN=$(cat ~/.mineru_token)
PDF_PATH="/absolute/path/to/paper.pdf"
PDF_NAME=$(basename "$PDF_PATH" .pdf)
PARENT_DIR=$(dirname "$PDF_PATH")

# Detect redo: if full.md exists alongside the PDF, reuse current folder
if [ -f "$PARENT_DIR/full.md" ]; then
  OUTPUT_DIR="$PARENT_DIR"
else
  OUTPUT_DIR="$PARENT_DIR/$PDF_NAME"
fi

# Sanitize data_id: alnum + underscore only, max 100 chars
DATA_ID=$(echo "$PDF_NAME" | tr -c 'A-Za-z0-9' '_' | cut -c1-100)

# 1. Request upload URL
RESPONSE=$(curl -s -X POST 'https://mineru.net/api/v4/file-urls/batch' \
  -H "Authorization: Bearer $MINERU_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"files\": [{\"name\": \"$DATA_ID.pdf\", \"data_id\": \"$DATA_ID\"}], \"enable_formula\": true, \"enable_table\": true, \"language\": \"en\"}")

BATCH_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['batch_id'])")
FILE_URL=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['file_urls'][0])")

# 2. Upload — use --globoff to prevent curl interpreting [] in filenames
curl -s --globoff -X PUT -T "$PDF_PATH" "$FILE_URL"

# 3. Poll until done (timeout after ~8 minutes)
for i in $(seq 1 60); do
  RESULT=$(curl -s -X GET "https://mineru.net/api/v4/extract-results/batch/$BATCH_ID" \
    -H "Authorization: Bearer $MINERU_TOKEN")
  STATE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['extract_result'][0]['state'])" 2>/dev/null)
  if [ "$STATE" = "done" ]; then
    ZIP_URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['extract_result'][0]['full_zip_url'])")
    break
  elif [ "$STATE" = "failed" ]; then
    ERR=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['extract_result'][0]['err_msg'])" 2>/dev/null)
    echo "FAILED: $ERR"
    exit 1
  fi
  sleep 8
done

if [ -z "$ZIP_URL" ]; then echo "Timed out waiting for extraction"; exit 1; fi

# 4. Download and extract
mkdir -p "$OUTPUT_DIR"
curl -s -L -o "$OUTPUT_DIR/result.zip" "$ZIP_URL"
unzip -o "$OUTPUT_DIR/result.zip" -d "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/result.zip"

echo "Done! Output in $OUTPUT_DIR"
```

### For Remote PDF URLs (Precision API)

```bash
MINERU_TOKEN=$(cat ~/.mineru_token)
PDF_URL="https://example.com/paper.pdf"
PDF_NAME="paper-name"  # derive from URL
OUTPUT_DIR="/path/to/output/$PDF_NAME"

# 1. Submit extraction task
RESPONSE=$(curl -s -X POST 'https://mineru.net/api/v4/extract/task' \
  -H "Authorization: Bearer $MINERU_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"url\": \"$PDF_URL\", \"enable_formula\": true, \"enable_table\": true, \"language\": \"en\"}")

TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['task_id'])")

# 2. Poll until done
for i in $(seq 1 60); do
  RESULT=$(curl -s -X GET "https://mineru.net/api/v4/extract/task/$TASK_ID" \
    -H "Authorization: Bearer $MINERU_TOKEN")
  STATE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['state'])" 2>/dev/null)
  if [ "$STATE" = "done" ]; then
    ZIP_URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['full_zip_url'])")
    break
  elif [ "$STATE" = "failed" ]; then
    echo "FAILED"; exit 1
  fi
  sleep 8
done

if [ -z "$ZIP_URL" ]; then echo "Timed out"; exit 1; fi

# 3. Download, extract, clean up
mkdir -p "$OUTPUT_DIR"
curl -s -L -o "$OUTPUT_DIR/result.zip" "$ZIP_URL"
unzip -o "$OUTPUT_DIR/result.zip" -d "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/result.zip"

echo "Done! Output in $OUTPUT_DIR"
```

### For Small Files Without a Token (Agent Lightweight API)

For files under 10MB and 20 pages — no token needed:

```bash
PDF_PATH="/absolute/path/to/paper.pdf"
PDF_NAME=$(basename "$PDF_PATH" .pdf)
DATA_ID=$(echo "$PDF_NAME" | tr -c 'A-Za-z0-9' '_' | cut -c1-100)

# 1. Get upload URL and task_id
RESPONSE=$(curl -s -X POST 'https://mineru.net/api/v1/agent/parse/file' \
  -H 'Content-Type: application/json' \
  -d "{\"file_name\": \"$DATA_ID.pdf\", \"language\": \"en\", \"enable_formula\": true, \"enable_table\": true}")

TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['task_id'])")
FILE_URL=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['file_url'])")

# 2. Upload
curl -s --globoff -X PUT -T "$PDF_PATH" "$FILE_URL"

# 3. Poll until done
for i in $(seq 1 60); do
  RESULT=$(curl -s -X GET "https://mineru.net/api/v1/agent/parse/$TASK_ID")
  STATE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['state'])" 2>/dev/null)
  if [ "$STATE" = "done" ]; then
    MD_URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['data']['markdown_url'])")
    break
  elif [ "$STATE" = "failed" ]; then
    echo "FAILED"; exit 1
  fi
  sleep 5
done

# 4. Download markdown
curl -s -L -o "/path/to/output.md" "$MD_URL"
```

## Shell Compatibility (zsh + bash)

The default shell on macOS is zsh, which errors on unmatched globs (e.g. `rm *.foo` fails if no `.foo` files exist). To avoid this:
- Use `rm -f` only with explicit filenames, not wildcard patterns
- Use `find ... -name '*.ext' -delete` instead of `rm *.ext` when matching by pattern
- Use `$(seq 1 N)` for loops (works in both bash and zsh)

## Output Structure

After conversion (Precision API), each paper folder contains:
- **`full.md`** — The main Markdown text with inline image references
- **`images/`** — Extracted figures as JPG files (referenced by `full.md`)
- **`layout.json`** — Page layout structure data
- **`*_content_list.json`** — Structured content metadata

## Batch Processing (Many Files)

For converting many files at once, create a reusable shell script that:

1. Reads a list of file paths (one per line) from a text file
2. Processes each sequentially with skip-if-done logic
3. Logs progress to a file (OK/SKIP/FAIL per file + final SUMMARY)

Key lessons from production batch runs:

- **Sanitize `data_id`**: Strip non-alnum chars (`tr -c 'A-Za-z0-9' '_'`) — spaces and special chars break the JSON payload.
- **Use `curl --globoff`**: Filenames with `[brackets]` cause curl to interpret them as URL range patterns, failing the upload silently.
- **Use 8-minute timeout** (60 polls × 8s sleep): 4 minutes is too short for large papers. Textbooks may still timeout — the 600-page API limit is the hard ceiling.
- **Run via `nohup bash script.sh &`** for long batch jobs to survive terminal disconnects.
- **Typical speed**: ~18–20 seconds per paper (upload + extraction + download).

## Optional API Parameters

These can be added to the batch or single-file request JSON:

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `model_version` | string | `pipeline` | `vlm` (recommended for higher quality), `MinerU-HTML` |
| `page_ranges` | string | all | e.g., `"1-10"` or `"2,4-6"` — useful for splitting large files |
| `extra_formats` | array | none | `["docx","html","latex"]` for additional output formats |
| `callback` | string | none | Webhook URL for async result delivery |
| `seed` | string | none | Required if using callback |
| `no_cache` | bool | false | Bypass server-side cache |
| `is_ocr` | bool | false | Force OCR mode for scanned documents |

## Error Handling

| Code | Meaning | Action |
|------|---------|--------|
| `A0202` | Token error | Verify token format with "Bearer " prefix |
| `A0211` | Token expired | Request new token |
| `-60005` | File exceeds 200MB | Split file |
| `-60006` | Page count exceeds 600 | Use `page_ranges` to split, or manually split the PDF |
| `-60012` | Task not found | Verify task_id/batch_id |
| `-60013` | Permission denied | Can only access own tasks |

## Extraction States

| State | Meaning |
|-------|---------|
| `done` | Complete — `full_zip_url` available |
| `pending` | Queued for processing |
| `running` | Processing (response includes `extracted_pages`/`total_pages`) |
| `converting` | Generating extra output formats |
| `failed` | Error — check `err_msg` |

## API Limits

| Limit | Value |
|-------|-------|
| Max file size | 200MB |
| Max pages | 600 |
| Max batch size | 200 files |
| Daily page quota | 2000 pages (at highest priority) |

## URL Mode Workarounds & Known Issues

See `references/url-mode-workarounds.md` for session-specific troubleshooting — TLS/proxy issues with ClashX, OSS upload failures, cloudflared tunnel setup, and the full history of known connectivity problems when using MinerU from outside China.
