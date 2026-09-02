---
name: web-search-chrome
description: General-purpose web search using a real Chrome browser and Google, via the Chrome DevTools Protocol. Returns organic search results (title, URL, snippet) as JSON. Use this for everyday web lookups — facts, products, news, documentation, people, "how to" questions, or anything you'd type into Google — especially when the built-in WebSearch tool is unavailable (it's US-only and hangs from China). For scholarly lookups (papers, DOIs, citation counts) use the web-search-academic skill instead. Trigger on phrases like "搜索/查一下/搜一下 X", "search the web for X", "google X", "look up X online", or any request needing current information from the general web.
compatibility: Requires Node.js and puppeteer-core (run `npm install` in the skill dir once). Drives Chrome with remote debugging on port 9222; Chrome is auto-started via the sibling browser-tools skill, or any Chrome launched with --remote-debugging-port=9222. Needs network access to google.com (works through a local proxy such as Clash/verge-mihomo).
---

# Web Search (Chrome + Google)

用真实 Chrome 浏览器驱动 Google 搜索，返回有机搜索结果（标题、URL、摘要）的 JSON。这是一个**通用**网络搜索引擎——适合查事实、产品、新闻、文档、"怎么做"之类你平时会直接 google 的东西。

## 为什么需要这个 skill

内置 `WebSearch` 仅限美国地区，从中国大陆调用会无限挂起。本 skill 改用真实 Chrome 打开 google.com、键入关键词、抓取结果页，绕开 WebSearch 的地区限制，也绕开 Google HTML 搜索的 JS 重定向问题（直接 curl Google 拿不到可解析的结果）。与之配套的 `web-search-chrome` 处理通用搜索，而学术/论文查询走 `web-search-academic`（Crossref / Semantic Scholar）。

## 一次性安装

```bash
cd {baseDir}/web-search-chrome && npm install
```

只装 `puppeteer-core`（很轻，不下载 Chromium——本 skill 连接的是已运行的 Chrome）。

## 搜索

```bash
{baseDir}/google-search.mjs "Polyimide properties"            # 默认最多 10 条
{baseDir}/google-search.mjs "best mechanical keyboard 2025" --limit 5
```

脚本会：连接 `:9222` 上的 Chrome（没在跑就用相邻的 browser-tools skill 自动启动）→ 新开标签页打开 google.com → 键入查询并提交 → 抓取有机结果 → 输出 JSON 后关闭标签页。输出形如：

```json
{
  "query": "Polyimide properties",
  "count": 6,
  "results": [
    {
      "title": "Polyimide - Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Polyimide",
      "snippet": "Polyimide is a polymer containing imide groups..."
    }
  ]
}
```

`url` 取自结果块的 `<cite>` 元素——Google 现在把链接 `href` 伪装成 `google.com/goto?url=...` 的跳转 token，直接读 `href` 拿不到真实地址，必须读 `<cite>`。这一步已由脚本处理。

## Chrome 的启动与管理

脚本需要 Chrome 以远程调试模式监听 `:9222`。如果检测不到，它会尝试调用相邻的 `browser-tools/browser-start.js` 自动启动；若该 skill 也不在，请手动启动：

```bash
# 方式一：用 browser-tools skill（推荐，会建独立 profile，不碰你的常用 profile）
{baseDir}/../browser-tools/browser-start.js

# 方式二：直接启动 Chrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir="$HOME/.cache/browser-tools" \
  --no-first-run --no-default-browser-check &
```

需要可视化调试（截图、点选元素）时，用 browser-tools skill 的 `browser-screenshot.js` / `browser-pick.js`。

## 网络

Chrome 的流量需要能访问 google.com——在中国大陆通常要走本地代理（如 Clash/verge-mihomo 监听 `127.0.0.1:7890`）。让 Chrome 走系统代理即可；若代理未开，google.com 会连不上。

## 使用要点

- 通用查询（事实、产品、新闻、how-to）用本 skill；论文/DOI/引用数用 `web-search-academic`。
- 摘要只有一两句；要正文就拿到 `url` 后用 browser-tools 的 `browser-content.js` 或 `WebFetch` 抓取全文。
- Google 偶尔返回 AI 概览或"人们还问"，脚本只取带真实 URL 的有机结果，这些干扰块会被自动跳过。
- 结果条数受 Google 页面布局影响，`--limit` 只是上限。
