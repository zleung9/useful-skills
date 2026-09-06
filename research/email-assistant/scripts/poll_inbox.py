#!/usr/bin/env python3
"""poll_inbox.py — watch the 163 IMAP inbox for new mail and hand each new
message to the pi agent (/skill:email-assistant), which processes it as a
request and replies by email.

Invoked every minute by cron via run_job (see ~/.local/cron/run-0100.sh).
Exits in ~1-2s when there is nothing new.

State:    ~/.local/cron/inbox/state.json   (keyed by Message-ID)
Archive:  ~/Nutstore Files/pi-mail-archive/YYYY-MM/<date>-<mid8>-<subject>/
          each processed email gets its own directory containing
          original.eml + attachments/ + meta.json (poller writes these);
          the agent adds reply.html + result.txt

Skip rules:
  - Messages carrying `X-Source: pi-*` are our own outgoing mail (daily
    digests sent to ourselves) — never reprocess them.
  - A Message-ID already done/failed/in_progress is not reprocessed.
  - A message is retried at most MAX_RETRIES times on failure.
"""
import email
import email.policy
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parseaddr

sys.path.insert(0, os.path.expanduser("~/.pi/agent/skills/email/scripts"))
from msmtp_lib import get_imap  # noqa: E402

ACCOUNT = os.environ.get("INBOX_ACCOUNT", "163")
BASE = os.path.expanduser(os.environ.get("INBOX_STATE_DIR", "~/.local/cron/inbox"))
STATE_FILE = os.path.join(BASE, "state.json")
ARCHIVE_ROOT = os.path.expanduser(
    os.environ.get("MAIL_ARCHIVE_ROOT", "~/Nutstore Files/pi-mail-archive")
)
PI_BIN = os.environ.get("PI_BIN", "/opt/homebrew/bin/pi")
STALE_SECONDS = 30 * 60      # in_progress older than this is stale (crashed run)
MAX_RETRIES = 3
PREVIEW_CHARS = 12000
PI_TIMEOUT = 40 * 60         # per-email processing budget


def ts():
    return datetime.now().strftime("%F %T")


def log(m):
    print(f"[{ts()}] {m}", flush=True)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def decode_h(raw):
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return str(raw)


