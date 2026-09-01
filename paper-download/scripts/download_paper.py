#!/usr/bin/env python3
"""
Download a subscription-journal PDF via a real Chrome session (Playwright)
that exports its cookies, then curls the publisher's PDF endpoint.

Why this exists: Playwright's `expect_download` never fires for inline-rendered
PDFs (Chrome shows them in its viewer), and `Page.printToPDF` only captures the
single viewport page. Exporting the authenticated session's cookies + UA and
curling the PDF endpoint with `--noproxy '*'` is the reliable save method.

Usage:
    python3 download_paper.py --doi 10.1021/acs.jpclett.5c00658 \
        --out ~/Downloads/slug/slug.pdf \
        --profile ~/.claude/jobs/_paperdl/chrome_profile

    # Or supply a known PDF URL directly (skips anchor discovery):
    python3 download_paper.py --landing https://pubs.acs.org/doi/10.1021/... \
        --pdf-url https://pubs.acs.org/jpclcd/article-pdf/.../x.pdf \
        --out ~/Downloads/slug/slug.pdf

Exits 0 on a verified PDF (>50KB, magic %PDF), nonzero otherwise.
Prints RESULT=PDF_OK / RESULT=NO_PDF / RESULT=BAD_PDF on the last line.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time

# --- Strip ALL proxy env vars BEFORE importing playwright ---
# Local Clash SOCKS/system proxy (127.0.0.1:7897) would otherwise reroute the
# browser away from the campus-recognized egress.
for _k in list(os.environ.keys()):
    if _k.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy") \
            or _k.lower().endswith("_proxy"):
        os.environ.pop(_k, None)

from playwright.sync_api import sync_playwright  # noqa: E402

CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MIN_PDF_BYTES = 50000
PDF_MAGIC = b"%PDF-"


def is_real_pdf(path):
    if not path or not os.path.exists(path):
        return False
    if os.path.getsize(path) < MIN_PDF_BYTES:
        return False
    with open(path, "rb") as f:
        return f.read(5) == PDF_MAGIC


def write_netscape_jar(cookies, path):
    with open(path, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            dom = c.get("domain", "")
            f.write("\t".join([
                dom,
                "TRUE" if dom.startswith(".") else "FALSE",
                c.get("path", "/"),
                "TRUE" if c.get("secure") else "FALSE",
                str(int(c.get("expires", 0) or 0)),
                c.get("name", ""),
                c.get("value", ""),
            ]) + "\n")


def origin_of(url):
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else url


def wait_cloudflare(page, timeout=120):
    """Poll page title until 'Just a moment' / 'moment' disappears."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            title = (page.title() or "").lower()
        except Exception:
            title = ""
        if "just a moment" not in title and "moment" not in title:
            return True
        time.sleep(1)
    return False


def find_pdf_url(page, origin):
    """Discover the publisher PDF endpoint from landing-page anchors."""
    try:
        anchors = page.eval_on_selector_all(
            "a",
            "els=>els.map(e=>({href:e.href||'',text:(e.innerText||'').trim()}))")
    except Exception:
        return None
    # Prefer canonical article-pdf / doi/pdf endpoints
    for a in anchors:
        href = a.get("href", "")
        if "/article-pdf/" in href or "/doi/pdf/" in href or "/doi/pdf" in href:
            if href.startswith("/"):
                href = origin + href
            if href.lower().endswith(".pdf") or "article-pdf" in href:
                return href
    # Fallback: any anchor whose text says "PDF" / "Open PDF"
    for a in anchors:
        href = a.get("href", "")
        text = (a.get("text") or "").lower()
        if ("pdf" in text or "open pdf" in text) and href.endswith(".pdf"):
            if href.startswith("/"):
                href = origin + href
            return href
    return None


