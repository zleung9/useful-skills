#!/usr/bin/env python3
"""
expense.py — 报销管理系统

entry_type='trip'    = 行程头（汇总信息）
entry_type='expense' = 单笔消费记录（归属某个 trip_id）

用法：
    python3 expense.py new-trip "行程名" --dest 目的地 --start YYYY-MM-DD --end YYYY-MM-DD
    python3 expense.py add "消费名称" --trip-id xxx --amount 188.5 --category 餐饮 --date YYYY-MM-DD --receipt path [--project xxx] [--payer xxx]
    python3 expense.py list [trip_id|month:YYYY-MM|all|pending|reimbursed]
    python3 expense.py detail <trip_id>
    python3 expense.py status <id> <0-3>
    python3 expense.py report <trip_id> [--output path]
    python3 expense.py delete <id>
    python3 expense.py categories
"""

import sqlite3, os, sys, re, argparse, shutil, hashlib
from datetime import datetime, date
from pathlib import Path

# ─── 路径配置 ─────────────────────────────────────────────
WORKSPACE    = os.path.expanduser("~/.openclaw/workspace-assistant")
EXPENSE_DIR  = os.path.join(WORKSPACE, "expense")
DB_PATH      = os.path.join(EXPENSE_DIR, "expense.db")
RECEIPTS_DIR = os.path.join(EXPENSE_DIR, "receipts")

# ─── 常量 ─────────────────────────────────────────────
CATEGORIES   = ["机票", "火车", "酒店", "餐饮", "交通", "办公", "通讯", "其他"]
STATUS_MAP   = {0: "未报销", 1: "已提交", 2: "已打款", 3: "已驳回"}
STATUS_EMOJI = {0: "⬜", 1: "🟡", 2: "🟢", 3: "🔴"}
CAT_EMOJI    = {
    "机票": "✈️", "火车": "🚄", "酒店": "🏨",
    "餐饮": "🍜", "交通": "🚕", "办公": "📎",
    "通讯": "📱", "其他": "📦"
}

# ─── 数据库初始化 ─────────────────────────────────────────────
def get_db():
    os.makedirs(EXPENSE_DIR, exist_ok=True)
    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn

