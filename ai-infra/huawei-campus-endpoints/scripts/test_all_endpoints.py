#!/usr/bin/env python3
"""Re-test models from 大模型校园网连接地址20250518.txt (2026-05-18 list).

GLM endpoint hash changed vs the 2026-05-14 list; others unchanged.
"""
import json
import time
import urllib.request
import urllib.error

API_KEY = "sk-bSQ...gUVS"

ENDPOINTS = [
    ("Qwen3.6-35B-A3B",            "Qwen3.6-35B-A3B",
     "http://10.26.15.52:30081/ccb44b4cfe18439f8affd07babd0810e/v1"),
    ("DeepSeek-V4-Flash-w8a8-mtp", "DeepSeek-V4-Flash-w8a8-mtp",
     "http://10.26.15.52:30081/132bc0947fc64cc79e22618a60394789/v1"),
    ("Qwen3.6-35B-A3B-64k",        "Qwen3.6-35B-A3B",
     "http://10.26.15.52:30081/f6f71ef40c934f75920fb8decd6db721/v1"),
    ("GLM-5.1-w8a8",               "glm-5",
     "http://10.26.15.52:30081/7f82733149be43a1b8f26196b2202fa6/v1"),
]

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
}]


def http(method, url, payload=None, timeout=120):
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.time() - t0
    except Exception as e:  # noqa
        return None, repr(e), time.time() - t0


def test(label, model_id, base):
    print(f"\n========== {label} ==========")
    print(f"base: {base}")

    s, b, dt = http("GET", base + "/models")
    print(f"[models] {s} {dt:.2f}s")
    try:
        real_id = json.loads(b)["data"][0]["id"]
        print(f"  real id from server: {real_id!r}  (use: {model_id!r})")
    except Exception:
        print(f"  raw: {b[:300]}")

    # chat
    s, b, dt = http("POST", base + "/chat/completions", {
        "model": model_id,
        "messages": [{"role": "user", "content": "用一句话介绍你自己。"}],
        "max_tokens": 200, "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
    })
    chat_ok = False
    if s == 200:
        try:
            content = (json.loads(b)["choices"][0]["message"].get("content") or "").strip()
            chat_ok = bool(content)
            print(f"[chat]   {s} {dt:.2f}s  ✅ -> {content[:120]}")
        except Exception as e:
            print(f"[chat]   {s} {dt:.2f}s  parse error: {e}")
    else:
        print(f"[chat]   {s} {dt:.2f}s  ❌ {b[:200]}")

    # tool call - auto
    s, b, dt = http("POST", base + "/chat/completions", {
        "model": model_id,
        "messages": [{"role": "user", "content": "请用工具查询厦门今天的天气，单位用摄氏度。"}],
        "tools": TOOLS, "tool_choice": "auto",
        "max_tokens": 2048, "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
    })
    tool_ok = False
    if s == 200:
        try:
            msg = json.loads(b)["choices"][0]["message"]
            tcs = msg.get("tool_calls") or []
            if tcs:
                fn = tcs[0]["function"]
                tool_ok = fn["name"] == "get_weather"
                print(f"[tool]   {s} {dt:.2f}s  ✅ name={fn['name']} args={fn['arguments']}")
            else:
                print(f"[tool]   {s} {dt:.2f}s  ❌ no tool_calls; content={(msg.get('content') or '')[:160]}")
        except Exception as e:
            print(f"[tool]   {s} {dt:.2f}s  parse error: {e}")
    else:
        print(f"[tool]   {s} {dt:.2f}s  ❌ {b[:200]}")

    return label, chat_ok, tool_ok


def main():
    rows = [test(*e) for e in ENDPOINTS]
    print("\n========== SUMMARY ==========")
    for name, c, t in rows:
        print(f"{name:32s}  chat {'✅' if c else '❌'}  tool {'✅' if t else '❌'}")


if __name__ == "__main__":
    main()