def has_access(page):
    """Heuristic: institution-recognized if footer mentions '<INST> user' and
    no paywall markers dominate. Returns (access_ok, needs_manual_login)."""
    try:
        body = page.locator("body").inner_text(timeout=8000).lower()
    except Exception:
        return False, False
    paywall = any(m in body for m in [
        "purchase access", "get access", "buy this article",
        "subscription required", "sign in to", "log in to"])
    inst = bool(re.search(r"by\s+\w+\s+user", body))  # "by XIAMEN UNIV user"
    has_content = any(w in body for w in ["abstract", "introduction", "received"])
    if inst and has_content and not paywall:
        return True, False
    if paywall and not inst:
        return False, True
    return has_content, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doi", help="DOI (used to build the ACS landing URL)")
    ap.add_argument("--landing", help="Full landing-page URL (overrides --doi)")
    ap.add_argument("--pdf-url", help="Known PDF endpoint (skips discovery)")
    ap.add_argument("--out", required=True, help="Output PDF path")
    ap.add_argument("--profile", required=True, help="Persistent Chrome profile dir")
    ap.add_argument("--cookies-jar", help="Where to write the Netscape cookie jar")
    ap.add_argument("--keep-open", type=int, default=10, help="Seconds to keep browser open at end")
    args = ap.parse_args()

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    # Remove any stale stub before this run so a failed curl can't fool verification.
    if os.path.exists(args.out):
        os.remove(args.out)

    cookies_jar = args.cookies_jar or os.path.join(out_dir, "_cookies.txt")

    landing = args.landing
    if not landing and args.doi:
        landing = "https://pubs.acs.org/doi/" + args.doi.lstrip()
    if not landing:
        sys.exit("ERROR: supply --doi or --landing")

    origin = origin_of(landing)

    p = sync_playwright().start()
    ctx = None
    try:
        launch_kwargs = dict(
            user_data_dir=args.profile,
            headless=False,
            no_viewport=True,
            args=["--no-proxy-server",
                  "--disable-blink-features=AutomationControlled"],
        )
        if os.path.exists(CHROME_APP):
            launch_kwargs["channel"] = "chrome"
            print("CHANNEL=chrome (real Google Chrome)", flush=True)
        else:
            print("CHANNEL=chromium (real Chrome NOT found)", flush=True)
        os.makedirs(args.profile, exist_ok=True)
        ctx = p.chromium.launch_persistent_context(**launch_kwargs)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 1. Navigate to landing page; clear Cloudflare.
        print(">>> goto landing:", landing, flush=True)
        try:
            page.goto(landing, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print("goto err (will still wait):", repr(e)[:120], flush=True)
        wait_cloudflare(page)
        try:
            page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            pass
        time.sleep(2)

        # 2. Confirm institutional access.
        access_ok, needs_login = has_access(page)
        print("ACCESS_OK=", access_ok, "NEEDS_MANUAL_LOGIN=", needs_login, flush=True)
        if needs_login:
            print("PAYWALL: institutional login required — hand the CARSI login "
                  "page in the Chrome window to the USER; do not enter credentials.",
                  flush=True)
            print("RESULT=NEEDS_MANUAL_LOGIN", flush=True)
            return 3

        # 3. Find the PDF endpoint (or use the one supplied).
        pdf_url = args.pdf_url or find_pdf_url(page, origin)
        if not pdf_url:
            print("NO_PDF_URL_FOUND on landing page", flush=True)
            print("RESULT=NO_PDF", flush=True)
            return 2
        if pdf_url.startswith("/"):
            pdf_url = origin + pdf_url
        print("PDF_URL=", pdf_url, flush=True)

        # 4. Export cookies + UA.
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        try:
            ua = page.evaluate("navigator.userAgent")
        except Exception:
            pass
        try:
            cookies = ctx.cookies(origin)
            write_netscape_jar(cookies, cookies_jar)
            print("COOKIES_JAR=", cookies_jar, "count=", len(cookies), flush=True)
        except Exception as e:
            print("cookies err:", repr(e)[:120], flush=True)

        # 5. curl the PDF endpoint with the session cookies.
        cmd = [
            "curl", "-sL", "--noproxy", "*",
            "-A", ua,
            "-b", cookies_jar,
            "-e", landing,
            "-o", args.out,
            pdf_url,
        ]
        print(">>> curl PDF endpoint", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print("curl rc=", r.returncode, "stderr=", (r.stderr or "")[:200], flush=True)

        if is_real_pdf(args.out):
            size = os.path.getsize(args.out)
            print("RESULT=PDF_OK size=%d" % size, flush=True)
            return 0

        # 6. Fallback: in-page fetch() -> base64 (uses same-origin auth).
        print(">>> fallback: in-page fetch()", flush=True)
        try:
            js = """async (u) => {
                const r = await fetch(u, {credentials:'include'});
                const buf = await r.arrayBuffer();
                const bytes = new Uint8Array(buf);
                let bin = '';
                const chunk = 0x8000;
                for (let i = 0; i < bytes.length; i += chunk)
                    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                return btoa(bin);
            }"""
            b64 = page.evaluate(js, pdf_url)
            data = base64.b64decode(b64)
            with open(args.out, "wb") as f:
                f.write(data)
            print("FETCH_FALLBACK wrote size=", len(data), flush=True)
            if is_real_pdf(args.out):
                print("RESULT=PDF_OK (via fetch fallback)", flush=True)
                return 0
        except Exception as e:
            print("fetch fallback err:", repr(e)[:120], flush=True)

        print("RESULT=BAD_PDF", flush=True)
        return 1
    finally:
        time.sleep(args.keep_open)
        try:
            if ctx is not None:
                ctx.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
