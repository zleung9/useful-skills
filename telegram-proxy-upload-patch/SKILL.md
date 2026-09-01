---
name: telegram-proxy-upload-patch
description: Re-apply the buffered-upload patch to the telegram MCP plugin's server.ts after a plugin upgrade overwrites the cache. Fixes "Network request for 'sendPhoto' failed! / ECONNRESET" that happens when the host is behind an HTTP proxy (Clash etc.) — caused by Bun fetch choking on streaming multipart bodies through the proxy. Use when the user reports that telegram reply with files (photos/documents) fails while text replies still work, or says "Telegram sendPhoto 又连不上了 / reply failed sendPhoto / 升级后图又发不出去了".
---

# telegram-proxy-upload-patch

## What this patches and why

- **Symptom**: `reply failed: Network request for 'sendPhoto' failed!` (or `sendDocument`) from the `plugin:telegram:telegram` MCP. `sendMessage` (text-only) still works.
- **Underlying error**: inside grammY the thrown cause is `ECONNRESET — The socket connection was closed unexpectedly`, path `https://api.telegram.org/bot.../sendPhoto`.
- **Root cause**: Bun's `fetch` + `HTTPS_PROXY` + streaming request body is broken — the proxy resets mid-upload. grammY sends multipart bodies as a `ReadableStream` (see `grammy/out/core/payload.js` `createFormDataPayload`), so every file upload falls into the broken path. JSON calls like `sendMessage` are immune because they ship as a small buffered body.
- **The proxy itself is fine** — `api.telegram.org` is reachable, text replies go through, only streamed uploads reset.

The patch replaces the grammY upload calls with a raw `fetch` that reads the file into memory and POSTs a `FormData`/`Blob`. Known `Content-Length`, no streaming, proxy passes it through.

## When to run

Run this skill when:
- The user complains telegram file attachments (photos, documents) fail while text still sends.
- The user mentions they just upgraded the telegram plugin and uploads broke.
- A fresh Claude Code install on a machine behind Clash / any HTTP proxy starts hitting the same error.

Don't run it if:
- The user isn't behind an HTTP proxy (the patch is harmless but unnecessary).
- `sendMessage` also fails — that's a different problem (wrong token, revoked bot, network down).

## How to run

```sh
python3 ~/.claude/skills/telegram-proxy-upload-patch/apply.py
```

Flags:
- `--check` — report status without modifying anything
- `--dir PATH` — target a specific plugin version directory

The script is idempotent: it detects `sendFileBuffered(` in the source and skips already-patched versions. It writes a `server.ts.prepatch` backup the first time it patches a given version, and runs `bun build` to syntax-check after.

## After patching

The running MCP server still has the old code in memory. To pick up the patch:
1. Preferred: restart the Claude Code session.
2. Or: `pkill -TERM -f 'telegram.*server'` (Claude Code respawns it on the next tool call — not guaranteed, fall back to option 1 if the next `reply` call errors).

## If the anchor regex fails ("plugin source has drifted")

Upstream changed `server.ts` enough that the regex no longer matches. Patch by hand:

1. Open `~/.claude/plugins/cache/claude-plugins-official/telegram/<version>/server.ts`.
2. Right after `const bot = new Bot(TOKEN)` / `let botUsername = ''`, paste the `sendFileBuffered` helper from `apply.py` (the `HELPER_SRC` constant).
3. In the `reply` handler, find the `for (const f of files)` loop that calls `bot.api.sendPhoto` / `bot.api.sendDocument` and replace it with the block from `apply.py` (`UPLOAD_BLOCK_NEW`).
4. `bun build --target=bun server.ts --outfile=/dev/null` to sanity-check.
5. Restart MCP server as above.

Both snippets depend on `readFileSync` (already imported) and `sep` from `'path'` (already imported) — no new imports needed.

## Upstream reporting

Worth filing on grammY: in Bun + HTTP proxy environments, `createFormDataPayload`'s `ReadableStream` body should be buffered. Could be opt-in via an env flag or auto-detected when `HTTPS_PROXY` is set. Mention this is not a grammY protocol issue — it's a Bun-fetch + HTTP-proxy streaming-body interaction — so the fix is a workaround, not a correctness fix.
