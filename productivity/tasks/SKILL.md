---
name: tasks
description: "任务/日程管理：使用 SQLite DB (task/tasks.db) + Markdown (task/task.md) 双重存储。支持待办事项和日历日程两种类型。"
version: 0.1
author: 梁柱私人助理
tags: ["任务管理", "待办", "日程", "todo", "schedule"]
platforms: ["macos", "linux"]
metadata:
  {
    openclaw:
      {
        emoji: "📋",
        requires:
          {
            bins: ["python3"],
          },
      },
  }
---

# 任务管理系统

## 数据库

- **DB**: `$WORKSPACE/task/tasks.db`
- **Markdown**: `$WORKSPACE/task/task.md`

## 数据模型

### tasks 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `title` | TEXT | 标题/描述 |
| `description` | TEXT | 详细说明 |
| `event_type` | TEXT | `event`=日程（有开始+结束时间）`todo`=待办（只有截止时间）|
| `start_date` | TEXT | 开始时间 `YYYY-MM-DD HH:MM`，日程必填 |
| `end_date` | TEXT | 结束时间 `YYYY-MM-DD HH:MM`，待办=截止时间 |
| `is_all_day` | INTEGER | 1=全天日程 |
| `priority` | INTEGER | 0=⚪无, 1=🔴高, 2=🟡中, 3=🟢低 |
| `time_dimension` | TEXT | 今天/本周/下周/本月/本季/未来/已过期 |
| `project` | TEXT | 所属项目 |
| `tags` | TEXT | 标签，逗号分隔 |
| `status` | INTEGER | 0=待办, 1=已完成, 2=已取消 |
| `created_at` | TEXT | 创建时间 |
| `updated_at` | TEXT | 更新时间 |
| `completed_at` | TEXT | 完成时间 |

### 事件 vs 待办判断逻辑

```
if start_date and end_date:
    → 日程 event（时间段）
elif end_date:
    → 待办 todo（截止时间）
else:
    → 待办 todo（无截止日期）
```

## 命令格式

```
+task <标题> [p:🔴] [项目名] [#标签]    添加待办
+event <标题> <开始> <结束> [p:🔴]      添加日程
+done <id>                              标记完成
+cancel <id>                            取消任务
+edit <id> <新标题>                     编辑标题
+tasks [today|week|all|overdue|project:名]   查看任务
+projects                               列出所有项目
+task <id> info                         查看详情
```

## 时间维度计算

- **今天**: end_date = 今日
- **本周剩余**: end_date 在本周（周一~周日）内
- **下周**: end_date 在下周
- **本月**: end_date 在本月内
- **本季**: end_date 在本季内（Q2: 4-6月）
- **未来**: end_date > 本季末
- **已过期**: end_date < 今日 且 status=0

## 定时任务

- **每日 6AM** (Asia/Shanghai): 从 DB 读取今天+本周任务，推送到 Telegram