def _init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id             TEXT    NOT NULL,
            entry_type          TEXT    NOT NULL,
            title               TEXT    NOT NULL,
            amount              REAL    DEFAULT 0,
            currency            TEXT    DEFAULT 'CNY',
            category            TEXT    DEFAULT '',
            expense_date        TEXT    DEFAULT '',
            start_date          TEXT    DEFAULT '',
            end_date            TEXT    DEFAULT '',
            destination         TEXT    DEFAULT '',
            reimbursement_status INTEGER DEFAULT 0,
            receipt_path        TEXT    DEFAULT '',
            receipt_paths       TEXT    DEFAULT '[]',
            file_type           TEXT    DEFAULT '',
            project             TEXT    DEFAULT '',
            payer               TEXT    DEFAULT '',
            notes               TEXT    DEFAULT '',
            created_at          TEXT,
            updated_at          TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_id ON expenses(trip_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_type ON expenses(entry_type)")
    # 确保 receipt_paths 列存在（旧数据库迁移）
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN receipt_paths TEXT DEFAULT '[]'")
    except:
        pass
    conn.commit()

# ─── 工具函数 ─────────────────────────────────────────────
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today():
    return datetime.now().strftime("%Y-%m-%d")

def _copy_receipt(src_path, trip_id, dest_name=None):
    """复制附件到 receipts/{trip_id}/ 目录，返回存储路径

    如果提供 dest_name 则使用自定义文件名，否则保留原始文件名（加时间戳前缀）。
    """
    if not src_path or not os.path.exists(src_path):
        return ""
    dest_dir = os.path.join(RECEIPTS_DIR, trip_id)
    os.makedirs(dest_dir, exist_ok=True)
    if dest_name:
        fname = dest_name
    else:
        fname = os.path.basename(src_path)
        # 避免文件名冲突，加时间戳前缀
        ts = datetime.now().strftime("%H%M%S")
        fname = f"{ts}_{fname}"
    dest_path = os.path.join(dest_dir, fname)
    shutil.copy2(src_path, dest_path)
    # 返回相对路径
    return os.path.join(trip_id, fname)

def _mask_amount(amount_str):
    """金额千分位格式化"""
    try:
        return f"{float(amount_str):,.2f}"
    except:
        return amount_str

# ─── 命令实现 ─────────────────────────────────────────────

def cmd_new_trip(conn, args):
    """创建新行程"""
    title = args.title.strip()
    if not args.start:
        print("❌ 需要指定 --start 开始日期")
        return
    if not args.end:
        print("❌ 需要指定 --end 结束日期")
        return

    # 自动生成 trip_id: YYYY-MM_slugified_title
    start_month = args.start[:7]  # YYYY-MM
    slug = title.lower().replace(" ", "-")
    trip_id = f"{start_month}_{slug[:20]}"

    # 检查是否已存在同名trip
    existing = conn.execute(
        "SELECT id FROM expenses WHERE trip_id = ? AND entry_type = 'trip'",
        (trip_id,)
    ).fetchone()
    if existing:
        print(f"❌ trip_id={trip_id} 已存在，使用 --force 强制创建或用其他名称")
        return

    conn.execute("""
        INSERT INTO expenses
        (trip_id, entry_type, title, start_date, end_date, destination,
         project, payer, notes, created_at, updated_at)
        VALUES (?, 'trip', ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trip_id, title,
        args.start, args.end or '',
        args.dest or '', args.project or '',
        args.payer or '', args.notes or '',
        now(), now()
    ))
    conn.commit()
    print(f"✅ 行程已创建: {trip_id}")
    print(f"   {args.title}")
    print(f"   {args.start} → {args.end}")
    if args.dest:
        print(f"   目的地: {args.dest}")


def cmd_add(conn, args):
    """添加单笔消费，支持追加多凭证到同一记录"""
    title = args.title.strip()
    if not args.trip_id:
        print("❌ 需要指定 --trip-id")
        return
    if not args.amount:
        print("❌ 需要指定 --amount")
        return

    # 验证 trip 存在
    trip = conn.execute(
        "SELECT * FROM expenses WHERE trip_id = ? AND entry_type = 'trip'",
        (args.trip_id,)
    ).fetchone()
    if not trip:
        print(f"❌ trip_id={args.trip_id} 不存在，请先创建行程")
        return

    # ── 重复条目检查 ─────────────────────────────────────────────
    # 同一 trip + 同金额 + 同日期 + 同类型 → 视为重复，追加凭证而非新建
    expense_date = args.date or today()
    existing = conn.execute(
        """SELECT id, receipt_paths FROM expenses
         WHERE trip_id = ? AND entry_type = 'expense'
           AND ABS(amount - ?) < 0.01
           AND expense_date = ?
           AND category = ?""",
        (args.trip_id, args.amount, expense_date, args.category or '其他')
    ).fetchone()

    new_receipt_rel = ""
    if args.receipt:
        new_receipt_rel = _copy_receipt(args.receipt, args.trip_id, dest_name=args.receipt_name)
        file_type = args.receipt_name or os.path.basename(args.receipt)

    if existing:
        # 追加凭证到已有记录
        import json as _json
        try:
            paths = _json.loads(existing['receipt_paths'] or '[]')
        except:
            paths = []
        if new_receipt_rel and new_receipt_rel not in paths:
            paths.append(new_receipt_rel)
        updated_paths = _json.dumps(paths, ensure_ascii=False)
        conn.execute(
            "UPDATE expenses SET receipt_paths = ?, updated_at = ? WHERE id = ?",
            (updated_paths, now(), existing['id'])
        )
        conn.commit()
        print(f"✅ 追加凭证到已有记录 [{existing['id']}]（trip={args.trip_id}）")
        print(f"   {title} | {_mask_amount(args.amount)}元 | {args.category or '其他'}")
        if new_receipt_rel:
            print(f"   📎 + {os.path.basename(new_receipt_rel)}")
        return

    # 新建记录
    if new_receipt_rel:
        import json as _json
        receipt_paths_json = _json.dumps([new_receipt_rel], ensure_ascii=False)
    else:
        receipt_paths_json = '[]'

    conn.execute("""
        INSERT INTO expenses
        (trip_id, entry_type, title, amount, currency, category,
         expense_date, project, payer, receipt_path, receipt_paths, file_type, notes,
         created_at, updated_at)
        VALUES (?, 'expense', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        args.trip_id, title,
        args.amount, args.currency or 'CNY',
        args.category or '其他',
        expense_date,
        args.project or trip['project'] or '',
        args.payer or '',
        new_receipt_rel, receipt_paths_json, os.path.basename(args.receipt) if args.receipt else '',
        args.notes or '',
        now(), now()
    ))
    conn.commit()
    print(f"✅ 消费记录已添加（trip={args.trip_id}）")
    print(f"   {title} | {_mask_amount(args.amount)}元 | {args.category or '其他'}")


def cmd_list(conn, args):
    """列出行程或消费"""
    filter_str = args.filter or "all"

    if filter_str == "all":
        rows = conn.execute("""
            SELECT * FROM expenses
            WHERE entry_type = 'trip'
            ORDER BY start_date DESC
        """).fetchall()
        print(f"📋 所有行程（共 {len(rows)} 个）\n")
        for r in rows:
            total = conn.execute(
                "SELECT SUM(amount) as s FROM expenses WHERE trip_id = ? AND entry_type = 'expense'",
                (r['trip_id'],)
            ).fetchone()['s'] or 0
            status = STATUS_EMOJI[r['reimbursement_status']] + STATUS_MAP[r['reimbursement_status']]
            print(f"  [{r['trip_id']}] {r['title']} | {r['start_date']}→{r['end_date']} | {status} | {_mask_amount(total)}元")

    elif filter_str.startswith("month:"):
        month = filter_str.split(":", 1)[1]  # YYYY-MM
        rows = conn.execute("""
            SELECT * FROM expenses
            WHERE entry_type = 'trip' AND trip_id LIKE ?
            ORDER BY start_date DESC
        """, (f"{month}%",)).fetchall()
        print(f"📋 {month} 行程（共 {len(rows)} 个）\n")
        for r in rows:
            total = conn.execute(
                "SELECT SUM(amount) as s FROM expenses WHERE trip_id = ? AND entry_type = 'expense'",
                (r['trip_id'],)
            ).fetchone()['s'] or 0
            print(f"  [{r['trip_id']}] {r['title']} | {_mask_amount(total)}元")

    elif filter_str == "pending":
        rows = conn.execute("""
            SELECT * FROM expenses WHERE entry_type = 'trip' AND reimbursement_status = 0
            ORDER BY start_date DESC
        """).fetchall()
        print(f"⏳ 待报销行程（共 {len(rows)} 个）\n")
        for r in rows:
            print(f"  [{r['trip_id']}] {r['title']} | {r['start_date']}→{r['end_date']}")

    elif filter_str == "reimbursed":
        rows = conn.execute("""
            SELECT * FROM expenses WHERE entry_type = 'trip' AND reimbursement_status IN (1,2,3)
            ORDER BY start_date DESC
        """).fetchall()
        print(f"💰 已报销行程（共 {len(rows)} 个）\n")
        for r in rows:
            print(f"  [{r['trip_id']}] {r['title']} | {STATUS_MAP[r['reimbursement_status']]}")

    else:
        # 按 trip_id 精确查找
        rows = conn.execute("""
            SELECT * FROM expenses WHERE trip_id = ? ORDER BY entry_type, expense_date
        """, (filter_str,)).fetchall()
        if not rows:
            print(f"❌ 未找到 trip_id={filter_str}")
            return
        print(f"📋 {filter_str} 详情\n")
        for r in rows:
            if r['entry_type'] == 'trip':
                print(f"  🚩 {r['title']}")
                print(f"     {r['start_date']} → {r['end_date']} | {r['destination']}")
                print(f"     状态: {STATUS_EMOJI[r['reimbursement_status']]}{STATUS_MAP[r['reimbursement_status']]}")
            else:
                cat = CAT_EMOJI.get(r['category'], "📦")
                amt = _mask_amount(str(r['amount']))
                import json as _json
                try:
                    rpaths = _json.loads(r['receipt_paths'] or '[]')
                except:
                    rpaths = []
                if r['receipt_path'] and r['receipt_path'] not in rpaths:
                    rpaths.append(r['receipt_path'])
                rec_info = f" 📎({len(rpaths)}份)" if rpaths else ""
                print(f"     {cat} {r['expense_date']} {r['title']} | {amt}元{rec_info}")


def cmd_detail(conn, args):
    """行程详情（含汇总）"""
    rows = conn.execute("""
        SELECT * FROM expenses WHERE trip_id = ? ORDER BY entry_type, expense_date
    """, (args.trip_id,)).fetchall()
    if not rows:
        print(f"❌ 未找到 trip_id={args.trip_id}")
        return

    trip = None
    expenses = []
    for r in rows:
        if r['entry_type'] == 'trip':
            trip = r
        else:
            expenses.append(r)

    if not trip:
        print(f"❌ 未找到行程头 trip_id={args.trip_id}")
        return

    total = sum(e['amount'] for e in expenses)
    print(f"\n{'='*50}")
    print(f"🚩 {trip['title']}")
    print(f"   行程: {trip['start_date']} → {trip['end_date']}")
    print(f"   目的地: {trip['destination'] or '—'}")
    print(f"   项目: {trip['project'] or '—'}")
    print(f"   状态: {STATUS_EMOJI[trip['reimbursement_status']]}{STATUS_MAP[trip['reimbursement_status']]}")
    print(f"{'─'*50}")
    print(f"  消费明细（共 {len(expenses)} 笔，合计 {_mask_amount(str(total))}元）\n")
    for e in expenses:
        cat = CAT_EMOJI.get(e['category'], "📦")
        import json as _json
        try:
            rpaths = _json.loads(e['receipt_paths'] or '[]')
        except:
            rpaths = []
        if e['receipt_path'] and e['receipt_path'] not in rpaths:
            rpaths.append(e['receipt_path'])
        rec_info = f" 📎({len(rpaths)}份)" if rpaths else " ❌无附件"
        print(f"  {cat} [{e['id']}] {e['expense_date']} {e['title']}")
        print(f"       {_mask_amount(str(e['amount']))}元 | {e['category'] or '其他'}{rec_info}")
        for rp in rpaths:
            print(f"         📄 {rp}")
        if e['notes']:
            print(f"       📝 {e['notes']}")
    print(f"{'─'*50}")
    print(f"  💰 合计: {_mask_amount(str(total))}元\n")


def cmd_status(conn, args):
    """更新报销状态"""
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?",
        (args.id,)
    ).fetchone()
    if not row:
        print(f"❌ 未找到 id={args.id}")
        return

    old_status = STATUS_EMOJI[row['reimbursement_status']] + STATUS_MAP[row['reimbursement_status']]
    new_status = STATUS_EMOJI[args.status] + STATUS_MAP[args.status]

    conn.execute(
        "UPDATE expenses SET reimbursement_status = ?, updated_at = ? WHERE id = ?",
        (args.status, now(), args.id)
    )
    conn.commit()
    print(f"✅ 状态更新: {old_status} → {new_status}")


