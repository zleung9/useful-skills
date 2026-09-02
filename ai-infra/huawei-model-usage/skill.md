# Huawei AI Platform Model Usage Monitor

Query the Huawei AI Platform API to retrieve model usage statistics, including per-model request counts, token consumption, and daily load breakdowns.

## Prerequisites

- Network access to `10.26.15.52:30081` (campus network, NO_PROXY required)
- `curl`, `python3` must be available

## When to Use

- User asks about Huawei model usage, load, or consumption
- User wants to check how much the Huawei AI models are being used
- User asks for daily/weekly model usage reports
- User mentions "华为模型用量", "Huawei model usage", "调用量"

## Network Configuration

All requests to `10.26.15.52` MUST bypass any local proxy. Always prefix commands with:
```bash
NO_PROXY="10.26.15.52,10.0.0.0/8"
```

## API Details

### Base URL
```
https://10.26.15.52/ai/api/v1/serving
```

### Authentication
All endpoints use HTTP Basic Authentication:
- **Username:** `rootRedfish`
- **Password:** `Machine@123`
- **Base64 encoded:** `cm9vdFJlZGZpc2g6TWFjaGluZUAxMjM=`
- **Header:** `Authorization: Basic cm9vdFJlZGZpc2g6TWFjaGluZUAxMjM=`

In curl, use `-u rootRedfish:Machine@123` or the explicit header. Add `-k` flag for SSL (self-signed cert).

### Endpoint 1: Get API Key List

```
GET /ai/api/v1/serving/apikeys?clusterId=fleet-local/local
```

Returns all API keys with their IDs, names, tokens, and metadata.

**Important:** Do NOT use `mine=true` or `all=true` parameters — they return empty results. Only use `clusterId=fleet-local/local`.

### Endpoint 2: Get API Key Usage Monitoring

```
POST /ai/api/v1/serving/apikeys/apiKeyMonitor/form
```

**Request body parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| apikeyIds | Array[String] | Yes | API Key IDs as strings (e.g., `["1","2","3"]`) |
| startTs | Long | Yes | Start timestamp (Unix seconds) |
| endTs | Long | Yes | End timestamp (Unix seconds) |
| inferenceNames | Array[String] | No | Filter by inference service name; empty = all |
| pageSize | Integer | No | Page size (default 10) |
| pageNum | Integer | No | Page number (default 1) |
| clusterId | String | Yes | Cluster ID: `fleet-local/local` |

**Critical:** `apikeyIds` values MUST be strings (`"1"` not `1`).

**Response fields per inference service:**
| Field | Description |
|-------|-------------|
| inferenceId | Inference service ID |
| inferenceName | Inference service name (model identifier) |
| inferenceTotalRequests | Total request count |
| inferenceSuccessRequests | Successful requests |
| inferenceFailedRequests | Failed requests |
| inferenceFailedRatio | Failure rate (0.0–1.0) |
| inferenceTotalTokenNum | Total tokens consumed |
| inferenceInputTokenNum | Input (prompt) tokens |
| inferenceOutputTokenNum | Output (completion) tokens |
| inferenceTimeToFirstToken | Avg time-to-first-token (ms) |
| inferenceTimePerOutToken | Avg time per output token (ms) |

## Workflow

### Step 1: Get all API Key IDs

```bash
NO_PROXY="10.26.15.52,10.0.0.0/8" curl -s -k \
  'https://10.26.15.52/ai/api/v1/serving/apikeys?clusterId=fleet-local/local' \
  -u rootRedfish:Machine@123
```

Extract all `id` values from `data.result[]`. Convert to string array for the next step.

### Step 2: Query usage for each day

To get daily breakdowns, query each day individually by iterating over single-day windows. The monitoring endpoint returns data grouped by inference service (model), not by day — daily breakdown requires separate queries per day.

### Step 3: Present results

Format as a daily table with totals, per-model breakdown, average daily load, and peak day identification.

