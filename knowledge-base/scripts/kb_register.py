#!/usr/bin/env python3
"""
kb_register.py — 知识库核心注册脚本

用法：
    python3 kb_register.py --add <文件路径> --title "标题" --type wechat_article --url "来源URL" --tags "标签1,标签2"
    python3 kb_register.py --remove <filename>
    python3 kb_register.py --list
    python3 kb_register.py --search <关键词>
    python3 kb_register.py --scan-workspace
    python3 kb_register.py --scan-sessions
    python3 kb_register.py --dedup
    python3 kb_register.py --stats
"""
import sqlite3, os, sys, json, subprocess, re, argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

KB_ROOT = os.path.expanduser("~/KnowledgeBase")
DB_PATH = os.path.join(KB_ROOT, "kb.db")
ITEMS_DIR = os.path.join(KB_ROOT, "items")

# 源类型枚举
SOURCE_TYPES = {
    "wechat_article": "微信公众号文章",
    "youtube": "YouTube 视频",
    "pdf": "PDF 论文",
    "task_output": "任务输出",
    "web_page": "网页",
    "image": "图片",
    "other": "其他",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def guess_source_type(path, url="", title=""):
    """根据文件路径/URL/标题推断 source_type"""
    lower = (path + url + title).lower()
    if "weixin.qq.com" in url or "wechat" in lower:
        return "wechat_article"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if path.endswith(".pdf"):
        return "pdf"
    if "task" in lower or "output" in lower:
        return "task_output"
    if path.endswith((".html", ".htm")):
        return "web_page"
    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return "image"
    return "other"


def guess_mime(path):
    ext = os.path.splitext(path)[1].lower()
    table = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".html": "text/html",
        ".htm": "text/html",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".json": "application/json",
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
    }
    return table.get(ext, "application/octet-stream")


def is_duplicate_file(file_path):
    """检查文件是否已在 KB 中（按文件名 + 大小）"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, filename FROM kb_items WHERE filename = ?",
        (os.path.basename(file_path),),
    )
    rows = cur.fetchall()
    conn.close()
    return len(rows) > 0


def register_file(
    file_path,
    title="",
    source_type=None,
    source_url="",
    tags="",
    description="",
    overwrite=False,
):
    """
    将文件注册到知识库。
    返回 (success: bool, message: str)
    """
    if not os.path.exists(file_path):
        return False, f"文件不存在：{file_path}"

    filename = os.path.basename(file_path)
    dest_path = os.path.join(ITEMS_DIR, filename)
    file_size = os.path.getsize(file_path)

    # 目标路径检查
    if os.path.exists(dest_path):
        if not overwrite:
            return False, f"⚠️ 文件已存在，跳过：{filename}"

    conn = get_db()
    cur = conn.cursor()

    # 检查数据库是否已有同名记录
    cur.execute("SELECT id FROM kb_items WHERE filename = ?", (filename,))
    row = cur.fetchone()
    if row and not overwrite:
        conn.close()
        return False, f"⚠️ 数据库已有记录，跳过：{filename}"

    # 复制文件到 items/
    import shutil

    shutil.copy2(file_path, dest_path)

    # 推断类型
    if source_type is None:
        source_type = guess_source_type(file_path, source_url, title)

    # 标题默认用文件名
    if not title:
        title = os.path.splitext(filename)[0]

    tags_str = tags or ""
    mime = guess_mime(filename)

    if row:  # 已存在，更新
        cur.execute(
            """UPDATE kb_items SET
                title=?, source_type=?, source_url=?, collected_at=?,
                tags=?, file_size=?, mime_type=?, description=?
            WHERE filename=?""",
            (title, source_type, source_url, now_iso(),
             tags_str, file_size, mime, description, filename),
        )
        action = "更新"
    else:  # 新增
        cur.execute(
            """INSERT INTO kb_items
                (filename, title, source_type, source_url, collected_at,
                 tags, file_size, mime_type, description)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (filename, title, source_type, source_url, now_iso(),
             tags_str, file_size, mime, description),
        )
        action = "新增"

    conn.commit()
    conn.close()

    size_kb = file_size // 1024
    return True, f"✅ {action}成功：{filename} ({size_kb}KB) [{SOURCE_TYPES.get(source_type, source_type)}]"


def unregister_file(filename):
    """从知识库移除文件（删除记录，文件可选留或删）"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, filename FROM kb_items WHERE filename = ?", (filename,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, f"⚠️ 数据库中没有记录：{filename}"

    cur.execute("DELETE FROM kb_items WHERE filename = ?", (filename,))
    conn.commit()
    conn.close()

    # 可选：删除物理文件
    file_path = os.path.join(ITEMS_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    return True, f"🗑️ 已移除：{filename}"


def list_all(tag_filter="", source_type_filter="", limit=50):
    """列出知识库条目"""
    conn = get_db()
    cur = conn.cursor()

    query = "SELECT * FROM kb_items WHERE 1=1"
    params = []

    if tag_filter:
        query += " AND tags LIKE ?"
        params.append(f"%{tag_filter}%")
    if source_type_filter:
        query += " AND source_type = ?"
        params.append(source_type_filter)

    query += " ORDER BY collected_at DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def search(keyword):
    """按关键词搜索（标题 + tags + description）"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM kb_items
        WHERE title LIKE ? OR tags LIKE ? OR description LIKE ? OR source_url LIKE ?
        ORDER BY collected_at DESC""",
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats():
    """知识库统计"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM kb_items")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT source_type, COUNT(*) FROM kb_items GROUP BY source_type ORDER BY COUNT(*) DESC"
    )
    by_type = dict(cur.fetchall())

    cur.execute("SELECT SUM(file_size) FROM kb_items")
    total_size = cur.fetchone()[0] or 0

    conn.close()
    return total, by_type, total_size


