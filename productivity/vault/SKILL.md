---
name: vault
description: "🔐 加密密码保险库。使用 AES-256-GCM + PBKDF2 加密，所有敏感数据（密码/用户名/URL）密文存储，Master Password 不落盘。查看密码需解锁。"
version: 0.1
author: 梁柱私人助理
tags: ["密码", "保险库", "vault", "加密", "账户管理"]
platforms: ["macos", "linux"]
metadata:
  {
    openclaw:
      {
        emoji: "🔐",
        requires:
          {
            bins: ["python3"],
            optionalBins: ["~/.agents/skills/faster-whisper/.venv/bin/python"],
          },
      },
  }
---

# 🔐 密码保险库

## 文件位置

```
~/.hermes/vault/
    vault.db       ← 加密数据库
    .vault_meta    ← 盐和加密内部密钥
```

## 安全设计

- **AES-256-GCM**：所有敏感字段（username/password/url/notes）全部加密
- **PBKDF2-HMAC-SHA256**：100k 次迭代派生密钥，防止暴力破解
- **双层密钥**：Master password → 派生密钥 → 解密内部随机密钥 → 二次派生为加密密钥
- **随机 IV**：每次加密使用不同的 12-byte nonce，防止模式分析
- **零存储**：Master password 永不存储，进程结束即从内存消失
- **隐式锁定**：vault.db 本身是密文，无密码的派生密钥无法解读任何内容

## 使用方式

**⚠️ 重要：Master password 不存储，需要你每次授权**

### 通过助手操作

你告诉我：
- 「查看密码」→ 我会请你输入 Master password → 展示后即忘
- 「添加密码」→ 告诉我标题/账号/密码，我存入加密库
- 「列出密码」→ 显示标题+掩码用户名（不显示密码）

### 命令行操作

```bash
# 解锁 vault（解锁后会话密钥保存在内存，进程结束即失效）
VAULT_MASTER_PASSWORD="你的密码" python3 ~/.agents/skills/vault/scripts/vault.py unlock

# 添加条目
VAULT_MASTER_PASSWORD="你的密码" python3 ~/.agents/skills/vault/scripts/vault.py add "GitHub" -u "user@email.com" -p "secret123" -c "工作"

# 列出所有条目（不解密密码，仅显示标题和掩码用户名）
VAULT_MASTER_PASSWORD="你的密码" python3 ~/.agents/skills/vault/scripts/vault.py list

# 查看完整条目（含密码）
VAULT_MASTER_PASSWORD="你的密码" python3 ~/.agents/skills/vault/scripts/vault.py get "GitHub"

# 删除条目
VAULT_MASTER_PASSWORD="你的密码" python3 ~/.agents/skills/vault/scripts/vault.py delete 1

# 修改密码
VAULT_MASTER_PASSWORD="你的密码" python3 ~/.agents/skills/vault/scripts/vault.py passwd 1 -p "newpassword"
```

## 字段说明

| 参数 | 说明 |
|------|------|
| `title` | 条目标题（不加密，用于搜索） |
| `-u/--username` | 用户名（加密存储） |
| `-p/--password` | 密码（加密存储） |
| `--url` | 网址链接（加密存储） |
| `--notes` | 备注（加密存储） |
| `-c/--category` | 分类，如"工作/个人/技术"（不加密） |
| `-t/--tags` | 标签，逗号分隔（不加密） |

## 通过助手使用示例

```
你：帮我存一下 GitHub 的密码，用户名是 zleung9@outlook.com，密码是 xxx
我：好的，请告诉我 master password 来解锁 vault

你：（提供 master password）
我：（解锁后存入，告诉你保存成功）

你：列出所有密码
我：📋 密码库（共 3 条）
    📁 工作 (2条)
       [1] GitHub zle****m
       [2] 服务器 root@1.2.3.4
    📁 个人 (1条)
       [3] Gmail zle****m

你：查看 GitHub 的密码
我：请提供 master password（或我记住你的上一次会话密钥...）
```

## 当前状态

- Vault 已初始化（测试条目已添加，需用真实密码替换）
- Master password 需要你自己设置（我目前不知道）
- 提醒：vault.db 和 .vault_meta 的文件权限均为 600（仅所有者可读写）