def cmd_report(conn, args):
    """生成报销单 Markdown"""
    rows = conn.execute("""
        SELECT * FROM expenses WHERE trip_id = ? ORDER BY entry_type, expense_date
    """, (args.trip_id,)).fetchall()
    if not rows:
        print(f"❌ 未找到 trip_id={args.trip_id}")
        return

    trip = None
    expenses = []
    for r in rows:
        if r['entry_type'] == 'trip':
            trip = r
        else:
            expenses.append(r)

    total = sum(e['amount'] for e in expenses)

    # 按 category 汇总
    by_cat = {}
    for e in expenses:
        cat = e['category'] or '其他'
        by_cat[cat] = by_cat.get(cat, 0) + e['amount']

    lines = []
    lines.append(f"# 📋 报销单\n")
    lines.append(f"**行程:** {trip['title']}")
    lines.append(f"**时间:** {trip['start_date']} → {trip['end_date']}")
    lines.append(f"**目的地:** {trip['destination'] or '—'}")
    lines.append(f"**项目:** {trip['project'] or '—'}")
    lines.append(f"**状态:** {STATUS_EMOJI[trip['reimbursement_status']]}{STATUS_MAP[trip['reimbursement_status']]}\n")
    lines.append(f"---")
    lines.append(f"\n## 💰 消费汇总\n")
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"- {CAT_EMOJI.get(cat,'📦')} {cat}: {_mask_amount(str(amt))}元")
    lines.append(f"\n**总计: {_mask_amount(str(total))}元**\n")
    lines.append(f"---\n\n## 📄 消费明细\n")
    lines.append(f"| # | 日期 | 项目 | 分类 | 金额 | 附件 |")
    lines.append(f"|---|------|------|------|------|------|")
    import json as _json
    for i, e in enumerate(expenses, 1):
        try:
            rpaths = _json.loads(e['receipt_paths'] or '[]')
        except:
            rpaths = []
        if e['receipt_path'] and e['receipt_path'] not in rpaths:
            rpaths.append(e['receipt_path'])
        rec = f"✅({len(rpaths)}份)" if rpaths else "❌"
        lines.append(f"| {i} | {e['expense_date']} | {e['title']} | {e['category']} | {_mask_amount(str(e['amount']))} | {rec} |")
    lines.append(f"\n---\n*报销单生成时间: {now()}*\n")

    report = "\n".join(lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 报销单已保存: {args.output}")
    else:
        print(report)


def cmd_delete(conn, args):
    """删除记录"""
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (args.id,)).fetchone()
    if not row:
        print(f"❌ 未找到 id={args.id}")
        return
    conn.execute("DELETE FROM expenses WHERE id = ?", (args.id,))
    # 如果是 trip 头，也删所有关联 expense
    if row['entry_type'] == 'trip':
        conn.execute("DELETE FROM expenses WHERE trip_id = ?", (row['trip_id'],))
        # 删除附件目录
        rec_dir = os.path.join(RECEIPTS_DIR, row['trip_id'])
        if os.path.exists(rec_dir):
            shutil.rmtree(rec_dir)
    conn.commit()
    print(f"✅ 已删除 {'行程' if row['entry_type']=='trip' else '消费记录'} [{args.id}] {row['title']}")


