#!/usr/bin/env python3
"""Save an email as a draft in the IMAP Drafts folder.

Why a draft first? Sending is irreversible — a wrong recipient or a typo'd
subject can't be unsent. Saving a draft lets the user review the real message
in their mail client before it goes out. This is the email skill's default;
only send directly when the user explicitly says to.

Body defaults to HTML; use --text for plain text. Recipients, CC, and
attachments accept repeated flags.

Usage:
    python scripts/save_draft.py --to a@x.com --subject "Hi" --body-file body.html
    echo "<p>hi</p>" | python scripts/save_draft.py --to a@x.com --subject Hi
    python scripts/save_draft.py --to a@x.com --subject Hi --attach report.pdf
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from msmtp_lib import get_account, get_imap, build_message, find_draft_folder


def main():
    ap = argparse.ArgumentParser(description="Save an email draft via IMAP.")
    ap.add_argument("--account", default="163", help="msmtp account name (default 163)")
    ap.add_argument("--to", action="append", required=True)
    ap.add_argument("--cc", action="append")
    ap.add_argument("--bcc", action="append")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", help="mail body (default HTML). If omitted, read stdin.")
    ap.add_argument("--body-file", help="read body from this file")
    ap.add_argument("--text", action="store_true", help="body is plain text, not HTML")
    ap.add_argument("--attach", action="append", help="file to attach (repeatable)")
    args = ap.parse_args()

    user, _ = get_account(args.account)
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text()
    if body is None:
        body = sys.stdin.read()

    msg = build_message(
        from_addr=user, to=args.to, cc=args.cc, bcc=args.bcc,
        subject=args.subject, body=body, html=not args.text,
        attachments=args.attach, bcc_header=True,
    )

    conn, _ = get_imap(args.account)
    try:
        folder = find_draft_folder(conn)
        conn.append(folder, "\\Draft", None, msg.as_bytes())
        print(f"Draft saved to folder: {folder}")
        print(f"From: {user}")
        print(f"To: {', '.join(args.to)}")
        if args.cc:
            print(f"Cc: {', '.join(args.cc)}")
    finally:
        conn.logout()


if __name__ == "__main__":
    main()
