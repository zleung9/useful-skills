#!/usr/bin/env python3
"""
wechat_article_extractor.py
从微信公众号文章提取正文和图片，保存为 Markdown 文件

用法：
    python3 extract.py <微信文章URL> [输出目录]

示例：
    python3 extract.py "https://mp.weixin.qq.com/s/QELXktggXCQCzlDaj7BQug" ~/Desktop/article
"""
import re, os, sys, subprocess, urllib.parse
from html2text import html2text

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_html(url: str, output_dir: str) -> str:
    """Step 1: 用 curl 获取文章原始 HTML"""
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, "article.html")

    result = subprocess.run(
        ["curl", "-sL", url, "-A", UA, "-o", html_path],
        check=True,
        capture_output=True,
        text=True,
    )
    if not os.path.exists(html_path) or os.path.getsize(html_path) == 0:
        raise ValueError(f"curl 下载失败，URL 可能无效或需要登录：{url}")

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_content(html: str) -> tuple[str, list[str]]:
    """Step 2: 从 HTML 中提取 js_content 正文章节，返回 (content, img_urls)"""
    m = re.search(r'id="js_content"(.*?)id="js_pc_qr_code"', html, re.DOTALL)
    if not m:
        raise ValueError("无法找到 id=js_content，请确认是微信公众号文章链接")

    content = m.group(1)

    # 按出现顺序提取所有图片 URL（原始顺序很重要，对应图注）
    img_urls = re.findall(r'data-src="(https://mmbiz[^"]+)"', content)

    return content, img_urls


def fix_img_url(url: str) -> str:
    """
    Step 3: 修复图片 URL 分辨率

    关键：微信 CDN 的 /640 参数表示按 640px 缩放，
          换成 /0 获取原始分辨率（可能是几 MB）。

    注意：URL 格式是 .../图片ID/640?wx_fmt=png&from=appmsg
          需要把 /640? 替换为 /0?
    """
    # 处理两种常见格式：
    # 1. .../xxx/640?wx_fmt=png&from=appmsg
    # 2. .../xxx/640?wx_fmt=png
    fixed = re.sub(r'/(\d+)\?wx_fmt=', r'/0?wx_fmt=', url)
    return fixed


def verify_image(path: str) -> str:
    """用 file 命令验证图片有效性，返回文件类型描述"""
    result = subprocess.run(["file", path], capture_output=True, text=True)
    return result.stdout.strip()


def download_images(img_urls: list[str], output_dir: str) -> list[tuple[int, str, str]]:
    """
    Step 4: 串行下载所有图片，逐一验证

    返回：[(序号, 文件名, 验证结果), ...]
    """
    downloaded = []
    for i, raw_url in enumerate(img_urls, 1):
        url = fix_img_url(raw_url)

        # 判断扩展名
        if "jpeg" in url.lower() or "jpg" in url.lower():
            ext = "jpg"
        else:
            ext = "png"
        fname = f"img_{i:02d}.{ext}"
        fpath = os.path.join(output_dir, fname)

        # 串行下载
        subprocess.run(["curl", "-sL", url, "-o", fpath], check=True)

        # 验证
        info = verify_image(fpath)
        size_kb = os.path.getsize(fpath) // 1024

        status = "✅" if ("PNG image" in info or "JPEG image" in info) and size_kb > 1 else "❌"
        print(f"  {status} {fname} ({size_kb}KB) - {info}")
        downloaded.append((i, fname, info))

    return downloaded


def to_markdown(content: str) -> str:
    """Step 5: HTML → Markdown"""
    # 1. 把 <img data-src="URL"> 替换为 ![图片](URL)
    def img_to_md(m):
        return f"\n\n![图片]({m.group(1)})  \n\n"

    content_md = re.sub(
        r'<img[^>]+data-src="(https://mmbiz[^"]+)"[^>]*>',
        img_to_md,
        content,
    )

    # 2. 去掉 inline style/script
    content_md = re.sub(r'<script[^>]*>.*?</script>', "", content_md, flags=re.DOTALL)
    content_md = re.sub(r'<style[^>]*>.*?</style>', "", content_md, flags=re.DOTALL)

    # 3. 转 Markdown
    md = html2text(content_md)

    # 4. 清理残留
    md = re.sub(r'^style="visibility: hidden; opacity: 0; "\s*\n', "", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"\n预览时标签不可点\s*$", "", md)
    md = md.strip() + "\n"

    return md


def extract(url: str, output_dir: str = None) -> str:
    """
    主流程：提取微信文章到本地文件夹

    返回：输出目录路径
    """
    # 解析 URL 获取文章标识作为默认目录名
    parsed = urllib.parse.urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    article_name = path_parts[-1] if path_parts else "article"
    output_dir = output_dir or f"./{article_name}"

    print(f"\n📰 开始提取：{url}")
    print(f"📁 输出目录：{output_dir}\n")

    # Step 1: 获取 HTML
    print("⬇️  获取页面 HTML...")
    html = fetch_html(url, output_dir)
    print(f"  ✅ HTML 大小：{len(html)//1024}KB")

    # Step 2: 提取内容
    print("\n🔍 提取正文和图片...")
    content, img_urls = extract_content(html)
    print(f"  ✅ 正文字符数：{len(content)//1024}KB")
    print(f"  ✅ 图片数量：{len(img_urls)} 张")

    # Step 3: 下载图片
    print("\n⬇️  下载图片（串行，逐张验证）...")
    downloaded = download_images(img_urls, output_dir)
    ok_count = sum(1 for _, _, info in downloaded
                    if ("PNG image" in info or "JPEG image" in info))
    print(f"\n  📊 图片：{ok_count}/{len(img_urls)} 张验证通过")

    # Step 4: 转换为 Markdown
    print("\n📝 转换为 Markdown...")
    md = to_markdown(content)
    md_path = os.path.join(output_dir, "README.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  ✅ 已保存：{md_path}")

    # Step 5: 汇总
    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 提取完成
   文章：{url}
   目录：{output_dir}
   Markdown：README.md
   图片：{ok_count}/{len(img_urls)} 张
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")

    return output_dir


if __name__ == "__main__":
    try:
        url = sys.argv[1]
    except IndexError:
        print("用法：python3 extract.py <微信文章URL> [输出目录]")
        sys.exit(1)

    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        extract(url, output_dir)
    except Exception as e:
        print(f"❌ 提取失败：{e}")
        sys.exit(1)
