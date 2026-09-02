# Qwen Vision — Read Images via Huawei AI Platform

Use this skill whenever you need to **read, describe, or analyze an image file** (PNG, JPG, etc.). Claude cannot read images directly in this environment, and passing images into the conversation will collapse it — so delegate all image-reading to the Qwen3.6-35B-A3B model on the Huawei AI Platform.

## When to Use

- User asks to read, describe, or analyze an image
- You encounter an image file (PNG, JPG, BMP, TIFF, WebP, GIF) that you need to understand
- Any task that requires visual understanding of a figure, diagram, photo, or plot

## When NOT to Use

- Reading PDFs (use the mineru-pdf skill instead)
- Non-image files

## Network Configuration

All requests to `10.26.15.52` MUST bypass any local proxy. Always prefix commands with:
```bash
NO_PROXY="10.26.15.52,10.0.0.0/8"
```

## API Details

### Inference Endpoint (OpenAI-compatible)

```
http://10.26.15.52:30081/<SERVICE_UUID>/v1/chat/completions
```

- **Protocol:** HTTP (not HTTPS) on port 30081
- **Auth:** Bearer token with API key
- **Content-Type:** `application/json`

### Authentication

- **API Key:** Read from environment variable `HUAWEI_API_KEY` (set in `~/.bashrc`)
- **Header:** `Authorization: Bearer $HUAWEI_API_KEY`
- Fallback: read directly from `~/.bashrc` line `export HUAWEI_API_KEY="..."`

### Model and Service UUID

- **Model name:** `Qwen3.6-35B-A3B`
- **Service UUID:** `ccb44b4cfe18439f8affd07babd0810e`
- **Full endpoint URL:** `http://10.26.15.52:30081/ccb44b4cfe18439f8affd07babd0810e/v1/chat/completions`

> **If the service UUID stops working**, query the management API to find the current UUID:
> ```bash
> NO_PROXY="10.26.15.52,10.0.0.0/8" python3 -c "
> import json, urllib.request, ssl, base64
> AUTH = base64.b64encode(b'rootRedfish:Machine@123').decode()
> ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
> opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
> req = urllib.request.Request('https://10.26.15.52/ai/api/v1/serving/services?clusterId=fleet-local/local', headers={'Authorization': f'Basic {AUTH}'})
> with opener.open(req, timeout=15) as resp:
>     services = json.loads(resp.read())['data']['result']
>     for s in services:
>         if 'Qwen3.6-35B-A3B' in s['name'] and s['status'] == '2':
>             print(f\"{s['name']}: uuid={s['url'].split('/')[-1]}, running={s['runningNode']}/{s['totalNode']}\")
> "
> ```
> Status `2` = running, Status `3` = stopped. Pick the one with status `2` and `runningNode > 0`.

### Management API (for discovering service UUIDs only)

- **Base URL:** `https://10.26.15.52` (HTTPS, self-signed cert)
- **Auth:** Basic Auth — `rootRedfish:Machine@123`
- **Services list:** `GET /ai/api/v1/serving/services?clusterId=fleet-local/local`
- **SSL:** Self-signed certificate — must disable verification

## Request Format

The endpoint follows the OpenAI Chat Completions API with multimodal support:

```json
{
  "model": "Qwen3.6-35B-A3B",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "<YOUR_QUESTION>"},
        {"type": "image_url", "image_url": {"url": "data:image/<FORMAT>;base64,<BASE64_DATA>"}}
      ]
    }
  ],
  "max_tokens": 2048
}
```

- **`<FORMAT>`**: MIME subtype — `png`, `jpeg`, `webp`, etc.
- **`<BASE64_DATA>`**: Base64-encoded content of the image file
- **`<YOUR_QUESTION>`**: What you want to know about the image

## Complete Python Script

Save and run with `NO_PROXY="10.26.15.52,10.0.0.0/8" python3 <script>.py <image_path> [question]`:

```python
#!/usr/bin/env python3
"""Read an image using Qwen3.6-35B-A3B on the Huawei AI Platform."""
import json, urllib.request, base64, sys, os, mimetypes, re

# Read API key from .bashrc
def get_api_key():
    key = os.environ.get("HUAWEI_API_KEY")
    if key:
        return key
    bashrc = os.path.expanduser("~/.bashrc")
    with open(bashrc) as f:
        for line in f:
            m = re.match(r'export\s+HUAWEI_API_KEY="([^"]+)"', line.strip())
            if m:
                return m.group(1)
    raise RuntimeError("HUAWEI_API_KEY not found in env or ~/.bashrc")

API_KEY = get_api_key()
SERVICE_UUID = "ccb44b4cfe18439f8affd07babd0810e"
BASE = "http://10.26.15.52:30081"
ENDPOINT = f"{BASE}/{SERVICE_UUID}/v1/chat/completions"

def read_image(image_path: str, question: str = "Please describe this image in detail.") -> str:
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    mime, _ = mimetypes.guess_type(image_path)
    if not mime:
        mime = "image/png"
    fmt = mime.split("/")[-1]

    payload = {
        "model": "Qwen3.6-35B-A3B",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{img_b64}"}}
            ]
        }],
        "max_tokens": 2048
    }

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=300) as resp:
        r = json.loads(resp.read())
        if "choices" in r:
            return r["choices"][0]["message"]["content"]
        else:
            return json.dumps(r, indent=2)[:3000]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <image_path> [question]")
        sys.exit(1)
    image_path = sys.argv[1]
    question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Please describe this image in detail."
    print(read_image(image_path, question))
```

## Workflow

1. **Identify the image** — locate the file path
2. **Read API key** — from `$HUAWEI_API_KEY` env var, or from `~/.bashrc`
3. **Determine MIME type** — PNG → `image/png`, JPG → `image/jpeg`, etc.
4. **Base64 encode** the image file
5. **Send request** to `http://10.26.15.52:30081/<SERVICE_UUID>/v1/chat/completions` with Bearer auth
6. **Return the model's response** — it contains the visual description/analysis

## Important Notes

- **Always use `NO_PROXY="10.26.15.52,10.0.0.0/8"`** — the campus network must bypass any local proxy
- **Port 30081 is HTTP, not HTTPS** — do not use SSL on this port
- **Timeout:** Image requests can take 30–120 seconds; set timeout to at least 300 seconds
- **Payload size:** A typical 500KB PNG produces ~640KB of base64 text; this is fine for the API
- **If you get a 500 error** with "service not started or abnormal", the service UUID may have changed — use the management API lookup above
- **Never use `https://` on port 30081** — it will fail with SSL errors
- **Never use port 443** for inference — that's the management API only