def get_workspace_download_dirs():
    """获取所有 agent workspace 里的下载/收集目录"""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".openclaw", "workspace"),
        os.path.join(home, ".openclaw", "workspace-oracle"),
        os.path.join(home, ".openclaw", "workspace-research"),
        os.path.join(home, "workspace"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
    ]
    dirs = []
    for d in candidates:
        if os.path.isdir(d):
            dirs.append(d)
    return dirs


def scan_workspace_files():
    """
    扫描 workspace 里新产生的文件（PDF、图片、Markdown、HTML 等）。
    只扫描最近 N 天内修改过的文件，排除系统文件。
    """
    import time

    allowed_exts = {
        ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
        ".md", ".html", ".htm", ".txt", ".json",
        ".mp4", ".mp3", ".wav",
    }
    skip_dirs = {
        ".git", "node_modules", ".cache", "__pycache__",
        "HEARTBEAT.md", "MEMORY.md", "AGENTS.md",
    }

    found = []
    scan_dirs = get_workspace_download_dirs()
    # 只扫描最近 3 天内修改过的文件
    cutoff = time.time() - 3 * 86400

    for base_dir in scan_dirs:
        for root, dirs, files in os.walk(base_dir):
            # 跳过系统目录
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for fname in files:
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()

                if ext not in allowed_exts:
                    continue
                if os.path.getmtime(fpath) < cutoff:
                    continue
                # 跳过知识库本身
                if "KnowledgeBase" in fpath:
                    continue
                # 跳过系统文件
                if fname.startswith("."):
                    continue

                found.append(fpath)

    return found


def format_item_list(items):
    """将 KB 条目列表格式化为可读字符串"""
    if not items:
        return "  （无）"

    lines = []
    for i, item in enumerate(items, 1):
        ts = item["collected_at"][:10]
        type_emoji = {
            "wechat_article": "📄",
            "youtube": "🎬",
            "pdf": "📚",
            "task_output": "📋",
            "web_page": "🌐",
            "image": "🖼️",
            "other": "📎",
        }.get(item["source_type"], "📎")

        tags = f" [{item['tags']}]" if item["tags"] else ""
        title = item["title"] or item["filename"]
        size_kb = (item["file_size"] or 0) // 1024
        lines.append(
            f"  {type_emoji} {i}. {title}{tags}"
            f"\n      ID:{item['id']} | {ts} | {size_kb}KB | {item['source_type']}"
        )
    return "\n".join(lines)


# ── CLI 入口 ────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="知识库注册工具")
    sub = parser.add_subparsers(dest="cmd")

    # add
    p_add = sub.add_parser("add", help="添加文件到知识库")
    p_add.add_argument("file", help="文件路径")
    p_add.add_argument("--title", "-t", default="", help="标题")
    p_add.add_argument("--type", default=None, help=f"来源类型：{', '.join(SOURCE_TYPES)}")
    p_add.add_argument("--url", "-u", default="", help="来源 URL")
    p_add.add_argument("--tags", default="", help="标签，逗号分隔")
    p_add.add_argument("--desc", default="", dest="description", help="描述")

    # remove
    p_rm = sub.add_parser("remove", help="从知识库移除文件")
    p_rm.add_argument("filename", help="知识库中的文件名")

    # list
    p_ls = sub.add_parser("list", help="列出知识库条目")
    p_ls.add_argument("--tag", default="", help="按标签过滤")
    p_ls.add_argument("--type", default="", help="按来源类型过滤")
    p_ls.add_argument("--limit", type=int, default=50)

    # search
    p_srch = sub.add_parser("search", help="搜索知识库")
    p_srch.add_argument("keyword", help="搜索关键词")

    # scan
    sub.add_parser("scan", help="扫描 workspace 文件")

    # stats
    sub.add_parser("stats", help="显示统计信息")

    args = parser.parse_args()

    if args.cmd == "add":
        success, msg = register_file(
            args.file,
            title=args.title,
            source_type=args.type,
            source_url=args.url,
            tags=args.tags,
            description=args.description,
        )
        print(msg)

    elif args.cmd == "remove":
        success, msg = unregister_file(args.filename)
        print(msg)

    elif args.cmd == "list":
        items = list_all(tag_filter=args.tag, source_type_filter=args.type, limit=args.limit)
        total, by_type, total_size = stats()
        print(f"\n📦 知识库统计：共 {total} 条，{total_size//1024//1024}MB")
        for t, c in by_type.items():
            print(f"   {SOURCE_TYPES.get(t, t)}: {c} 条")
        print(f"\n{format_item_list(items)}")

    elif args.cmd == "search":
        items = search(args.keyword)
        print(f"\n🔍 搜索「{args.keyword}」共 {len(items)} 条：")
        print(format_item_list(items))

    elif args.cmd == "scan":
        files = scan_workspace_files()
        print(f"\n🔍 扫描到 {len(files)} 个最近修改的文件：")
        added = 0
        skipped = 0
        for f in files:
            ok, msg = register_file(f)
            print(f"  {msg}")
            if ok:
                added += 1
            else:
                skipped += 1
        print(f"\n📊 扫描完成：新增 {added}，跳过 {skipped}（已存在）")

    elif args.cmd == "stats":
        total, by_type, total_size = stats()
        print(f"\n📊 知识库统计")
        print(f"   总条目：{total}")
        print(f"   总大小：{total_size//1024//1024}MB")
        for t, c in by_type.items():
            print(f"   {SOURCE_TYPES.get(t, t)}: {c}")

    else:
        parser.print_help()
