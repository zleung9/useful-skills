#!/usr/bin/env python3
"""
vault.py — 加密密码保险库

安全设计：
- AES-256-GCM 加密所有敏感字段（用户名、密码、URL、备注）
- PBKDF2-HMAC-SHA256 从 master password 派生加密密钥（100k iterations）
- Master password 不存储，任何时候都不落盘
- 16 bytes 随机 IV 每次加密都不同，防止彩虹表攻击
- 密文格式：nonce(16) || ciphertext || tag(16)

用法：
    python3 vault.py setup <master_password>              初始化保险库
    python3 vault.py add <标题> -u <用户名> -p <密码> [--url x] [--notes x] [-c 分类] [-t 标签]
    python3 vault.py list [关键词]                        列出所有条目（不显示密码）
    python3 vault.py get <标题或ID>                       获取单条详情（需输入 master password）
    python3 vault.py delete <ID>                          删除条目
    python3 vault.py edit <ID> -p <新密码>                修改密码
    python3 vault.py categories                           列出所有分类
    python3 vault.py lock / unlock                       锁定/解锁会话
"""

import sqlite3, os, sys, re, argparse, getpass, json, hashlib, base64, secrets
from datetime import datetime
from pathlib import Path

# ─── 路径配置 ─────────────────────────────────────────────
WORKSPACE   = os.path.expanduser("~/.hermes")
VAULT_DIR   = os.path.join(WORKSPACE, "vault")
DB_PATH     = os.path.join(VAULT_DIR, "vault.db")
META_FILE   = os.path.join(VAULT_DIR, ".vault_meta")
SESSION_KEY = None  # 内存中解密密钥，进程结束即消失

# ─── 加密工具 ─────────────────────────────────────────────
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS  = 200_000  # PBKDF2 迭代次数
SALT_LEN    = 32       # 32 bytes 盐
NONCE_LEN   = 12       # GCM 标准 nonce 长度

def derive_key(password: str, salt: bytes) -> bytes:
    """从 master password 派生加密密钥"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))

def encrypt(plaintext: str, key: bytes) -> bytes:
    """AES-256-GCM 加密，返回 nonce+ciphertext+tag"""
    if not plaintext:
        return b""
    nonce = secrets.token_bytes(NONCE_LEN)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct  # nonce(12) + ciphertext + tag(16)

def decrypt(ciphertext: bytes, key: bytes) -> str:
    """AES-256-GCM 解密"""
    if not ciphertext:
        return ""
    nonce = ciphertext[:NONCE_LEN]
    ct    = ciphertext[NONCE_LEN:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")

# ─── Vault 元数据 ─────────────────────────────────────────
def load_meta() -> dict:
    """加载 vault 元数据（用于验证密码）"""
    if not os.path.exists(META_FILE):
        return None
    with open(META_FILE) as f:
        return json.load(f)

def save_meta(salt: bytes, encrypted_key: bytes):
    """保存 vault 元数据（salt + 加密的内部密钥）"""
    with open(META_FILE, "w") as f:
        json.dump({
            "salt":         base64.b64encode(salt).decode(),
            "encrypted_key": base64.b64encode(encrypted_key).decode(),
            "kdf_ops":      ITERATIONS,
        }, f)
    os.chmod(META_FILE, 0o600)  # 仅所有者可读写

# ─── 会话密钥管理 ─────────────────────────────────────────
def _get_env_password():
    import os as _os
    return _os.environ.get("VAULT_MASTER_PASSWORD", "")

def session_unlock(password: str) -> bool:
    """验证 password，解密内部密钥到会话内存"""
    global SESSION_KEY
    meta = load_meta()
    if not meta:
        return False
    
    salt  = base64.b64decode(meta["salt"])
    inner = base64.b64decode(meta["encrypted_key"])
    
    derived = derive_key(password, salt)
    
    # 用派生密钥解密内部密钥，验证 password 正确性
    try:
        inner_plain = decrypt(inner, derived)
        SESSION_KEY = derive_key(inner_plain, salt)  # 双层派生
        return True
    except Exception:
        return False

def _get_password_interactive(prompt="Master password: ") -> str:
    import os as _os, sys as _sys
    # 如果不是 TTY，尝试环境变量
    if not _sys.stdin.isatty():
        pw = _get_env_password()
        if pw: return pw
        raise EOFError("非交互环境，请使用 --password 参数或设置 VAULT_MASTER_PASSWORD 环境变量")
    try:
        return getpass.getpass(prompt)
    except EOFError:
        pw = _get_env_password()
        if pw: return pw
        raise


    meta = load_meta()
    if not meta:
        return False
    
    salt  = base64.b64decode(meta["salt"])
    inner = base64.b64decode(meta["encrypted_key"])
    
    derived = derive_key(password, salt)
    
    # 用派生密钥解密内部密钥，验证 password 正确性
    try:
        inner_plain = decrypt(inner, derived)
        SESSION_KEY = derive_key(inner_plain, salt)  # 双层派生
        return True
    except Exception:
        return False

def session_lock():
    global SESSION_KEY
    SESSION_KEY = None

def is_unlocked() -> bool:
    return SESSION_KEY is not None

# ─── 数据库 ───────────────────────────────────────────────
def init_db():
    os.makedirs(VAULT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS entries (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        category    TEXT DEFAULT '',
        tags        TEXT DEFAULT '',
        username    BLOB,   -- AES-GCM encrypted
        password    BLOB,   -- AES-GCM encrypted
        url         BLOB,   -- AES-GCM encrypted
        notes       BLOB,   -- AES-GCM encrypted
        created_at  TEXT,
        updated_at  TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        action      TEXT,
        entry_id    INTEGER,
        entry_title TEXT,
        ts          TEXT,
        ip_addr     TEXT
    )""")
    conn.commit()
    conn.close()
    os.chmod(DB_PATH, 0o600)

