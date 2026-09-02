# PDF to Markdown — MinerU API Skill

This skill converts scientific papers from PDF to Markdown using **MinerU's Standard API (v4)**.

## ⚠️ CRITICAL RULES

### NEVER use Pandoc
**Pandoc cannot read PDF files.** It can only convert *to* PDF, not *from* PDF. Do not attempt to use pandoc for PDF conversion. Only use MinerU.

### Only use MinerU
This skill is exclusively for MinerU. Do not use pdfminer, pypdf2, PyMuPDF, or any other tool for converting PDFs to Markdown. MinerU provides superior layout understanding, figure extraction, and table formatting.

## Quick Start

```bash
python3 ~/.agents/skills/pdf-to-markdown/scripts/convert.py <pdf_path>
```

## API Reference

| Item | Value |
|------|-------|
| **Base URL** | `https://mineru.net/api/v4` |
| **Docs** | `https://mineru.net/apiManage/docs` |
| **Auth** | `Authorization: Bearer <token>` header |
| **API key location** | `~/.mineru/config` (format: `MINERU_API_KEY=eyJ...`) |

> ⚠️ **CRITICAL**: The old endpoint `https://api.mineru.net` does **NOT** exist. Always use `mineru.net/api/v4`.

## API Key

The token is a JWT. To check if it's valid:

```bash
export MINERU_API_KEY=$(grep MINERU_API_KEY ~/.mineru/config | cut -d'=' -f2-)
curl -s https://mineru.net/api/v4/extract/task \
  -H "Authorization: Bearer $MINERU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf", "model_version": "vlm"}'
```

A successful response: `{"code":0,"msg":"ok","data":{"task_id":"..."}}`

## Two Conversion Modes

### Mode 1: URL Mode (Recommended — simpler, more reliable)

MinerU downloads the file from a public HTTPS URL. No upload step needed.

```bash
curl -s https://mineru.net/api/v4/extract/task \
  -X POST \
  -H "Authorization: Bearer $MINERU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-public-url.com/paper.pdf",
    "file_name": "paper.pdf",
    "model_version": "vlm",
    "language": "en",
    "enable_table": true,
    "enable_formula": true
  }'
```

Returns: `{"code":0,"msg":"ok","data":{"task_id":"..."}}`

### Mode 2: File Upload Mode (⚠️ Known Bug — Open Issue)

The 3-step upload process (get signed URL → PUT to OSS → submit task) has a **known bug** — confirmed by multiple users on GitHub issue #4257 and others. The upload succeeds (HTTP 200), but MinerU's processing service returns `"failed to read file"` when trying to read the uploaded file.

**This affects all users, not just this setup.** The issue is open and unfixed as of 2026-04-07.

**Current workaround**: Use URL mode (Mode 1). If the PDF is local, expose it via a cloudflared tunnel (see below).

### Getting a Public URL for Local Files

If the PDF is local and has no public URL, you have these options:

**Option A: Use cloudflared tunnel (recommended)**
```bash
# Install cloudflared
brew install cloudflared

# In terminal A: start a local HTTP server
cd /path/to/pdf/folder
python3 -m http.server 8000

# In terminal B: create tunnel to expose local server
cloudflared tunnel --url http://localhost:8000
# Copy the public URL (e.g., https://xyz.trycloudflare.com)

# Use that URL in MinerU URL mode
```

**Option B: Upload to a public file host**
- Use a service like transfer.sh, file.io, or any public URL that MinerU can reach
- Note: 0x0.st is currently disabled due to abuse

**Option C: Upload to Feishu Drive then use the URL**
```bash
# Upload to Feishu Drive
lark-cli drive +upload --file-path /path/to/paper.pdf --folder-token <folder_token>

# Use the Feishu file URL in MinerU URL mode
# Note: MinerU must be able to reach the URL (Feishu file URLs require login, not suitable)
```

## Polling for Result

```bash
curl -s "https://mineru.net/api/v4/extract/task/{task_id}" \
  -H "Authorization: Bearer $MINERU_API_KEY"
```

State values:
1. `waiting-file` — waiting for file upload
2. `uploading` — downloading file
3. `pending` — queued
4. `running` — extraction in progress
5. `done` — ✅ complete, use `markdown_url` or `full_zip_url`
6. `failed` — ❌ error, check `err_msg`

## Download Result

When `done`, download from `markdown_url` (preferred) or `full_zip_url`:
```bash
curl -L -o output.zip "https://cdn-mineru.openxlab.org.cn/pdf/...zip"
unzip -j output.zip -d output_dir/
```

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| `A0202` | Invalid Token | Check API key is correct, not expired |
| `A0211` | Token expired | Get a new token from mineru.net |
| `-10002` | Parameter error | Use `name` not `file_name` in batch endpoint |
| `-60003` | File read failure | Try re-uploading with fresh signed URL |
| `-60005` | File too large | Max 200MB |
| `-60006` | Too many pages | Max 600 pages, use `page_range` to split |
| `-60010` | Extract failed | Try with smaller `page_range` |
| `-60011` | File not accessible | URL mode: check URL is public. OSS mode: use tunnel. |
| `parsing failed` | Cannot parse URL | URL is not a direct file download (may require login) |

## Model Versions

- `vlm` — **Recommended**. Better layout understanding.
- `pipeline` — Default, faster, for simpler documents.
- `MinerU-HTML` — For HTML source files only.

## Language Codes

- `ch` — Chinese + English (default)
- `en` — English only
- `ch_server` — Chinese Traditional + Japanese

## Known Issues & Lessons Learned

### Issue: `api.mineru.net` doesn't resolve
- **Cause**: API is at `mineru.net/api/v4`, not `api.mineru.net`. That subdomain doesn't exist.
- **Fix**: Always use `https://mineru.net/api/v4`

### Issue: TLS/SSL errors through proxy
- **Cause**: ClashX (`127.0.0.1:7890`) does TLS interception.
- **Fix**: Add `DOMAIN,mineru.net,DIRECT` to ClashX rules. Reload config.

### Issue: OSS signed URL upload → "failed to read file"
- **Cause**: OSS bucket is China-internal. MinerU's processing service can't read externally-uploaded files.
- **Fix**: Do NOT use file upload mode. Use URL mode with a public URL, or use cloudflared tunnel.

### Issue: Feishu Drive URL in MinerU → "parsing failed"
- **Cause**: Feishu file URLs (`my.feishu.cn/file/...`) require login, not direct downloads.
- **Fix**: Download the file locally first, then expose via cloudflared tunnel.

### Issue: Proxy is down
- **Cause**: MinerU is in China. Without proxy, `mineru.net` is unreachable.
- **Fix**: Ensure ClashX is running with `mineru.net` routed to China.

### Issue: Large PDFs fail
- **Cause**: Timeout or size limit.
- **Fix**: Split into chunks with `page_range` (e.g. `"1-50"`, `"51-100"`).

### Issue: "failed to read file, please check if the file is corrupted"
- **Cause**: Almost always a network/connectivity issue, not a corrupt file. MinerU's service can't reach the URL or OSS bucket.
- **Fix**: For OSS uploads: use cloudflared tunnel instead. For URL mode: verify the URL is publicly accessible without login.

## Output

The `.md` file is saved **alongside** the original PDF in the same folder.

```
~/Nutstore Files/zotero/storage/89F3JPDJ/
├── Rubinstein and Colby - 2014 - Polymer physics.pdf   ← original
└── Rubinstein and Colby - 2014 - Polymer physics.md   ← converted
```

**Rule: Skip if `.md` already exists** alongside the PDF.
