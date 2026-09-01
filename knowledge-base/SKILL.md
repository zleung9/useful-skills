---
name: knowledge-base
description: |
  个人知识库管理：添加、搜索、移除知识库条目；定期扫描 workspace 自动入库。

  **当以下情况时使用此 Skill**：
  (1) 用户说「存到知识库」「收藏」「加入 KB」「记一下」
  (2) 用户说「搜一下知识库」「知识库里有没有」
  (3) 用户说「从知识库移除」
  (4) 用户说「知识库统计」「看看知识库」
  (5) 定时触发：定期扫描 workspace 文件并通知用户新增内容

  **NOT for**：长期记忆、个人偏好（用 MEMORY.md）
metadata:
  {
    "openclaw":
      {
        "emoji": "🗃️",
        "requires": { "bins": ["python3", "sqlite3"] },
        "install": [],
        "homepage": "https://github.com/openclaw/openclaw"
      }
  }
---

# Knowledge Base Skill

## 目录结构

```
~/KnowledgeBase/
├── kb.db              ← SQLite 数据库
└── items/             ← 所有文件的物理存储位置
```

## 数据库 Schema

```sql
CREATE TABLE kb_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT UNIQUE NOT NULL,   -- items/ 下的真实文件名
    title           TEXT,                    -- 可读标题
    source_type     TEXT NOT NULL,           -- 来源类型
    source_url      TEXT,                    -- 原始 URL
    collected_at    TEXT NOT NULL,           -- 入库时间 ISO 8601
    tags            TEXT,                    -- 逗号分隔标签
    file_size       INTEGER,                 -- 字节数
    mime_type       TEXT,                   -- MIME 类型
    description     TEXT                    -- 简短描述
);
```

**source_type 可选值：**
| 值 | 含义 |
|---|---|
| `wechat_article` | 微信公众号文章 |
| `youtube` | YouTube 视频 |
| `pdf` | PDF 论文 |
| `task_output` | 任务输出 |
| `web_page` | 网页 |
| `image` | 图片 |
| `other` | 其他 |

## 脚本用法

```bash
python3 ~/.agents/skills/knowledge-base/scripts/kb_register.py <命令>

# 添加文件
python3 kb_register.py add <文件路径> --title "标题" --type wechat_article \
    --url "来源URL" --tags "AI,Agent" --desc "描述"

# 列出所有
python3 kb_register.py list --tag AI --limit 50

# 搜索
python3 kb_register.py search <关键词>

# 移除
python3 kb_register.py remove <filename>

# 统计
python3 kb_register.py stats

# 扫描 workspace
python3 kb_register.py scan
```

## Cron 定时任务

**建议配置**：每 4 小时扫描一次 workspace，汇总新增文件并通知用户：

```
cron add \
  --name "知识库 workspace 扫描" \
  --schedule "cron,expr=0 */4 * * *,tz=Asia/Shanghai" \
  --sessionTarget isolated \
  --payload.kind agentTurn \
  --payload.message "
执行以下步骤：

1. 运行扫描命令：
   python3 ~/.agents/skills/knowledge-base/scripts/kb_register.py scan

2. 检查扫描结果：
   - 如果有新增条目（✅ 新增成功），汇总列出：文件名、大小、来源类型
   - 如果全是跳过（⚠️ 文件已存在），回复「知识库扫描完成：无新增内容」

3. 运行统计：
   python3 ~/.agents/skills/knowledge-base/scripts/kb_register.py stats

4. 向用户（梁柱，Telegram ID: 8273544929）发送消息：
   - 标题：「📦 知识库定期扫描报告」
   - 内容：本次新增 N 条，当前合计 M 条（按类型分布）
   - 每种来源类型一行（例如：微信公众号文章: X 条）

5. 将本次扫描的简要记录追加到 ~/KnowledgeBase/scan_log.txt
" \
  --delivery.mode announce \
  --delivery.channel telegram \
  --delivery.to 8273544929
```

## 手动添加内容流程

当用户说「把这个存到知识库」时：

1. **识别文件来源**：
   - 微信文章 → 调用 `wechat-article-extractor` skill 先提取
   - YouTube 视频 → 调用 `youtube-video` skill 先获取 transcript
   - PDF 论文 → 确保文件在本地
   - workspace 已有文件 → 直接注册

2. **注册到 KB**：
   ```bash
   python3 kb_register.py add <文件路径> \
     --title "内容标题" \
     --type <来源类型> \
     --url "<来源URL>" \
     --tags "<标签1,标签2>"
   ```

3. **回复用户**：
   确认入库成功，包含：文件名、大小、来源类型、知识库当前总条目数

## 搜索流程

当用户说「搜一下知识库」时：

1. 提取搜索关键词
2. 运行：`python3 kb_register.py search <关键词>`
3. 按格式返回结果列表

## 移除流程

当用户说「从知识库移除」时：

1. 运行：`python3 kb_register.py remove <filename>`
2. 确认文件和数据库记录均已删除
3. 回复用户

## 注意事项

- **items/ 是物理存储**：添加文件时会被复制到 items/，原文件保留在原位置
- **扫描会复制文件**：scan 命令会把 workspace 文件复制到 KB，不移动原文件
- **同名文件去重**：已存在的文件名会跳过，不覆盖
- **session 历史扫描**：暂不自动扫描（内容识别复杂），以手动添加为主
- **图片命名**：从微信/网页下载的图片，在文件名中包含序号便于对应 caption
