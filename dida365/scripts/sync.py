#!/usr/bin/env python3
"""
Dida365 任务同步脚本

功能：
1. 从 Dida365 API 读取任务
2. 同步到 GOALS.md 格式
3. 支持双向更新

依赖：
    pip install requests

环境变量：
    DIDA365_CLIENT_ID     - OAuth2 Client ID
    DIDA365_CLIENT_SECRET - OAuth2 Client Secret
    DIDA365_TOKEN         - Refresh Token
"""

import os, json, sys, argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ 请先安装 requests: pip install requests")
    sys.exit(1)

# ─── 配置 ────────────────────────────────────────────────
TOKEN_URL    = "https://api.dida365.com/oauth2/token"
API_BASE     = "https://api.dida365.com/v1"
TOKEN_FILE   = os.path.expanduser("~/.agents/skills/dida365/.token_cache.json")
GOALS_FILE   = os.path.expanduser("~/.openclaw/workspace/GOALS.md")

# ─── 认证 ────────────────────────────────────────────────
def get_client_credentials():
    client_id     = os.environ.get("DIDA365_CLIENT_ID")
    client_secret = os.environ.get("DIDA365_CLIENT_SECRET")
    refresh_token = os.environ.get("DIDA365_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        print("❌ 缺少环境变量：DIDA365_CLIENT_ID, DIDA365_CLIENT_SECRET, DIDA365_TOKEN")
        sys.exit(1)
    return client_id, client_secret, refresh_token

def load_cached_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        if datetime.now().timestamp() < data.get("expires_at", 0) - 60:
            return data["access_token"]
    return None

def save_cached_token(access_token, expires_in):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": access_token,
            "expires_at": datetime.now().timestamp() + expires_in
        }, f)

def refresh_access_token(client_id, client_secret, refresh_token):
    cached = load_cached_token()
    if cached:
        return cached

    resp = requests.post(TOKEN_URL, data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    })
    if resp.status_code != 200:
        raise Exception(f"Token refresh failed: {resp.status_code} {resp.text}")
    
    data = resp.json()
    save_cached_token(data["access_token"], data.get("expires_in", 3600))
    return data["access_token"]

# ─── API 请求 ───────────────────────────────────────────
def api_get(access_token, path):
    resp = requests.get(f"{API_BASE}{path}", headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    })
    resp.raise_for_status()
    return resp.json()

# ─── 获取任务 ────────────────────────────────────────────
def fetch_all_tasks(access_token):
    """获取所有项目任务"""
    tasks = []
    
    # 获取所有项目
    projects = api_get(access_token, "/projects")
    project_map = {p["id"]: p["name"] for p in projects}
    
    # 获取每个项目的任务
    for project in projects:
        try:
            project_tasks = api_get(access_token, f"/project/{project['id']}/task/")
            for task in project_tasks:
                task["projectName"] = project_map.get(project["id"], "默认")
                tasks.append(task)
        except Exception as e:
            print(f"  ⚠️  项目 {project['name']} 获取失败: {e}", file=sys.stderr)
    
    return tasks

# ─── 时间维度判断 ─────────────────────────────────────────
def get_time_dimension(due_date_str):
    """根据截止日期判断属于哪个时间维度"""
    if not due_date_str:
        return None, None
    
    try:
        # Dida365 使用时间戳（毫秒）
        if len(due_date_str) > 13:
            dt = datetime.fromtimestamp(int(due_date_str) / 1000)
        else:
            dt = datetime.fromtimestamp(int(due_date_str))
    except:
        return None, None
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = today + timedelta(days=6 - today.weekday())  # 本周日
    end_of_next_week = end_of_week + timedelta(days=7)        # 下周末
    
    date_label = dt.strftime("%m/%d")
    
    if dt.date() == today.date():
        return "今天", date_label
    elif dt.date() < end_of_week.date():
        weekday = ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()]
        return f"本周剩余", f"{weekday} {date_label}"
    elif dt.date() <= end_of_next_week.date():
        weekday = ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()]
        return "下周", f"{weekday} {date_label}"
    else:
        return "未来", dt.strftime("%m/%d")

