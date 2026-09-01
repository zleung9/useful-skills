---
name: wechat-article-extractor
description: |
  从微信公众号文章链接中提取正文内容（文字+图片）并转换为 Markdown 文档。

  **当以下情况时使用此 Skill**：
  (1) 用户发来微信公众号文章链接，要求"保存"、"下载"、"转成文档"
  (2) 用户发来微信文章链接，要求"提取内容"
  (3) 用户说"把这个网页转成 markdown"且链接是 mp.weixin.qq.com

  **NOT for**：
  - 非微信公众号内容（用 web_fetch 或其他方式）
  - 需要登录才能访问的内容
  - 视频号内容（不同格式）
metadata:
  {
    "openclaw":
      {
        "emoji": "📰",
        "requires": { "bins": ["curl", "python3"] },
        "install":
          [
            {
              "id": "pip-html2text",
              "kind": "pip",
              "formula": "html2text",
              "label": "pip install html2text (--break-system-packages if needed)",
            }
          ],
        "homepage": "https://github.com/openclaw/openclaw"
      }
  }
---

# WeChat Article Extractor Skill

将微信公众号文章完整提取为本地 Markdown 文件（含图片）。

## 核心流程（4 步）

```
1. 获取原始 HTML     → curl 带浏览器 UA
2. 提取正文内容      → 正则定位 js_content，提取文字+图片 URL
3. 下载图片（重点）   → 把 URL 里的 /640 替换为 /0 获取原始分辨率
4. 转换为 Markdown   → html2text + 正则清洗
```

---

## Step 1：获取原始 HTML

微信公众号内容是**动态渲染**的，直接 `web_fetch` 只能拿到 JS 片段，必须用 curl：

```bash
curl -sL "https://mp.weixin.qq.com/s/文章ID" \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  -o /tmp/wechat_article.html
```

**必须带 User-Agent**，否则微信服务器可能拒绝请求或返回简化版页面。

---

## Step 2：提取正文内容

文章正文在 HTML 的 `id="js_content"` 和 `id="js_pc_qr_code"` 之间：

```python
import re

with open('/tmp/wechat_article.html', 'r', encoding='utf-8', errors='replace') as f:
    html = f.read()

m = re.search(r'id="js_content"(.*?)id="js_pc_qr_code"', html, re.DOTALL)
content = m.group(1)
```

**提取所有图片 URL**（按出现顺序）：
```python
img_urls = re.findall(r'data-src="(https://mmbiz[^"]+)"', content)
```

---

## Step 3：下载图片（⚠️ 关键）

### 教训：URL 里的 `/640` 是缩放参数

```
.../图片ID/640?wx_fmt=png   → 微信按 640px 宽度缩放，可能只有几百字节
.../图片ID/0?wx_fmt=png     → 原始分辨率，可能是几百 KB 甚至更大
```

**每个图片 URL 都要把 `/640` 替换为 `/0`**：
```python
url_orig = url.replace('/640?', '/0?')   # 注意替换的是 "/640?" 整个模式
# 如果 URL 里没有 /640（比如本身就是 /0 或其他尺寸），保持不变
```

### 教训：串行下载，不要并行

之前并行下载 7 张图，部分图片因 CDN 并发限制返回不完整数据（243 字节的损坏文件）。

**正确做法：串行下载，逐一验证**
```bash
for url in "${img_urls[@]}"; do
  url_orig="${url/\/640/\/0}"   # Bash 字符串替换
  curl -sL "$url_orig" -o "$(basename "$url").png"
done
```

### 教训：下载后必须验证

**不要只看文件大小**，要用 `file` 命令验证：
```bash
file img_01.png
# 正常：PNG image data, 2316 x 1248, 8-bit/color RGB
# 损坏：PNG image data, 691 x 10, 8-bit/color RGBA  （691x10 是微信占位图）
```

如果图片尺寸异常小（如 691x10），说明微信 CDN 对该图片本身只存了缩略图，尝试其他尺寸参数：
```bash
# 尝试 /0（原始）、/1080（高分辨率）、不带数字（原始）
curl -sL "${url_orig}" -o img.png
```

---

## Step 4：转换为 Markdown

### 修复图片 URL 后转换为 Markdown
```python
from html2text import html2text

# 把 <img data-src="URL"> 替换为 ![图片](URL)
def img_to_md(m):
    url = m.group(1)
    return f'\n\n![图片]({url})\n\n'

content_with_imgs = re.sub(
    r'<img[^>]+data-src="(https://mmbiz[^"]+)"[^>]*>',
    img_to_md,
    content
)

md = html2text(content_with_imgs)
```

