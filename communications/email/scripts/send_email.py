#!/usr/bin/env python3
"""Send an email via msmtp (optionally with attachments).

By default the email skill saves a DRAFT first and sends only after the user
confirms. Send directly only when the user explicitly says to ("直接发").

Body defaults to HTML; use --text for plain text. Recipients, CC, BCC, and
attachments all accept repeated flags.

Usage:
    python scripts/send_email.py --to a@x.com --subject Hi --body-file body.html
    echo "<p>hi</p>" | python scripts/send_email.py --to a@x.com --subject Hi
    python scripts/send_email.py --to a@x.com --to b@y.com --cc c@z.com \
        --subject Report --body "<p>see attached</p>" --attach report.pdf
    python scripts/send_email.py --to a@x.com --subject Hi --body-file b.html --dry-run
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from msmtp_lib import get_account, build_message, send_via_msmtp


def main():
    ap = argparse.ArgumentParser(description="Send email via msmtp.")
    ap.add_argument("--account", default="163", help="msmtp account name (default 163)")
    ap.add_argument("--from", dest="from_addr",
                    help="override From (must match the account or 163 rejects with 553)")
    ap.add_argument("--to", action="append", required=True)
    ap.add_argument("--cc", action="append")
    ap.add_argument("--bcc", action="append")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", help="mail body (default HTML). If omitted, read stdin.")
    ap.add_argument("--body-file", help="read body from this file")
    ap.add_argument("--text", action="store_true", help="plain-text body")
    ap.add_argument("--attach", action="append", help="file to attach (repeatable)")
    ap.add_argument("--header", action="append",
                    help="extra MIME header 'Name: value' (repeatable, e.g. 'X-Source: pi-email-assistant')")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the rendered message instead of sending")
    args = ap.parse_args()

    user, _ = get_account(args.account)
    from_addr = args.from_addr or user
    if args.from_addr and args.from_addr != user:
        print(f"WARNING: --from {args.from_addr!r} differs from account {args.account!r} "
              f"address {user!r}; 163 will reject this with error 553.",
              file=sys.stderr)

    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text()
    if body is None:
        body = sys.stdin.read()

    msg = build_message(
        from_addr=from_addr, to=args.to, cc=args.cc, bcc=args.bcc,
        subject=args.subject, body=body, html=not args.text,
        attachments=args.attach, bcc_header=False, extra_headers=args.header,
    )

    if args.dry_run:
        print(msg.as_string())
        return

    recipients = list(args.to) + list(args.cc or []) + list(args.bcc or [])
    send_via_msmtp(msg, recipients, account=args.account)
    print(f"Sent via msmtp (account={args.account}) from {from_addr} to {', '.join(args.to)}")


if __name__ == "__main__":
    main()