def strip_html(h):
    h = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", h)
    h = re.sub(r"(?is)<br\s*/?>", "\n", h)
    h = re.sub(r"(?is)</p>|</div>|</li>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"[ \t]+", " ", h)


def text_of(msg):
    """Readable text of a message: text/plain preferred, html stripped as fallback."""
    plain, html = [], []
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    for part in parts:
        cd = str(part.get("Content-Disposition") or "")
        if cd.startswith("attachment"):
            continue
        ct = part.get_content_type()
        try:
            if ct == "text/plain":
                plain.append(str(part.get_content()))
            elif ct == "text/html":
                html.append(str(part.get_content()))
        except Exception:
            pass
    if plain:
        return "\n".join(plain)
    if html:
        return strip_html("\n".join(html))
    return ""


def save_attachments(msg, att_dir):
    names = []
    if not msg.is_multipart():
        return names
    for i, part in enumerate(msg.walk()):
        cd = str(part.get("Content-Disposition") or "")
        is_att = cd.startswith("attachment") or (cd.startswith("inline") and part.get_filename())
        if not is_att:
            continue
        fn = decode_h(part.get_filename() or f"attach_{i}")
        fn = os.path.basename(fn) or f"attach_{i}"
        try:
            payload = part.get_payload(decode=True)
            with open(os.path.join(att_dir, fn), "wb") as f:
                f.write(payload or b"")
            names.append(fn)
        except Exception as e:
            log(f"attachment {fn!r} failed: {e}")
    return names


def slugify(subject, maxlen=40):
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", subject or "").strip("-")
    return s[:maxlen] or "email"


def main():
    os.makedirs(BASE, exist_ok=True)
    state = load_state()
    now = time.time()

    # recover stale in_progress entries (crashed/interrupted runs)
    for mid, v in list(state.items()):
        if v.get("status") == "in_progress" and now - v.get("ts", 0) > STALE_SECONDS:
            v["status"] = "failed" if v.get("tries", 0) >= MAX_RETRIES else "pending"
            log(f"recovered stale entry {mid} -> {v['status']}")
    save_state(state)

    conn, _user = get_imap(ACCOUNT)
    conn.select("INBOX")
    _t, data = conn.search(None, "UNSEEN")
    uids = data[0].split()

    todo = []
    for uid_b in uids:
        uid = uid_b.decode()
        _t, msgdata = conn.fetch(uid, "(RFC822)")
        raw = msgdata[0][1]
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        mid = (msg.get("Message-ID") or f"uid:{ACCOUNT}:{uid}").strip()
        if str(msg.get("X-Source") or "").lower().startswith("pi-"):
            continue  # our own outgoing mail delivered to ourselves
        st = state.get(mid)
        if st and st.get("status") in ("done", "failed", "in_progress"):
            continue
        todo.append((uid, raw, msg, mid, None))

    # retries: previously failed attempts keep their raw copy in the archive
    seen_mid = {t[3] for t in todo}
    for mid, st in list(state.items()):
        if st.get("status") != "pending" or mid in seen_mid:
            continue
        arch = st.get("archive") or ""
        p = os.path.join(arch, "original.eml") if arch else ""
        if not p or not os.path.exists(p):
            state[mid]["status"] = "failed"
            log(f"retry {mid}: archive missing, marking failed")
            continue
        with open(p, "rb") as f:
            raw = f.read()
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        todo.append((st.get("uid", "?"), raw, msg, mid, arch))
        log(f"retrying message-id={mid} (try {st.get('tries', 0) + 1})")
    save_state(state)

    if not todo:
        log(f"no new mail ({len(uids)} unseen in {ACCOUNT} INBOX)")
        try:
            conn.logout()
        except Exception:
            pass
        return 0

    rc = 0
    try:
      for item in todo:
        uid, raw, msg, mid = item[0], item[1], item[2], item[3]
        arch_reuse = item[4]
        sender = parseaddr(msg.get("From", ""))[1]
        reply_to = parseaddr(msg.get("Reply-To", ""))[1] or sender
        subject = decode_h(msg.get("Subject"))
        datestr = str(msg.get("Date") or "")
        body = text_of(msg)[:PREVIEW_CHARS]

        stamp = datetime.now()
        tries = state.get(mid, {}).get("tries", 0) + 1
        if arch_reuse and os.path.isdir(arch_reuse):
            arch = arch_reuse
            att_dir = os.path.join(arch, "attachments")
            atts = sorted(os.listdir(att_dir)) if os.path.isdir(att_dir) else []
            meta = {"message_id": mid, "tries": tries, "status": "in_progress",
                    "retried_at": stamp.isoformat(timespec="seconds")}
            try:
                with open(os.path.join(arch, "meta.json")) as f:
                    meta.update(json.load(f))
                meta.update({"tries": tries, "status": "in_progress"})
            except Exception:
                pass
            with open(os.path.join(arch, "meta.json"), "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
        else:
            local_id = mid.strip("<>").split("@")[0]
            mid8 = (local_id[-8:] or "nomid").replace(":", "")
            month_dir = os.path.join(ARCHIVE_ROOT, stamp.strftime("%Y-%m"))
            name = f"{stamp:%Y-%m-%d-%H%M}-{mid8}-{slugify(subject)}"
            arch = os.path.join(month_dir, name)
            n = 2
            while os.path.exists(arch):
                arch = os.path.join(month_dir, f"{name}-{n}")
                n += 1
            att_dir = os.path.join(arch, "attachments")
            os.makedirs(att_dir, exist_ok=True)
            with open(os.path.join(arch, "original.eml"), "wb") as f:
                f.write(raw)
            atts = save_attachments(msg, att_dir)
            meta = {
                "message_id": mid, "uid": uid, "from": sender,
                "to": str(msg.get("To") or ""), "subject": subject,
                "date": datestr, "archived_at": stamp.isoformat(timespec="seconds"),
                "tries": tries, "status": "in_progress",
            }
            with open(os.path.join(arch, "meta.json"), "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
        # mark read now: processing has started; retries are state-driven
        try:
            conn.uid("STORE", uid, "+FLAGS", "\\Seen")
        except Exception as e:
            log(f"warn: could not mark read uid={uid}: {e}")

        state[mid] = {
            "status": "in_progress", "ts": time.time(), "uid": uid,
            "from": sender, "subject": subject, "tries": tries,
            "archive": arch,
        }
        save_state(state)

        prompt = (
            f"/skill:email-assistant account={ACCOUNT} uid={uid} "
            f"message-id={mid} sender={sender} reply-to={reply_to} "
            f"date={datestr} subject={subject} archive={arch} "
            f"attachments={','.join(atts) if atts else 'none'}\n\n"
            f"--- body preview (truncated at {PREVIEW_CHARS} chars) ---\n"
            f"{body}\n--- end preview ---"
        )
        log(f"processing message-id={mid} from={sender} subject={subject!r} (try {tries})")
        try:
            r = subprocess.run([PI_BIN, "-p", prompt], timeout=PI_TIMEOUT)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            log(f"TIMEOUT processing {mid} after {PI_TIMEOUT // 60} min")
            ok = False
        except FileNotFoundError:
            log(f"PI_BIN not found: {PI_BIN}")
            ok = False

        state[mid]["status"] = "done" if ok else ("pending" if tries < MAX_RETRIES else "failed")
        save_state(state)
        try:
            meta["status"] = "done" if ok else "failed"
            meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
            with open(os.path.join(arch, "meta.json"), "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
        except OSError:
            pass
        log(f"finished message-id={mid} ok={ok} (status={state[mid]['status']})")
        rc = rc or (0 if ok else 1)
      return rc
    finally:
        try:
            conn.logout()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