### 清洗残留内容
```python
# 去掉顶部隐藏样式块
md = re.sub(r'^style="visibility: hidden; opacity: 0; "\s*\n', '', md)
# 合并多余空行
md = re.sub(r'\n{3,}', '\n\n', md)
# 去掉底部微信公众号水印
md = re.sub(r'\n预览时标签不可点\s*$', '', md)
```

---

## 完整脚本

```python
#!/usr/bin/env python3
"""
wechat_article_extractor.py
从微信公众号文章提取正文和图片，保存为 Markdown 文件
"""
import re, os, sys, subprocess
from html2text import html2text

def extract(url, output_dir='./wechat_article'):
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, 'article.html')

    # Step 1: fetch HTML
    subprocess.run([
        'curl', '-sL', url,
        '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        '-o', html_path
    ], check=True)

    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    # Step 2: extract content
    m = re.search(r'id="js_content"(.*?)id="js_pc_qr_code"', html, re.DOTALL)
    if not m:
        raise ValueError("无法找到文章正文区域（id=js_content）")
    content = m.group(1)

    # Extract image URLs in order
    img_urls = re.findall(r'data-src="(https://mmbiz[^"]+)"', content)

    # Step 3: fix image URLs (replace /640 with /0 for original resolution)
    fixed_urls = []
    for url in img_urls:
        # Replace /640? with /0? to get original size
        fixed = re.sub(r'/(\d+)\?wx_fmt=', r'/0?wx_fmt=', url)
        fixed_urls.append(fixed)

    # Step 4: replace img tags with markdown images
    def img_to_md(m):
        return f'\n\n![图片]({m.group(1)})\n\n'
    content_f = re.sub(r'<img[^>]+data-src="(https://mmbiz[^"]+)"[^>]*>', img_to_md, content)

    # Step 5: convert to markdown
    md = html2text(content_f)

    # Step 6: clean up
    md = re.sub(r'^style="visibility: hidden; opacity: 0; "\s*\n', '', md)
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'\n预览时标签不可点\s*$', '', md)

    # Save markdown
    md_path = os.path.join(output_dir, 'README.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md)

    # Step 7: download images serially, verify each
    downloaded = []
    for i, url in enumerate(fixed_urls, 1):
        ext = 'jpg' if 'jpeg' in url else 'png'
        fname = f'img_{i:02d}.{ext}'
        fpath = os.path.join(output_dir, fname)

        subprocess.run(['curl', '-sL', url, '-o', fpath], check=True)

        # Verify with file command
        result = subprocess.run(['file', fpath], capture_output=True, text=True)
        if 'PNG image data' in result.stdout or 'JPEG image' in result.stdout:
            downloaded.append(fname)
            print(f'  ✅ {fname} ({os.path.getsize(fpath)//1024}KB)')
        else:
            print(f'  ❌ {fname} 可能是损坏文件: {result.stdout.strip()}')

    print(f'\n完成：{len(downloaded)}/{len(fixed_urls)} 张图片已下载')
    print(f'输出目录：{output_dir}')
    return md_path, downloaded

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else input('输入微信文章链接：')
    out = sys.argv[2] if len(sys.argv) > 2 else None
    extract(url, out)
```

---

## 故障排除

| 症状 | 原因 | 解决方法 |
|------|------|----------|
| `web_fetch` 只返回 JS 片段 | 微信内容动态渲染 | 用 curl 而非 web_fetch |
| 图片只有几百字节 | CDN 返回缩略图 | 把 URL 里的 `/640` 改为 `/0` |
| 并行下载部分图片损坏 | 微信 CDN 并发限制 | 改串行下载 |
| `html2text` 没安装 | 缺少依赖 | `pip install --break-system-packages html2text` |
| `id="js_content"` 没找到 | 文章结构不同 | 检查 HTML，确认正确的起止位置 |
| 桌面文件夹找不到 | 保存到了 cwd | 用绝对路径指定输出目录 |

---

## ⚠️ Agent 行为约束

1. **每次下载图片都必须验证 `file` 命令输出**，不要只看 ls -lh 大小
2. **串行下载图片**，不要用 & 并行或 xargs -P
3. **替换 /640 为 /0** 是默认操作，不需要用户特别要求
4. **图片保存到与 README.md 同一目录**，用 `img_01.png`、`img_02.jpg` 命名
5. **先把所有图片下载完毕再发送给用户**，不要一边下一边发
