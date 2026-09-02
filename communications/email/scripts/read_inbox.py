#!/usr/bin/env python3
"""List recent inbox messages, or read one message in full.

Usage:
    python scripts/read_inbox.py                       # list last 20
    python scripts/read_inbox.py --limit 50            # list last 50
    python scripts/read_inbox.py --id 123              # read message #123 in full
    python scripts/read_inbox.py --id 123 --save-attachments ./att
"""
import argparse
import email
from email.header import decode_header
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from msmtp_lib import get_imap


def _decode(hdr):
    """Decode an RFC 2047 encoded header (handles =?charset?...? chunks)."""
    if hdr is None:
        return ""
    out = []
    for text, enc in decode_header(hdr):
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _body_text(msg):
    """Return (text_part, html_part) extracted from a message, or (None, None)."""
    text = html = None
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/plain" and text is None:
            cs = part.get_content_charset() or "utf-8"
            text = (part.get_payload(decode=True) or b"").decode(cs, errors="replace")
        elif ct == "text/html" and html is None:
            cs = part.get_content_charset() or "utf-8"
            html = (part.get_payload(decode=True) or b"").decode(cs, errors="replace")
    return text, html


def list_recent(conn, limit):
    typ, data = conn.search(None, "ALL")
    ids = data[0].split() if data and data[0] else []
    for mid in reversed(ids[-limit:]):
        typ, msg_data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        for part in msg_data:
            if isinstance(part, tuple):
                msg = email.message_from_bytes(part[1])
                date = (msg.get("Date") or "?")[:30]
                print(f"[{mid.decode()}] {date}  {_decode(msg['Subject'])}  "
                      f"← {_decode(msg['From'])}")


def read_one(conn, mid, save_attachments):
    typ, msg_data = conn.fetch(mid, "(RFC822)")
    raw = None
    for part in msg_data:
        if isinstance(part, tuple):
            raw = part[1]
            break
    if raw is None:
        print("Could not fetch message body.")
        return
    msg = email.message_from_bytes(raw)
    print(f"From: {_decode(msg['From'])}")
    print(f"To:  {_decode(msg.get('To'))}")
    print(f"Date: {msg.get('Date')}")
    print(f"Subject: {_decode(msg['Subject'])}")
    print("-" * 50)
    text, html = _body_text(msg)
    print(text or html or "(no readable body)")

    attachments = []
    for part in msg.walk():
        if "attachment" in (part.get("Content-Disposition", "") or ""):
            attachments.append((part.get_filename(), part.get_payload(decode=True)))
    if not attachments:
        return
    print("-" * 50)
    print("Attachments:")
    for fn, _ in attachments:
        print(f"  - {fn}")
    if save_attachments:
        Path(save_attachments).mkdir(parents=True, exist_ok=True)
        for fn, blob in attachments:
            out = Path(save_attachments) / (fn or "attachment.bin")
            out.write_bytes(blob or b"")
        print(f"Saved {len(attachments)} attachment(s) to {save_attachments}")


def main():
    ap = argparse.ArgumentParser(description="List or read inbox mail via IMAP.")
    ap.add_argument("--account", default="163", help="msmtp account name (default 163)")
    ap.add_argument("--limit", type=int, default=20, help="how many recent messages to list")
    ap.add_argument("--id", help="read a single message (sequence number) in full")
    ap.add_argument("--save-attachments", metavar="DIR",
                    help="with --id, write attachments to this directory")
    args = ap.parse_args()

    conn, _ = get_imap(args.account)
    try:
        conn.select("INBOX")
        if args.id:
            read_one(conn, args.id.encode(), args.save_attachments)
        else:
            list_recent(conn, args.limit)
    finally:
        conn.logout()


if __name__ == "__main__":
    main()