def cmd_categories(conn, args):
    """分类统计"""
    rows = conn.execute("""
        SELECT category, SUM(amount) as total, COUNT(*) as cnt
        FROM expenses WHERE entry_type = 'expense' AND category != ''
        GROUP BY category ORDER BY total DESC
    """).fetchall()
    print("📊 分类统计\n")
    for r in rows:
        cat = r['category'] or '其他'
        print(f"  {CAT_EMOJI.get(cat,'📦')} {cat}: {_mask_amount(str(r['total']))}元 ({r['cnt']}笔)")


# ─── CLI 入口 ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="报销管理系统")
    sub = parser.add_subparsers(dest="cmd")

    # new-trip
    p_trip = sub.add_parser("new-trip", help="创建新行程")
    p_trip.add_argument("title")
    p_trip.add_argument("--dest")
    p_trip.add_argument("--start")
    p_trip.add_argument("--end")
    p_trip.add_argument("--project")
    p_trip.add_argument("--payer")
    p_trip.add_argument("--notes")

    # add
    p_add = sub.add_parser("add", help="添加消费记录")
    p_add.add_argument("title")
    p_add.add_argument("--trip-id", required=True)
    p_add.add_argument("--amount", type=float, required=True)
    p_add.add_argument("--category")
    p_add.add_argument("--date")
    p_add.add_argument("--currency", default="CNY")
    p_add.add_argument("--project")
    p_add.add_argument("--payer")
    p_add.add_argument("--receipt")
    p_add.add_argument("--receipt-name")
    p_add.add_argument("--notes")

    # list
    p_list = sub.add_parser("list", help="列出行程")
    p_list.add_argument("filter", nargs="?", default="all")

    # detail
    p_detail = sub.add_parser("detail", help="行程详情")
    p_detail.add_argument("trip_id")

    # status
    p_status = sub.add_parser("status", help="更新状态")
    p_status.add_argument("id", type=int)
    p_status.add_argument("status", type=int, choices=[0,1,2,3])

    # report
    p_report = sub.add_parser("report", help="生成报销单")
    p_report.add_argument("trip_id")
    p_report.add_argument("--output", "-o")

    # delete
    p_del = sub.add_parser("delete", help="删除记录")
    p_del.add_argument("id", type=int)

    # categories
    sub.add_parser("categories", help="分类统计")

    args = parser.parse_args()

    conn = get_db()

    if args.cmd == "new-trip":
        cmd_new_trip(conn, args)
    elif args.cmd == "add":
        cmd_add(conn, args)
    elif args.cmd == "list":
        cmd_list(conn, args)
    elif args.cmd == "detail":
        cmd_detail(conn, args)
    elif args.cmd == "status":
        cmd_status(conn, args)
    elif args.cmd == "report":
        cmd_report(conn, args)
    elif args.cmd == "delete":
        cmd_delete(conn, args)
    elif args.cmd == "categories":
        cmd_categories(conn, args)
    else:
        parser.print_help()

    conn.close()

if __name__ == "__main__":
    main()
