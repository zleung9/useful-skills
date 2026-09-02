#!/usr/bin/env node
/**
 * google-search.mjs — General web search via Chrome + Google.
 *
 * Connects to Chrome with remote debugging on :9222 (auto-starts it via the
 * sibling browser-tools skill if needed), opens google.com, types the query,
 * submits, and extracts organic results (title, real URL from <cite>, snippet).
 *
 * Usage:  node google-search.mjs "search query" [--limit N]
 * Output: JSON to stdout.
 */

import puppeteer from "puppeteer-core";
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BROWSER_URL = "http://localhost:9222";
const BROWSER_TOOLS_START = path.join(__dirname, "..", "browser-tools", "browser-start.js");
const NAV_TIMEOUT = 30000;

async function connect() {
  try {
    return await puppeteer.connect({ browserURL: BROWSER_URL, defaultViewport: null });
  } catch {}
  // Not running — try launching via the sibling browser-tools skill.
  if (existsSync(BROWSER_TOOLS_START)) {
    console.error("Chrome not detected on :9222 — starting via browser-tools...");
    try { execSync(`node "${BROWSER_TOOLS_START}"`, { stdio: "inherit" }); } catch {}
    try {
      return await puppeteer.connect({ browserURL: BROWSER_URL, defaultViewport: null });
    } catch {}
  }
  console.error(
    "Could not connect to Chrome on :9222.\n" +
    "Start it with the browser-tools skill (browser-start.js) or launch Chrome with\n" +
    "  --remote-debugging-port=9222 --user-data-dir=\"$HOME/.cache/browser-tools\""
  );
  process.exit(1);
}

// --- parse args ---
const args = process.argv.slice(2);
let query = "";
let limit = 10;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--limit" || args[i] === "-l") {
    limit = parseInt(args[++i], 10) || 10;
  } else if (args[i] === "--help" || args[i] === "-h") {
    console.log('Usage: google-search.mjs "search query" [--limit N]');
    process.exit(0);
  } else {
    query = (query ? query + " " : "") + args[i];
  }
}
if (!query) {
  console.log('Usage: google-search.mjs "search query" [--limit N]');
  process.exit(1);
}

const browser = await connect();
const page = await browser.newPage();
try {
  await page.goto("https://www.google.com", { waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT });

  // Type the query (real key events work with Google's React-controlled input)
  await page.focus('textarea[name="q"], input[name="q"]');
  await page.type('textarea[name="q"], input[name="q"]', query, { delay: 15 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT }),
    page.keyboard.press("Enter"),
  ]);
  await new Promise((r) => setTimeout(r, 1500)); // let results render

  const data = await page.evaluate((lim) => {
    const results = [];
    const seen = new Set();
    // Google wraps the real URL in a google.com/goto redirect token, so read
    // it from the <cite> element inside each result block instead of the <a href>.
    document.querySelectorAll("a h3, h3 a, h3").forEach((h) => {
      const a = h.closest("a") || h.querySelector("a") || (h.parentElement && h.parentElement.querySelector("a"));
      if (!a) return;
      let block = h;
      for (let i = 0; i < 8 && block; i++) block = block.parentElement;
      if (!block) return;
      const cite = block.querySelector("cite");
      const realUrl = cite ? cite.textContent.trim() : null;
      if (!realUrl || !/^https?:\/\//.test(realUrl) || seen.has(realUrl)) return;
      seen.add(realUrl);
      // Snippet: longest leaf-ish text in the block, excluding the title/url line.
      let snippet = "";
      block.querySelectorAll("span, div").forEach((el) => {
        const t = el.textContent.trim();
        if (
          t.length > snippet.length && t.length < 400 &&
          !t.startsWith(realUrl) && t !== h.textContent.trim() &&
          !el.querySelector("cite")
        ) {
          snippet = t;
        }
      });
      results.push({ title: h.textContent.trim(), url: realUrl, snippet: snippet.slice(0, 240) });
    });
    return { count: results.length, results: results.slice(0, lim) };
  }, limit);

  data.query = query;
  console.log(JSON.stringify(data, null, 2));
} finally {
  await page.close().catch(() => {});
  await browser.disconnect();
}