# ─── 优先级映射 ──────────────────────────────────────────
def map_priority(p):
    return {1: "🔴", 2: "🟡", 3: "🟢"}.get(p, "⚪")

# ─── 同步到 GOALS.md ─────────────────────────────────────
def sync_to_goals(tasks):
    today_tasks = []
    week_tasks  = []
    next_week_tasks = []
    future_tasks = []
    
    for task in tasks:
        # 跳过已完成任务
        status = task.get("status", 0)
        if status == 2:  # 2 = completed
            continue
        
        due = task.get("dueDate") or task.get("startDate")
        time_dim, date_label = get_time_dimension(due)
        
        title    = task.get("title", "无标题")
        priority = map_priority(task.get("priority", 0))
        project  = task.get("projectName", "")
        tags     = f"[{project}]" if project else ""
        
        task_line = f"- {priority} {title} {tags}"
        
        if time_dim == "今天":
            today_tasks.append((task_line, date_label))
        elif time_dim == "本周剩余":
            week_tasks.append((task_line, date_label))
        elif time_dim == "下周":
            next_week_tasks.append((task_line, date_label))
        else:
            future_tasks.append((task_line, date_label))
    
    # 写入 GOALS.md（追加到现有文件，或创建新文件）
    existing = Path(GOALS_FILE).read_text() if Path(GOALS_FILE).exists() else ""
    
    # 找到 ## Dida365 任务 节的位置
    marker = "\n## Dida365 任务\n"
    if marker in existing:
        before, _ = existing.split(marker, 1)
    else:
        before = existing
    
    new_content = before.rstrip()
    if new_content != existing.rstrip() or marker not in existing:
        new_content += f"\n{marker}"
    else:
        new_content = before
    
    new_content += "\n\n"
    
    if today_tasks:
        new_content += "### 今天\n" + "\n".join(t[0] for t in sorted(today_tasks, key=lambda x: x[1])) + "\n\n"
    if week_tasks:
        new_content += "### 本周剩余\n" + "\n".join(t[0] for t in sorted(week_tasks, key=lambda x: x[1])) + "\n\n"
    if next_week_tasks:
        new_content += "### 下周\n" + "\n".join(t[0] for t in sorted(next_week_tasks, key=lambda x: x[1])) + "\n\n"
    if future_tasks:
        new_content += "### 未来\n" + "\n".join(t[0] for t in sorted(future_tasks, key=lambda x: x[1])) + "\n\n"
    
    # 统计
    total = len(today_tasks) + len(week_tasks) + len(next_week_tasks) + len(future_tasks)
    high  = sum(1 for t in tasks if t.get("priority") == 1 and t.get("status") != 2)
    new_content += f"\n*Dida365 同步于 {datetime.now().strftime('%H:%M:%S')}，共 {total} 项待办，🔴高优先级 {high} 项*\n"
    
    Path(GOALS_FILE).write_text(new_content)
    print(f"✅ 已同步到 GOALS.md")
    print(f"   今天: {len(today_tasks)} | 本周剩余: {len(week_tasks)} | 下周: {len(next_week_tasks)} | 未来: {len(future_tasks)}")

# ─── 主程序 ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Dida365 任务同步")
    parser.add_argument("--read", action="store_true", help="仅读取任务")
    parser.add_argument("--sync-goals", action="store_true", help="同步到 GOALS.md")
    args = parser.parse_args()
    
    client_id, client_secret, refresh_token = get_client_credentials()
    access_token = refresh_access_token(client_id, client_secret, refresh_token)
    
    print("📡 正在从 Dida365 获取任务...")
    tasks = fetch_all_tasks(access_token)
    print(f"📋 共获取 {len(tasks)} 个任务（含已完成）")
    
    if args.read:
        for task in tasks:
            priority = map_priority(task.get("priority", 0))
            status = "✅" if task.get("status") == 2 else "⬜"
            due = task.get("dueDate", "")[:8] if task.get("dueDate") else ""
            print(f"{status} {priority} {task.get('title','无标题')} [{task.get('projectName','')}] due:{due}")
    
    if args.sync_goals:
        sync_to_goals(tasks)

if __name__ == "__main__":
    main()
