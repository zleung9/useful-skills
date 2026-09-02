#!/usr/bin/env python3
"""
task.py — 任务/日程管理核心脚本

用法：
    python3 task.py add "任务描述" [--priority 1] [--project xxx] [--tags a,b] [--end YYYY-MM-DD] [--start YYYY-MM-DD]
    python3 task.py event "日程标题" --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM" [--project xxx] [--priority 1]
    python3 task.py done <id>
    python3 task.py cancel <id>
    python3 task.py edit <id> "新标题"
    python3 task.py list [today|week|month|all|overdue|project:名]
    python3 task.py info <id>
    python3 task.py projects
    python3 task.py sync-md    # 同步 DB → task.md
"""

import sqlite3, os, sys, re, argparse
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = os.path.expanduser("~/.hermes")
DB_PATH   = os.path.join(WORKSPACE, "task", "tasks.db")
MD_PATH   = os.path.join(WORKSPACE, "task", "task.md")

# 优先级：0=⚪无, 1=🟢低, 2=🟡中, 3=🔴高
PRIO_MAP   = {3: "🔴", 2: "🟡", 1: "🟢", 0: "⚪"}
PRIO_LABEL = {3: "🔴高", 2: "🟡中", 1: "🟢低", 0: "⚪无"}

# ─── 时间工具 ──────────────────────────────────────────────
def today():
    return datetime.now().strftime("%Y-%m-%d")

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calc_time_dim(end_date_str):
    """根据 end_date 计算 time_dimension"""
    if not end_date_str:
        return "未来"
    try:
        end = end_date_str.strip()
        if len(end) == 16:  # YYYY-MM-DD HH:MM
            ed = datetime.strptime(end, "%Y-%m-%d %H:%M")
        elif len(end) == 10:  # YYYY-MM-DD
            ed = datetime.strptime(end, "%Y-%m-%d")
        else:
            return "未来"
    except:
        return "未来"
    
    td   = datetime.now()
    today_s = td.strftime("%Y-%m-%d")
    monday  = td - timedelta(days=td.weekday())
    sunday  = monday + timedelta(days=6)
    n_monday = monday + timedelta(days=7)
    n_sunday = n_monday + timedelta(days=6)
    
    if ed.date() == td.date():
        return "今天"
    elif monday.date() <= ed.date() <= sunday.date():
        return "本周"
    elif n_monday.date() <= ed.date() <= n_sunday.date():
        return "下周"
    elif ed.year == td.year and ed.month == td.month:
        return "本月"
    elif (td.month in [4,5,6] and ed.month in [4,5,6] and ed.year == td.year) or \
         (td.month in [7,8,9] and ed.month in [7,8,9] and ed.year == td.year) or \
         (td.month in [10,11,12] and ed.month in [10,11,12] and ed.year == td.year) or \
         (td.month in [1,2,3] and ed.month in [1,2,3] and ed.year == td.year):
        return "本季"
    else:
        return "未来"

def is_overdue(end_date_str, status):
    if status != 0 or not end_date_str:
        return False
    try:
        end = end_date_str.strip()
        ed = datetime.strptime(end[:16], "%Y-%m-%d %H:%M") if len(end) >= 16 else datetime.strptime(end, "%Y-%m-%d")
        return ed < datetime.now()
    except:
        return False

def week_range():
    td = datetime.now()
    monday = td - timedelta(days=td.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%m/%d"), sunday.strftime("%m/%d")

def next_week_range():
    td = datetime.now()
    monday = td - timedelta(days=td.weekday()) + timedelta(days=7)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%m/%d"), sunday.strftime("%m/%d")

# ─── 数据库 ────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def row_to_dict(row):
    return dict(row) if row else None

# ─── 核心操作 ──────────────────────────────────────────────
def add_task(title, description="", end_date=None, start_date=None,
             priority=0, project="", tags="", is_all_day=0):
    conn = get_db()
    c = conn.cursor()
    
    # 判断事件类型
    if start_date and end_date:
        event_type = "event"
    elif end_date:
        event_type = "todo"
    else:
        event_type = "todo"
    
    time_dim = calc_time_dim(end_date)
    
    c.execute("""INSERT INTO tasks 
        (title, description, event_type, start_date, end_date, is_all_day,
         priority, time_dimension, project, tags, status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?)""",
        (title, description, event_type, start_date, end_date, is_all_day,
         priority, time_dim, project, tags, now(), now()))
    
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id

def add_event(title, start, end, description="", priority=0, project="", tags=""):
    """添加日程"""
    return add_task(title, description, end_date=end, start_date=start,
                    priority=priority, project=project, tags=tags, is_all_day=0)

def complete_task(task_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE tasks SET status=1, completed_at=?, updated_at=? WHERE id=?",
              (now(), now(), task_id))
    conn.commit()
    conn.close()

def cancel_task(task_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE tasks SET status=2, updated_at=? WHERE id=?",
              (now(), task_id))
    conn.commit()
    conn.close()

def edit_task(task_id, new_title):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE tasks SET title=?, updated_at=? WHERE id=?",
              (new_title, now(), task_id))
    conn.commit()
    conn.close()