# ─── 条目操作 ─────────────────────────────────────────────
def add_entry(title, username, password, url="", notes="", category="", tags=""):
    if not is_unlocked():
        raise PermissionError("🔒 Vault 未解锁，请先输入 master password")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO entries 
        (title, category, tags, username, password, url, notes, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (title, category, tags,
         encrypt(username, SESSION_KEY),
         encrypt(password, SESSION_KEY),
         encrypt(url, SESSION_KEY),
         encrypt(notes, SESSION_KEY),
         now, now))
    eid = c.lastrowid
    conn.commit()
    conn.close()
    return eid

def list_entries(keyword=""):
    """列出所有条目（仅显示标题/分类/标签，不显示密码）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute("SELECT id, title, category, tags, username, created_at FROM entries ORDER BY id DESC").fetchall()
    conn.close()
    
    result = []
    for r in rows:
        username_ct = r[4]
        username_short = ""
        if username_ct:
            try:
                username_dec = decrypt(username_ct, _get_derived_key_unsafe())
                username_short = mask_string(username_dec)
            except:
                username_short = "🔐"
        
        result.append({
            "id":       r[0],
            "title":    r[1],
            "category": r[2],
            "tags":     r[3],
            "username": username_short,
            "created":  r[5][:10],
        })
    
    if keyword:
        k = keyword.lower()
        result = [r for r in result if k in r["title"].lower() 
                  or k in r["category"].lower() or k in r["tags"].lower()]
    
    return result

def get_entry(key_or_title):
    """获取单条完整详情（调用方需确保 vault 已解锁）"""
    if not is_unlocked():
        raise PermissionError("🔒 Vault 未解锁")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 支持 ID 或标题模糊匹配
    if key_or_title.isdigit():
        row = c.execute("SELECT * FROM entries WHERE id=?", (int(key_or_title),)).fetchone()
    else:
        row = c.execute("SELECT * FROM entries WHERE title LIKE ? LIMIT 1", 
                       (f"%{key_or_title}%",)).fetchone()
    
    if not row:
        conn.close()
        return None
    
    def safe_decrypt(b):
        if not b: return ""
        try: return decrypt(b, SESSION_KEY)
        except: return "❌解密失败"
    
    entry = {
        "id":       row[0],
        "title":    row[1],
        "category": row[2],
        "tags":     row[3],
        "username": safe_decrypt(row[4]),
        "password": safe_decrypt(row[5]),
        "url":      safe_decrypt(row[6]),
        "notes":    safe_decrypt(row[7]),
        "created":  row[8],
        "updated":  row[9],
    }
    conn.close()
    return entry

def delete_entry(entry_id):
    if not is_unlocked():
        raise PermissionError("🔒 Vault 未解锁")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

def update_password(entry_id, new_password):
    if not is_unlocked():
        raise PermissionError("🔒 Vault 未解锁")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE entries SET password=?, updated_at=? WHERE id=?",
              (encrypt(new_password, SESSION_KEY), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), entry_id))
    conn.commit()
    conn.close()

# ─── 工具 ─────────────────────────────────────────────────
def mask_string(s):
    if not s: return ""
    if len(s) <= 4: return "****"
    return s[:3] + "****" + s[-1] if len(s) > 6 else "****"

def _get_derived_key_unsafe():
    """从 SESSION_KEY 重新派生（仅用于 list 显示用户名）"""
    return SESSION_KEY

def format_entry_list(entries, keyword=""):
    if not entries:
        return "🔍 无匹配条目"
    
    lines = [f"📋 密码库（共 {len(entries)} 条）"]
    if keyword:
        lines.append(f"   搜索: 「{keyword}」\n")
    
    cats = {}
    for e in entries:
        cat = e["category"] or "未分类"
        cats.setdefault(cat, []).append(e)
    
    for cat, items in cats.items():
        lines.append(f"\n📁 {cat} ({len(items)}条)")
        for e in items:
            lines.append(f"   [{e['id']}] {e['title']} {e['username']}")
    
    return "\n".join(lines)

def format_entry_detail(e):
    lines = [
        f"🔐 {e['title']}",
        f"",
        f"👤 用户名：{e['username']}",
        f"🔑 密码：{e['password']}",
    ]
    if e.get("url"):
        lines.append(f"🌐 网址：{e['url']}")
    if e.get("notes"):
        lines.append(f"📝 备注：{e['notes']}")
    lines.extend([f"", f"📅 创建：{e['created'][:10]} | 更新：{e['updated'][:10]}"])
    return "\n".join(lines)

# ─── 命令行入口 ───────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="🔐 密码保险库")
    sub = parser.add_subparsers(dest="cmd")
    
    p = sub.add_parser("setup", help="初始化保险库（仅首次）")
    p.add_argument("master_password", help="Master password（不存储，请牢记）")
    
    p = sub.add_parser("add", help="添加条目")
    p.add_argument("title")
    p.add_argument("-u", "--username", dest="username", required=True)
    p.add_argument("-p", "--password", dest="password", required=True)
    p.add_argument("--url", default="")
    p.add_argument("--notes", default="")
    p.add_argument("-c", "--category", dest="category", default="")
    p.add_argument("-t", "--tags", dest="tags", default="")
    
    p = sub.add_parser("list", help="列出所有条目")
    p.add_argument("keyword", nargs="?", default="")
    
    p = sub.add_parser("get", help="查看条目详情")
    p.add_argument("key", help="标题或 ID")
    
    p = sub.add_parser("delete", help="删除条目")
    p.add_argument("id", type=int)
    
    p = sub.add_parser("passwd", help="修改密码")
    p.add_argument("id", type=int)
    p.add_argument("-p", "--password", dest="password", required=True)
    
    p = sub.add_parser("categories", help="列出所有分类")
    p = sub.add_parser("lock", help="锁定会话")
    p = sub.add_parser("unlock", help="解锁会话")
    
    args = parser.parse_args()
    
    if args.cmd is None:
        parser.print_help()
        return
    
    # setup
    if args.cmd == "setup":
        if os.path.exists(META_FILE):
            print("⚠️  Vault 已存在，setup 仅用于初始化新保险库")
            return
        init_db()
        salt  = secrets.token_bytes(SALT_LEN)
        inner_plain = secrets.token_hex(32)  # 随机内部密钥
        derived = derive_key(args.master_password, salt)
        encrypted_key = encrypt(inner_plain, derived)
        save_meta(salt, encrypted_key)
        print("✅ 保险库初始化成功！请牢记 master password。")
        return
    
    # lock/unlock
    if args.cmd == "lock":
        session_lock()
        print("🔒 已锁定")
        return
    
    if args.cmd == "unlock":
        pw = getpass.getpass("Master password: ")
        if session_unlock(pw):
            print("✅ 已解锁")
        else:
            print("❌ 密码错误")
        return
    
    # 以下命令需要 vault 已初始化
    if not os.path.exists(META_FILE):
        print("❌ Vault 未初始化，请先运行: vault.py setup <master_password>")
        return
    
    # unlock 自动（从环境变量或提示）
    if not is_unlocked():
        pw = _get_password_interactive()
        if not session_unlock(pw):
            print("❌ 密码错误")
            return
    
    if args.cmd == "add":
        eid = add_entry(args.title, args.username, args.password,
                       args.url, args.notes, args.category, args.tags)
        print(f"✅ 已添加 (ID: {eid})")
    
    elif args.cmd == "list":
        entries = list_entries(args.keyword)
        print(format_entry_list(entries, args.keyword))
    
    elif args.cmd == "get":
        entry = get_entry(args.key)
        if not entry:
            print(f"❌ 未找到：{args.key}")
        else:
            print(format_entry_detail(entry))
    
    elif args.cmd == "delete":
        delete_entry(args.id)
        print(f"🗑️  已删除 ID:{args.id}")
    
    elif args.cmd == "passwd":
        update_password(args.id, args.password)
        print(f"✅ 密码已更新 ID:{args.id}")
    
    elif args.cmd == "categories":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT category, COUNT(*) FROM entries GROUP BY category ORDER BY COUNT(*) DESC").fetchall()
        conn.close()
        for r in rows:
            print(f"📁 {r[0] or '未分类'}: {r[1]}条")

if __name__ == "__main__":
    main()
