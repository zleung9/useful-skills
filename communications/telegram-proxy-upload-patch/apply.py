#!/usr/bin/env python3
"""Re-apply the buffered-upload patch to the telegram MCP plugin's server.ts.

Root cause being patched:
    Bun fetch + HTTPS_PROXY + ReadableStream request body → ECONNRESET mid-upload.
    grammY's sendPhoto / sendDocument stream multipart bodies, so they fail
    whenever the host is behind an HTTP proxy (Clash etc.). sendMessage is
    unaffected because its body is a small JSON blob.

Fix:
    Bypass grammY for those two methods. Read the file into memory, wrap in a
    Blob, POST via raw fetch — the full Content-Length lets the proxy pass the
    request through without resetting.

This script is idempotent: if the patch is already present it exits 0 with a
note. It targets every version directory under
    ~/.claude/plugins/cache/claude-plugins-official/telegram/*/server.ts
so you can run it right after a plugin upgrade overwrites the cache.

Usage:
    python3 apply.py              # patch every version dir it finds
    python3 apply.py --check      # report status only, don't modify
    python3 apply.py --dir PATH   # patch a specific version dir
"""
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys
from glob import glob
from pathlib import Path

HELPER_MARKER = "async function sendFileBuffered("

HELPER_SRC = """\

// Bun fetch + HTTPS_PROXY + streaming request body → ECONNRESET during upload.
// grammY's sendPhoto/sendDocument sends multipart as a ReadableStream, which
// the proxy (Clash, etc.) can't pass through reliably. Pre-buffer the file and
// POST with a Blob so the body has a known Content-Length and goes in one shot.
async function sendFileBuffered(
  method: 'sendPhoto' | 'sendDocument',
  chat_id: string,
  filePath: string,
  reply_to?: number,
): Promise<{ message_id: number }> {
  const buf = readFileSync(filePath)
  const form = new FormData()
  form.append('chat_id', chat_id)
  if (reply_to != null) {
    form.append('reply_parameters', JSON.stringify({ message_id: reply_to }))
  }
  const field = method === 'sendPhoto' ? 'photo' : 'document'
  const filename = filePath.split(sep).pop() ?? 'file'
  form.append(field, new Blob([buf]), filename)
  const res = await fetch(`https://api.telegram.org/bot${TOKEN}/${method}`, {
    method: 'POST',
    body: form,
  })
  const data = await res.json() as { ok: boolean; result?: { message_id: number }; description?: string }
  if (!data.ok || !data.result) {
    throw new Error(`${method} failed: HTTP ${res.status} ${data.description ?? ''}`)
  }
  return { message_id: data.result.message_id }
}
"""

# Anchor just after `const bot = new Bot(TOKEN)` / `let botUsername = ''`.
# We insert the helper immediately after the bot init so it can see TOKEN.
ANCHOR_RE = re.compile(
    r"(const bot = new Bot\(TOKEN\)\s*\nlet botUsername = ''\s*\n)",
)

# The original upload block we replace. Matched loosely to survive whitespace
# drift. We anchor on `for (const f of files)` that constructs InputFile.
UPLOAD_BLOCK_RE = re.compile(
    r"""        // Files go as separate messages[^\n]*\n
        // sendMessage call\)\. Thread under reply_to if present\.\n
        for \(const f of files\) \{\n
\s*const ext = extname\(f\)\.toLowerCase\(\)\n
\s*const input = new InputFile\(f\)\n
\s*const opts = reply_to != null && replyMode !== 'off'\n
\s*\? \{ reply_parameters: \{ message_id: reply_to \} \}\n
\s*: undefined\n
\s*if \(PHOTO_EXTS\.has\(ext\)\) \{\n
\s*const sent = await bot\.api\.sendPhoto\(chat_id, input, opts\)\n
\s*sentIds\.push\(sent\.message_id\)\n
\s*\} else \{\n
\s*const sent = await bot\.api\.sendDocument\(chat_id, input, opts\)\n
\s*sentIds\.push\(sent\.message_id\)\n
\s*\}\n
\s*\}\n""",
    re.VERBOSE,
)

UPLOAD_BLOCK_NEW = """\
        // Files go as separate messages (Telegram doesn't mix text+file in one
        // sendMessage call). Thread under reply_to if present.
        // Uploads bypass grammY — see sendFileBuffered (proxy+stream ECONNRESET).
        for (const f of files) {
          const ext = extname(f).toLowerCase()
          const threadTo = reply_to != null && replyMode !== 'off' ? reply_to : undefined
          const method = PHOTO_EXTS.has(ext) ? 'sendPhoto' : 'sendDocument'
          const sent = await sendFileBuffered(method, chat_id, f, threadTo)
          sentIds.push(sent.message_id)
        }
"""


def find_plugin_dirs(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser().resolve()]
    pattern = os.path.expanduser(
        "~/.claude/plugins/cache/claude-plugins-official/telegram/*/server.ts"
    )
    return sorted({Path(p).parent for p in glob(pattern)})


def patch_one(dir_path: Path, check_only: bool) -> str:
    server = dir_path / "server.ts"
    if not server.is_file():
        return f"[skip] {dir_path}: no server.ts"
    src = server.read_text()

    if HELPER_MARKER in src:
        return f"[ok] {dir_path}: already patched"

    if not ANCHOR_RE.search(src):
        return (
            f"[fail] {dir_path}: anchor `const bot = new Bot(TOKEN)` not found — "
            "plugin source has drifted, patch manually"
        )
    if not UPLOAD_BLOCK_RE.search(src):
        return (
            f"[fail] {dir_path}: upload-loop block not found — "
            "plugin source has drifted, patch manually"
        )

    if check_only:
        return f"[would-patch] {dir_path}"

    new_src = ANCHOR_RE.sub(r"\1" + HELPER_SRC, src, count=1)
    new_src = UPLOAD_BLOCK_RE.sub(UPLOAD_BLOCK_NEW, new_src, count=1)

    backup = server.with_suffix(".ts.prepatch")
    if not backup.exists():
        backup.write_text(src)
    server.write_text(new_src)

    # Syntax check with bun if available. We only warn — the write already
    # happened, and the user can inspect backup if build fails.
    bun = _which("bun")
    if bun:
        r = subprocess.run(
            [bun, "build", "--target=bun", str(server), "--outfile=/dev/null"],
            capture_output=True,
            text=True,
            cwd=str(dir_path),
        )
        if r.returncode != 0:
            return (
                f"[warn] {dir_path}: patched, but bun build failed:\n"
                f"{r.stderr.strip()[:400]}\n"
                f"backup at {backup}"
            )
    return f"[patched] {dir_path}"


def _which(prog: str) -> str | None:
    for p in os.environ.get("PATH", "").split(":"):
        cand = os.path.join(p, prog)
        if os.access(cand, os.X_OK):
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="don't modify, just report")
    ap.add_argument("--dir", help="patch only this version directory")
    args = ap.parse_args()

    dirs = find_plugin_dirs(args.dir)
    if not dirs:
        print("no telegram plugin versions found under ~/.claude/plugins/cache/", file=sys.stderr)
        return 1

    any_fail = False
    for d in dirs:
        line = patch_one(d, args.check)
        print(line)
        if line.startswith("[fail]"):
            any_fail = True

    print()
    print("After patching, restart the MCP server for changes to take effect:")
    print("  — restart the Claude Code session, or")
    print("  — kill the `bun run ... telegram` process and let the host respawn it.")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
