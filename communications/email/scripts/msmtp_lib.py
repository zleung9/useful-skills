#!/usr/bin/env python3
"""Shared helpers for the email skill.

Credentials live in ``~/.config/msmtp/config`` (one ``account`` block per
mailbox, perms 600). Reading them here keeps passwords off the command line
and out of every script that sends or reads mail. Import from here rather than
re-parsing the config yourself — the parsing has a subtlety: keys repeat across
``account`` blocks, so you must scope each key under its block rather than
keeping a flat dict (otherwise two accounts clobber each other's ``password``).

Public API:
    get_account(account)      -> (user, password)
    get_imap_host(account)    -> IMAP host string
    get_imap(account)         -> (IMAP4_SSL conn, user)  [connects + logs in]
    build_message(...)        -> MIMEMultipart, ready to send or save as draft
    find_draft_folder(conn)   -> mailbox name for drafts on this server
    send_via_msmtp(msg, recips, account) -> pipes msg to ``msmtp -a <account>``
"""
from __future__ import annotations

import subprocess
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    import imaplib
except ImportError:  # pragma: no cover
    imaplib = None

# IMAP host per account. Add new accounts here when you add them to the msmtp
# config (or rely on the smtp.->imap. fallback in get_imap_host).
IMAP_HOSTS = {
    "163": "imap.163.com",
    "xmu": "imap.xmu.edu.cn",
}

CONFIG_PATH = Path.home() / ".config" / "msmtp" / "config"


def load_accounts():
    """Parse ``~/.config/msmtp/config`` into ``{account_name: {key: value}}``.

    Blank and ``#`` comment lines are skipped.
    """
    blocks: dict[str, dict[str, str]] = {}
    cur = None
    for line in CONFIG_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("account "):
            cur = line.split()[1]
            blocks.setdefault(cur, {})
        elif cur and " " in line:
            key, value = line.split(None, 1)
            blocks[cur][key] = value
    return blocks


def get_account(account="163"):
    """Return ``(user, password)`` for the named msmtp account."""
    info = load_accounts().get(account)
    if not info or "password" not in info:
        raise RuntimeError(
            f"account {account!r} not found in {CONFIG_PATH}. "
            "Add an `account <name>` block with a `password` line."
        )
    return info.get("user"), info["password"]


def get_imap_host(account="163"):
    """Return the IMAP host for an account."""
    if account in IMAP_HOSTS:
        return IMAP_HOSTS[account]
    # Fallback: smtp.x.edu.cn -> imap.x.edu.cn (works for 163/xmu-style hosts).
    smtp = load_accounts().get(account, {}).get("host", "")
    if smtp.startswith("smtp."):
        return "imap." + smtp[len("smtp."):]
    raise RuntimeError(
        f"unknown IMAP host for account {account!r}; add it to IMAP_HOSTS in "
        f"{__file__}"
    )


def get_imap(account="163"):
    """Connect + log in to IMAP for an account. Returns ``(conn, user)``.

    After login, identifies the client via the IMAP ``ID`` command (RFC 2971).
    NetEase (163/126) requires this — otherwise ``SELECT`` is rejected with
    ``Unsafe Login``. Servers without ID support (e.g. xmu) simply answer
    BAD/NO, which is ignored.
    """
    if imaplib is None:  # pragma: no cover
        raise RuntimeError("imaplib unavailable in this environment")
    user, password = get_account(account)
    conn = imaplib.IMAP4_SSL(get_imap_host(account), 993)
    conn.login(user, password)
    try:
        tag = conn._new_tag()
        conn.send(tag + b' ID ("name" "pi-mail" "version" "1.0" '
                    b'"vendor" "pi-agent" "contact" "' + user.encode() + b'")\r\n')
        conn._get_response()
    except Exception:
        pass  # non-NetEase servers: ID unsupported, continue without it
    return conn, user


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def build_message(from_addr, to, subject, body, cc=None, bcc=None,
                  html=True, attachments=None, bcc_header=False, extra_headers=None):
    """Build a MIME message ready to send or append to Drafts.

    ``to``/``cc``/``bcc`` may be a string or a list of strings. ``body`` is the
    mail body; ``html=False`` makes it plain text. ``attachments`` is a list of
    file paths. ``bcc_header=True`` adds a ``Bcc:`` header (use for drafts, so
    the composer shows blind recipients); for sending, leave it False and pass
    the full recipient list to :func:`send_via_msmtp` so BCC stays blind.
    """
    msg = MIMEMultipart("mixed")
    msg["From"] = from_addr
    msg["To"] = ", ".join(_as_list(to))
    if cc:
        msg["Cc"] = ", ".join(_as_list(cc))
    if bcc and bcc_header:
        msg["Bcc"] = ", ".join(_as_list(bcc))
    msg["Subject"] = subject
    for h in _as_list(extra_headers):
        name, _, value = h.partition(":")
        if name.strip():
            msg[name.strip()] = value.strip()

    msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))

    for path in _as_list(attachments):
        p = Path(path)
        part = MIMEBase("application", "octet-stream")
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg.attach(part)
    return msg


def find_draft_folder(conn):
    """Find the Drafts mailbox on a connected IMAP server.

    Servers name this folder inconsistently (``Drafts``, ``草稿箱``,
    ``INBOX.Drafts``, ...), so try LIST first, then a list of common names.
    """
    typ, folders = conn.list()
    if typ == "OK":
        for f in folders:
            decoded = f.decode() if isinstance(f, bytes) else f
            if "Draft" in decoded or "草稿" in decoded:
                parts = decoded.split(' "/" ')
                if len(parts) == 2:
                    return parts[1].strip('"')
    for name in ["Drafts", "草稿箱", "INBOX.Drafts", "Draft"]:
        typ, _ = conn.select(name)
        if typ == "OK":
            return name
    return "Drafts"


def send_via_msmtp(msg, recipients, account="163"):
    """Send a built message via ``msmtp -a <account>``.

    ``recipients`` is the full envelope recipient list (To + Cc + Bcc). The
    message bytes are passed on stdin; binary attachments survive intact.
    Raises ``RuntimeError`` with msmtp's stderr if delivery fails.
    """
    recips = recipients if isinstance(recipients, list) else [recipients]
    result = subprocess.run(
        ["msmtp", "-a", account, *recips],
        input=msg.as_bytes(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"msmtp failed (exit {result.returncode}):\n"
            f"{result.stderr.decode(errors='replace')}"
        )
    return result.stdout