def list_tasks(filter_type="all"):
    conn = get_db()
    c = conn.cursor()
    
    base = "SELECT * FROM tasks WHERE status != 2"
    
    if filter_type == "today":
        today_s = datetime.now().strftime("%Y-%m-%d")
        rows = c.execute(f"{base} AND date(end_date) = date('{today_s}') ORDER BY priority DESC, end_date").fetchall()
    elif filter_type == "week":
        monday = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        sunday = (datetime.now() + timedelta(days=6 - datetime.now().weekday())).strftime("%Y-%m-%d")
        rows = c.execute(f"{base} AND date(end_date) BETWEEN date('{monday}') AND date('{sunday}') ORDER BY priority DESC, end_date").fetchall()
    elif filter_type == "month":
        rows = c.execute(f"{base} AND strftime('%Y-%m', end_date) = strftime('%Y-%m', 'now') ORDER BY priority DESC, end_date").fetchall()
    elif filter_type == "overdue":
        rows = c.execute(f"{base} AND date(end_date) < date('now') AND status=0 ORDER BY priority DESC, end_date").fetchall()
    elif filter_type.startswith("project:"):
        proj = filter_type.split(":", 1)[1]
        rows = c.execute(f"{base} AND project=? ORDER BY priority DESC, end_date", (proj,)).fetchall()
    else:
        rows = c.execute(f"{base} ORDER BY priority DESC, end_date").fetchall()
    
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_task_info(task_id):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

