---
name: web-search-academic
description: Academic and reference web search via free JSON APIs — Crossref (papers/DOIs), Semantic Scholar (papers with citation counts), Wikipedia (encyclopedia entries), and DuckDuckGo Instant Answer. Use for scholarly lookups, finding research papers, DOIs, citation counts, or encyclopedia entries — especially when the built-in WebSearch is unavailable (US-only, hangs from China). For general/everyday web searches (products, news, how-to, anything you'd Google) prefer the web-search-chrome skill instead. Trigger on phrases like "找关于 X 的论文", "search for papers on X", "X 的 DOI/引用数", "查一下 X 的百科", or any academic/reference lookup.
compatibility: Requires python3. Requests go through a local HTTP proxy at http://127.0.0.1:7890 (Clash / verge-mihomo); direct connection works for some APIs on unrestricted networks.
---

# Web Search (Academic & Reference)

用免费 JSON API 做学术与参考类搜索（论文、DOI、引用数、百科条目），替代内置的 `WebSearch` 工具。

## 为什么需要这个 skill

内置 `WebSearch` 仅限美国地区：从中国大陆 IP 调用会无限挂起或被拒绝。本 skill 改用 Crossref、Semantic Scholar、Wikipedia、DuckDuckGo 这几个免费 JSON API 完成学术与参考类搜索，不需要 API Key；请求统一走本地代理，绕过直连受限的问题。注意它的定位是**学术/参考**——查论文、DOI、引用数、百科条目；而事实、产品、新闻、how-to 这类**通用**搜索请用配套的 `web-search-chrome`（真实 Chrome 驱动 Google）。

## 搜索

首选方式是调用打包好的脚本——它会依次查询多个后端、处理重试与错误、返回 JSON：

```bash
{baseDir}/search.py "Polyimide properties"            # 所有后端（默认）
{baseDir}/search.py "Polyimide" --mode general        # 仅 Wikipedia + DuckDuckGo
{baseDir}/search.py "Polyimide" --mode academic       # 仅 Crossref + Semantic Scholar
{baseDir}/search.py "Polyimide" --limit 8             # 每个后端返回更多结果
```

输出是一个 JSON 数组，每条结果形如：

```json
{
  "source": "wikipedia",
  "title": "Polyimide",
  "url": "https://en.wikipedia.org/wiki/Polyimide",
  "snippet": "Polyimide is a polymer containing imide groups..."
}
```

学术结果额外带 `year`、`doi`、`citations` 等字段；某个后端出错时对应一条 `{"source": "...", "error": "..."}`，不会中断整体返回。需要单独控制某个后端时，直接读 `{baseDir}/search.py` 并复用其中的函数，不要在对话里重写一遍。

## 后端选择

| 后端 | 适用 | 注意 |
|------|------|------|
| Wikipedia | 通用知识、百科条目 | 仅限 Wikipedia 内容 |
| DuckDuckGo Instant Answer | 即时摘要 | 很多查询返回空，作补充而非主力 |
| Crossref | 学术论文 / DOI | 需要带 mailto 的礼貌 User-Agent（脚本已处理）；学术搜索优先用它 |
| Semantic Scholar | 学术论文，含引用数 | 速率限制严格，遇 429 脚本会退避重试 |

以下方案已验证不可用，不要再花时间尝试：Google HTML 搜索（JS 重定向）、Bing（跳转 cn.bing.com）、DuckDuckGo HTML/Lite（触发 CAPTCHA）、Brave Search（SSL 被阻断）。

## 抓取网页全文

搜索拿到 URL 后，用 `WebFetch` 获取页面内容并按需提取——snippet 通常不够用：

```
WebFetch({ url: "https://en.wikipedia.org/wiki/Polyimide", prompt: "提取聚酰亚胺的材料特性、应用领域和主要类型" })
```

## 网络与代理

脚本默认通过本地 HTTP 代理 `http://127.0.0.1:7890`（Clash / verge-mihomo）发出请求，目的是绕过直连受限。如果代理没开（脚本返回 `Connection refused`），可以：先确认 Clash 是否在运行；或在校园网等可直连的环境里，把 `search.py` 顶部的 `PROXY_URL` 改为直连。后端调用之间留有 0.5 秒间隔，避免触发限流。

## 使用要点

- 本 skill 专做**学术/参考**搜索（论文、DOI、引用数、百科）；**通用**网络查询（事实、产品、新闻、how-to）请改用 `web-search-chrome`，它用真实 Chrome 跑 Google，覆盖面更广。
- 学术查询优先 `--mode academic`，且 Crossref 比 Semantic Scholar 稳定（后者限流更严）。
- DuckDuckGo 经常无结果，不要当唯一后端；参考类查询用默认的 `all` 模式更保险。
- 拿到 URL 后用 `WebFetch` 取正文，搜索结果的 snippet 一般不够用。