## Complete One-Shot Script

Save this Python script and run with `NO_PROXY="10.26.15.52,10.0.0.0/8" python3 huawei_usage.py [DAYS]`:

```python
#!/usr/bin/env python3
"""Query Huawei AI Platform model usage for the last N days."""
import json, urllib.request, urllib.error, base64, datetime, sys, os, ssl

os.environ["NO_PROXY"] = "10.26.15.52,10.0.0.0/8"
BASE = "https://10.26.15.52"
AUTH = base64.b64encode(b"rootRedfish:Machine@123").decode()
CLUSTER = "fleet-local/local"
HEADERS_JSON = {
    "Authorization": f"Basic {AUTH}",
    "Content-Type": "application/json",
}
HEADERS_GET = {
    "Authorization": f"Basic {AUTH}",
}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HTTPS_HANDLER = urllib.request.HTTPSHandler(context=CTX)

def api_get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers=HEADERS_GET)
    opener = urllib.request.build_opener(HTTPS_HANDLER)
    try:
        with opener.open(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"code": e.code, "msg": f"HTTP {e.code}: {body[:500]}", "data": None}

def api_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=HEADERS_JSON, method="POST")
    opener = urllib.request.build_opener(HTTPS_HANDLER)
    try:
        with opener.open(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"code": e.code, "msg": f"HTTP {e.code}: {body[:500]}", "data": None}

def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    # Step 1: Get API key IDs
    print("Fetching API key list...")
    keys_resp = api_get("/ai/api/v1/serving/apikeys", {"clusterId": CLUSTER})
    if keys_resp.get("code") != 200 or not keys_resp.get("data"):
        print(f"Error getting API keys: code={keys_resp.get('code')}, msg={keys_resp.get('msg')}")
        print("\nTrying to query with known key IDs from the API guide: [1, 2, 3]")
        key_ids = ["1", "2", "3"]
    else:
        key_ids = [str(k["id"]) for k in keys_resp["data"]["result"]]
        key_names = {str(k["id"]): k["name"] for k in keys_resp["data"]["result"]}
        print(f"Found {len(key_ids)} API keys: {key_ids}")

    # Step 2: Query daily usage
    now = datetime.datetime.now()
    results = []
    for d in range(days):
        day = now - datetime.timedelta(days=days - 1 - d)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + datetime.timedelta(days=1)
        body = {
            "apikeyIds": key_ids,
            "startTs": int(day_start.timestamp()),
            "endTs": int(day_end.timestamp()),
            "inferenceNames": [],
            "pageSize": 100,
            "pageNum": 1,
            "clusterId": CLUSTER,
        }
        print(f"  Querying {day_start.strftime('%Y-%m-%d')}...")
        resp = api_post("/ai/api/v1/serving/apikeys/apiKeyMonitor/form", body)
        records = resp.get("data", {}).get("result", []) if resp.get("data") else []
        if resp.get("code") != 200:
            print(f"    Warning: API returned code={resp.get('code')}, msg={resp.get('msg', '')[:100]}")
        results.append({"date": day_start.strftime("%Y-%m-%d"), "records": records or []})

    # Step 3: Print daily table
    print(f"\n{'Date':<12} {'Requests':>9} {'Success':>8} {'Failed':>7} {'TotalTok':>10} {'InTok':>9} {'OutTok':>9} {'Models'}")
    print("-" * 90)
    total_req = total_ok = total_fail = total_tok = total_in = total_out = 0
    peak_day = ""
    peak_req = 0
    for r in results:
        req = sum(rec.get("inferenceTotalRequests", 0) for rec in r["records"])
        ok = sum(rec.get("inferenceSuccessRequests", 0) for rec in r["records"])
        fail = sum(rec.get("inferenceFailedRequests", 0) for rec in r["records"])
        tok = sum(rec.get("inferenceTotalTokenNum", 0) for rec in r["records"])
        itok = sum(rec.get("inferenceInputTokenNum", 0) for rec in r["records"])
        otok = sum(rec.get("inferenceOutputTokenNum", 0) for rec in r["records"])
        models = ", ".join(sorted(set(rec.get("inferenceName","?") for rec in r["records"]))[:5]) or "—"
        print(f"{r['date']:<12} {req:>9} {ok:>8} {fail:>7} {tok:>10,} {itok:>9,} {otok:>9,} {models}")
        total_req += req; total_ok += ok; total_fail += fail
        total_tok += tok; total_in += itok; total_out += otok
        if req > peak_req:
            peak_req = req; peak_day = r["date"]

    print("-" * 90)
    print(f"{'TOTAL':<12} {total_req:>9} {total_ok:>8} {total_fail:>7} {total_tok:>10,} {total_in:>9,} {total_out:>9,}")
    print(f"\nAvg daily requests: {total_req/days:.1f}  |  Avg daily tokens: {total_tok/days:,.0f}")
    if peak_day:
        print(f"Peak day: {peak_day} ({peak_req} requests)")

    # Step 4: Per-model breakdown
    model_stats = {}
    for r in results:
        for rec in r["records"]:
            name = rec.get("inferenceName", "unknown")
            if name not in model_stats:
                model_stats[name] = {"req": 0, "ok": 0, "fail": 0, "tok": 0, "in": 0, "out": 0, "days_active": 0, "ttft": [], "tpot": []}
            model_stats[name]["req"] += rec.get("inferenceTotalRequests", 0)
            model_stats[name]["ok"] += rec.get("inferenceSuccessRequests", 0)
            model_stats[name]["fail"] += rec.get("inferenceFailedRequests", 0)
            model_stats[name]["tok"] += rec.get("inferenceTotalTokenNum", 0)
            model_stats[name]["in"] += rec.get("inferenceInputTokenNum", 0)
            model_stats[name]["out"] += rec.get("inferenceOutputTokenNum", 0)
            if rec.get("inferenceTotalRequests", 0) > 0:
                model_stats[name]["days_active"] += 1
                if rec.get("inferenceTimeToFirstToken"):
                    model_stats[name]["ttft"].append(rec["inferenceTimeToFirstToken"])
                if rec.get("inferenceTimePerOutToken"):
                    model_stats[name]["tpot"].append(rec["inferenceTimePerOutToken"])

    if model_stats:
        print("\n=== Per-Model Breakdown ===")
        print(f"{'Model':<20} {'Requests':>9} {'Success':>8} {'Failed':>7} {'TotalTok':>10} {'InTok':>9} {'OutTok':>9} {'DaysActive':>10} {'AvgTTFT(ms)':>11} {'AvgTPOT(ms)':>11}")
        print("-" * 115)
        for name, s in sorted(model_stats.items(), key=lambda x: -x[1]["req"]):
            avg_ttft = sum(s["ttft"])/len(s["ttft"]) if s["ttft"] else 0
            avg_tpot = sum(s["tpot"])/len(s["tpot"]) if s["tpot"] else 0
            print(f"{name:<20} {s['req']:>9} {s['ok']:>8} {s['fail']:>7} {s['tok']:>10,} {s['in']:>9,} {s['out']:>9,} {s['days_active']:>10} {avg_ttft:>11.1f} {avg_tpot:>11.1f}")
    else:
        print("\nNo model usage data found for the queried period.")

if __name__ == "__main__":
    main()
```

## Notes

- The API uses self-signed certificates — always use `-k` with curl
- `apikeyIds` values must be strings, not integers
- Timestamps are Unix seconds (UTC)
- `mine=true` / `all=true` parameters on the key list endpoint return empty results — don't use them
- If `pageSize` is too small, results may be truncated — use 100 or paginate
- Times returned by the API are UTC; convert to local timezone for display
- The monitoring endpoint returns data grouped by inference service (model), not by day — daily breakdown requires separate queries per day
