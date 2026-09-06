#!/usr/bin/env node
// fetch_feed.mjs — capture the X.com home feed (Following tab) with Playwright.
//
// X virtualizes the feed DOM, so we extract incrementally while scrolling.
// The persistent profile (browser-profile/) keeps the login; if it expires,
// run `node scripts/x-login.mjs` first.
//
// Usage: node scripts/fetch_feed.mjs [--scrolls 16] [--wait 2200] [--out data/feed.json] [--merge]
import { mkdirSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { launchX } from "./pw-common.mjs";

const argv = process.argv.slice(2);
function getArg(name, dflt) {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
}
const SCROLLS = parseInt(getArg("--scrolls", "16"), 10);
const WAIT = parseInt(getArg("--wait", "2200"), 10);
const OUT = resolve(process.cwd(), getArg("--out", "data/feed.json"));
const log = (m) => process.stderr.write(`[feed] ${m}\n`);

const ctx = await launchX({ headed: true });
let exitCode = 0;
try {
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto("https://x.com/home", { waitUntil: "domcontentloaded", timeout: 60000 });

  // login check (X redirects /home → /i/flow/login when logged out)
  await page.waitForTimeout(4000);
  if (/login|flow/i.test(page.url())) {
    log("NOT_LOGGED_IN — run: node scripts/x-login.mjs");
    exitCode = 2;
  } else {
    await capture(ctx, page);
  }
} finally {
  await ctx.close();
}
process.exit(exitCode);

async function capture(ctx, page) {

  // switch to Following tab if needed
  const tabInfo = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('[role="tab"]'));
    const cur = btns.find((t) => t.getAttribute("aria-selected") === "true");
    return { tabs: btns.map((t) => t.textContent.trim()), current: cur ? cur.textContent.trim() : null };
  });
  log("tabs: " + JSON.stringify(tabInfo));
  if (tabInfo.current && !/following/i.test(tabInfo.current)) {
    const switched = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('[role="tab"]'));
      const f = btns.find((t) => /following/i.test(t.textContent));
      if (f) { f.click(); return true; }
      return false;
    });
    log("switched to Following tab: " + switched);
    await page.waitForTimeout(3500);
  }

  // wait for first articles
  let n = 0;
  for (let i = 0; i < 30; i++) {
    n = await page.locator("article").count();
    if (n > 0) break;
    await page.waitForTimeout(1000);
  }
  log(`initial articles in DOM: ${n}`);

  // in-page extractor (same DOM logic as the puppeteer version)
  const extract = () =>
    page.evaluate(() => {
      const out = [];
      for (const art of document.querySelectorAll("article")) {
        try {
          const statusA = Array.from(art.querySelectorAll('a[href*="/status/"]'))
            .map((a) => a.getAttribute("href"))
            .find((h) => /\/status\/\d+/.test(h || ""));
          if (!statusA) continue;
          const id = (statusA.match(/\/status\/(\d+)/) || [])[1];
          if (!id) continue;

          let handle = "", name = "";
          const profA = Array.from(art.querySelectorAll("a[href]")).find((a) => {
            const h = a.getAttribute("href") || "";
            return /^\/[A-Za-z0-9_]{1,15}$/.test(h) && h !== "/home";
          });
          if (profA) {
            const t = (profA.textContent || "").trim();
            const parts = t.split(/\s*\n\s*/).map((s) => s.trim()).filter(Boolean);
            for (const part of parts) {
              if (part.startsWith("@")) handle = part.replace(/^@/, "");
              else if (!name) name = part;
            }
            if (!handle) handle = (profA.getAttribute("href") || "").replace(/^\//, "");
          }

          const txt = art.querySelector('[data-testid="tweetText"]');
          const text = txt ? txt.innerText.trim() : "";
          const timeEl = art.querySelector("a time");
          const time = timeEl ? timeEl.getAttribute("datetime") || "" : "";
          const isRT = /Repost(ed)?\b|retweeted|转推/i.test(art.innerText.slice(0, 80));

          out.push({ id, handle, name, text, time, link: "https://x.com" + statusA.split("?")[0], rt: isRT });
        } catch {}
      }
      return out;
    });

  const byId = new Map();
  async function drain() {
    const list = await extract();
    let added = 0;
    for (const t of list) {
      if (!byId.has(t.id)) { byId.set(t.id, t); added++; }
      else {
        const old = byId.get(t.id);
        if (t.text.length > old.text.length) old.text = t.text;
      }
    }
    return { total: byId.size, added };
  }

  let first = await drain();
  log(`captured: ${first.total}`);

  let same = 0;
  for (let i = 0; i < SCROLLS; i++) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(WAIT);
    const r = await drain();
    log(`scroll ${i + 1}/${SCROLLS}: +${r.added}, total ${r.total}`);
    if (r.added === 0) {
      same++;
      if (same >= 4) { log("feed exhausted (4 scrolls, no new)"); break; }
    } else same = 0;
  }

  let tweets = [...byId.values()];
  if (existsSync(OUT) && argv.includes("--merge")) {
    try {
      const prev = JSON.parse(readFileSync(OUT, "utf8"));
      const m = new Map(tweets.map((t) => [t.id, t]));
      for (const t of prev.tweets || []) if (!m.has(t.id)) m.set(t.id, t);
      tweets = [...m.values()];
      log(`merged with previous file -> ${tweets.length}`);
    } catch {}
  }

  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify({ fetchedAt: new Date().toISOString(), count: tweets.length, tweets }, null, 2));
  log(`saved ${tweets.length} tweets -> ${OUT}`);
}