def get_projects():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("""SELECT project, COUNT(*) as cnt FROM tasks 
                        WHERE status=0 AND project != '' GROUP BY project 
                        ORDER BY cnt DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def sync_to_md():
    """把 DB 内容同步到 task.md"""
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM tasks WHERE status != 2 ORDER BY priority DESC, end_date").fetchall()
    conn.close()
    
    today_s    = datetime.now().strftime("%Y-%m-%d")
    td         = datetime.now()
    monday     = td - timedelta(days=td.weekday())
    sunday     = monday + timedelta(days=6)
    
    def due_label(d):
        if not d: return ""
        try:
            dt = datetime.strptime(d[:16], "%Y-%m-%d %H:%M") if len(str(d)) >= 16 else datetime.strptime(d[:10], "%Y-%m-%d")
            if dt.date() == td.date(): return "今天"
            wd = ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()]
            return f"{wd} {dt.strftime('%m/%d')}"
        except: return d
    
    sections = {
        "今天": [],
        "本周": [],
        "下周": [],
        "本月": [],
        "未来": [],
        "已过期": [],
    }
    
    for r in rows:
        d = dict(r)
        if d["status"] == 1:
            continue
        
        end = d.get("end_date","")[:10]
        if is_overdue(d.get("end_date"), d["status"]):
            sections["已过期"].append(d)
        elif end == today_s:
            sections["今天"].append(d)
        elif monday.date() <= datetime.strptime(end,"%Y-%m-%d").date() <= sunday.date():
            sections["本周"].append(d)
        elif d["time_dimension"] in sections:
            sections[d["time_dimension"]].append(d)
        else:
            sections["未来"].append(d)

    type_icon = {"event": "📅", "todo": "☑️"}
    
    lines = [
        f"# 🎯 目标清单",
        f"",
        f"> 上次更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"---",
        f"",
        f"## 📋 待办 & 日程",
        f"",
    ]
    
    for dim, tasks in sections.items():
        if not tasks:
            continue
        lines.append(f"### {dim}")
        for t in tasks:
            icon = PRIO_MAP.get(t["priority"], "⚪")
            type_i = type_icon.get(t.get("event_type","todo"), "☑️")
            due = due_label(t.get("end_date"))
            proj = f"[{t['project']}]" if t["project"] else ""
            status = "✅" if t["status"] == 1 else "⬜"
            lines.append(f"- {status} {icon}{type_i} {t['title']} {proj} {f'⏰{due}' if due else ''}")
        lines.append("")
    
    lines.append(f"\n*从 tasks.db 自动生成 @ {now()}*")
    
    Path(MD_PATH).write_text("\n".join(lines))
    return "\n".join(lines)

# ─── 格式化输出 ───────────────────────────────────────────
def format_task_list(rows, title="任务列表"):
    if not rows:
        return f"📋 {title}\n\n（无任务）"
    
    type_map  = {"event": "📅", "todo": "☑️"}
    status_map = {0: "⬜", 1: "✅", 2: "❌"}
    
    lines = [f"📋 {title}\n"]
    
    dim_groups = {}
    for t in rows:
        dim = t.get("time_dimension", "未来") or "未来"
        if is_overdue(t.get("end_date"), t.get("status")):
            dim = "已过期"
        dim_groups.setdefault(dim, []).append(t)
    
    for dim, tasks in dim_groups.items():
        lines.append(f"\n**{dim}** ({len(tasks)}项)")
        for t in tasks:
            icon   = PRIO_MAP.get(t["priority"], "⚪")
            type_i = type_map.get(t.get("event_type","todo"), "☑️")
            stat   = status_map.get(t["status"], "⬜")
            due    = t.get("end_date", "")[:16] if t.get("end_date") else "无截止"
            proj   = f"[{t['project']}]" if t["project"] else ""
            lines.append(f"{stat} `{t['id']}` {icon}{type_i} {t['title']} {proj} ⏰{due}")
    
    return "\n".join(lines)

# ─── CLI 入口 ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="任务管理系统")
    sub = parser.add_subparsers(dest="cmd")
    
    p = sub.add_parser("add", help="添加待办")
    p.add_argument("title")
    p.add_argument("--desc", "--description", dest="desc", default="")
    p.add_argument("--end", "--end-date", dest="end_date", default=None)
    p.add_argument("--start", "--start-date", dest="start_date", default=None)
    p.add_argument("-p", "--priority", type=int, default=0)
    p.add_argument("--project", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--allday", "--all-day", dest="is_all_day", action="store_true")
    
    p = sub.add_parser("event", help="添加日程")
    p.add_argument("title")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--desc", "--description", dest="desc", default="")
    p.add_argument("-p", "--priority", type=int, default=0)
    p.add_argument("--project", default="")
    p.add_argument("--tags", default="")
    
    p = sub.add_parser("done", help="标记完成")
    p.add_argument("id", type=int)
    
    p = sub.add_parser("cancel", help="取消任务")
    p.add_argument("id", type=int)
    
    p = sub.add_parser("edit", help="编辑任务")
    p.add_argument("id", type=int)
    p.add_argument("title")
    
    p = sub.add_parser("list", help="列出任务")
    p.add_argument("filter", nargs="?", default="all")
    
    p = sub.add_parser("info", help="任务详情")
    p.add_argument("id", type=int)
    
    p = sub.add_parser("projects", help="列出项目")
    
    p = sub.add_parser("sync-md", help="同步到 Markdown")
    
    args = parser.parse_args()
    
    if args.cmd == "add":
        tid = add_task(args.title, args.desc, args.end_date, args.start_date,
                      args.priority, args.project, args.tags, 
                      1 if args.is_all_day else 0)
        print(f"✅ 添加成功 (ID: {tid})")
        sync_to_md()
    
    elif args.cmd == "event":
        tid = add_event(args.title, args.start, args.end, args.desc,
                       args.priority, args.project, args.tags)
        print(f"✅ 日程添加成功 (ID: {tid})")
        sync_to_md()
    
    elif args.cmd == "done":
        complete_task(args.id)
        print(f"✅ 已完成 ID:{args.id}")
        sync_to_md()
    
    elif args.cmd == "cancel":
        cancel_task(args.id)
        print(f"❌ 已取消 ID:{args.id}")
        sync_to_md()
    
    elif args.cmd == "edit":
        edit_task(args.id, args.title)
        print(f"✏️ 已更新 ID:{args.id}")
        sync_to_md()
    
    elif args.cmd == "list":
        rows = list_tasks(args.filter)
        print(format_task_list(rows, args.filter))
    
    elif args.cmd == "info":
        t = get_task_info(args.id)
        if t:

            print(f"**{t['title']}**")
            print(f"ID: {t['id']}")
            print(f"类型: {'📅日程' if t['event_type']=='event' else '☑️待办'}")
            print(f"优先级: {PRIO_LABEL.get(t['priority'],'⚪')}")
            print(f"时间: {t['start_date'] or '无'} → {t['end_date'] or '无'}")
            print(f"项目: {t['project'] or '无'}")
            print(f"标签: {t['tags'] or '无'}")
            print(f"状态: {'✅已完成' if t['status']==1 else '❌已取消' if t['status']==2 else '⬜待办'}")
        else:
            print(f"❌ 未找到 ID:{args.id}")
    
    elif args.cmd == "projects":
        for p in get_projects():
            print(f"📁 {p['project']}: {p['cnt']}项")
    
    elif args.cmd == "sync-md":
        result = sync_to_md()
        print("✅ 已同步到 task.md")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
