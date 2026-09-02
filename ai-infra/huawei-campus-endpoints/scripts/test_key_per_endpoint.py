#!/usr/bin/env python3
"""Test an API key against ALL Huawei campus endpoints individually.

Key insight: a key can work on some hash endpoints but not others
(e.g. 2026-06-02: old key works on 4/5, GLM-5 hash returns 401).
Testing just one endpoint is NOT sufficient.

Usage:
  python3 test_key_per_endpoint.py [API_KEY]

If API_KEY is omitted, reads from ~/.hermes/config.yaml (model.default.api_key).
"""
import sys, json, urllib.request, os, re

ENDPOINTS = [
    ("GLM-5",              "7f82733149be43a1b8f26196b2202fa6", "glm-5"),
    ("DeepSeek-V4",        "132bc0947fc64cc79e22618a60394789", "DeepSeek-V4-Flash-w8a8-mtp"),
    ("Qwen3.6-128K",       "f6f71ef40c934f75920fb8decd6db721", "Qwen3.6-35B-A3B"),
    ("Qwen3.6-std",        "ccb44b4cfe18439f8affd07babd0810e", "Qwen3.6-35B-A3B"),
    ("Intern-S2",          "784fa5165cd6424fa19764c8c6b95274", "intern-s2-preview"),
]

def get_key_from_config():
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    with open(config_path) as f:
        text = f.read()
    # Try custom_providers first
    m = re.search(r'api_key:\s*(sk-\S+)', text)
    return m.group(1) if m else None

def test_endpoint(name, hash_prefix, model, key):
    url = f"http://10.26.15.52:30081/{hash_prefix}/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Say hi"}],
        "max_tokens": 16
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:60]
            return "OK", content
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:120]
        return f"HTTP {e.code}", err
    except Exception as e:
        return "ERROR", str(e)[:120]

if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else get_key_from_config()
    if not key:
        print("ERROR: No API key provided and could not read from config.yaml")
        sys.exit(1)
    
    key_display = key[:8] + "..." + key[-4:] if len(key) > 12 else key
    print(f"Testing key: {key_display}\n")
    print(f"{'Model':<20} {'Hash':<8} {'Status':<12} {'Detail'}")
    print("-" * 80)
    
    ok_count = 0
    for name, hash_prefix, model in ENDPOINTS:
        status, detail = test_endpoint(name, hash_prefix, model, key)
        hash_short = hash_prefix[:8]
        print(f"{name:<20} {hash_short:<8} {status:<12} {detail}")
        if status == "OK":
            ok_count += 1
    
    print(f"\nResult: {ok_count}/{len(ENDPOINTS)} endpoints OK")
    if ok_count < len(ENDPOINTS):
        print("⚠️  Some endpoints failed — key may not work uniformly across all hashes.")
