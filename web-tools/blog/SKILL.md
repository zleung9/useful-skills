---
name: blog
description: Create an HTML blog post and publish it. Generates a styled HTML page from the user's content, saves it to ~/blog-server/blog/, regenerates manifest.json, rsyncs to claw server, and git-pushes to GitHub. Use when user says blog this / publish blog / add to blog / post blog / 写博客 / 发博客.
---

# blog

When invoked, create and publish an HTML blog post.

## Input

The skill args contain the **content description** — what the blog post should be about. It may be:
- A topic or summary the user wants turned into a full HTML page
- Raw HTML content the user already wrote
- A file path whose content should be turned into a blog post

## Steps

### 1. Generate the HTML page

Create a self-contained HTML file with the content. The page should:

- Include `<!DOCTYPE html>` and proper `<head>` with charset utf-8, viewport meta
- Have a clean, readable style (similar to the blog index page — system font stack, max-width 720px, good typography)
- Include a `<title>` tag — this is extracted by `gen-manifest.sh` for the index listing
- Be fully self-contained (inline CSS, no external dependencies unless user-provided)

**Filename convention:** Use `YYYY-MM-DD-short-slug.html` format based on today's date and the post topic. The date prefix is used by the index for sorting.

Save the file to `~/blog-server/blog/<filename>.html`.

### 2. Regenerate the manifest

Run the manifest generator to update the blog index:

```bash
~/blog-server/gen-manifest.sh
```

This scans all HTML files in `blog/`, extracts `<title>` and date, and writes `manifest.json`.

### 3. Deploy to claw server

Copy the new/changed files to the server:

```bash
scp ~/blog-server/blog/<filename>.html claw:/home/liangzhu/blog-server/blog/
scp ~/blog-server/blog/manifest.json claw:/home/liangzhu/blog-server/blog/
```

No container restart needed — the volume mount means nginx serves the new file immediately.

### 4. Git commit and push

```bash
cd ~/blog-server
git add -A
git commit -m "post: <short-slug>"
git push origin main
```

This keeps the GitHub repo in sync, making it GitHub Pages–compatible.

## Example

User says: "blog this — my electrolyte BO round 4 results show 30% improvement"

You would:
1. Create `~/blog-server/blog/2026-06-24-electrolyte-bo-round4.html` with a styled HTML page summarizing the results
2. Run `~/blog-server/gen-manifest.sh`
3. `scp` the HTML + manifest.json to `claw:/home/liangzhu/blog-server/blog/`
4. `git add -A && git commit -m "post: electrolyte-bo-round4" && git push origin main`

## Notes

- The blog index is at http://10.26.15.53:18800
- The GitHub repo is git@github.com:zleung9/blog.git
- `manifest.json` is auto-generated — never edit it manually
- If the user provides raw HTML, wrap it in the standard page template but preserve their content
- If the user provides a file path, read it and convert to a styled blog page
- NO_PROXY=10.26.15.53 is needed when curling the blog from the local machine
