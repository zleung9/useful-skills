#!/usr/bin/env node
// Download a URL as a file via CDP download behavior
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const url = process.argv[2];
const outDir = process.argv[3] || "/tmp/papers";
fs.mkdirSync(outDir, { recursive: true });

const b = await puppeteer.connect({ browserURL: "http://localhost:9222", defaultViewport: null });
const page = (await b.pages()).at(-1) || await b.newPage();
const client = await page.target().createCDPSession();
await client.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: outDir });
await client.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: outDir, eventsEnabled: true });

const before = new Set(fs.readdirSync(outDir));
console.log("navigating:", url);
const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => { console.log("goto error:", e.message); return null; });
if (resp) console.log("status:", resp.status(), "type:", resp.headers()["content-type"]);

// wait for a new file to appear
for (let i = 0; i < 20; i++) {
  await new Promise(r => setTimeout(r, 500));
  const now = fs.readdirSync(outDir);
  const fresh = now.filter(f => !before.has(f) && !f.startsWith(".") && !f.endsWith(".crdownload"));
  if (fresh.length) {
    console.log("downloaded:", JSON.stringify(now.filter(f => !before.has(f))));
    break;
  }
}
const final = fs.readdirSync(outDir).filter(f => !before.has(f));
console.log("new files:", JSON.stringify(final));
await b.disconnect();
