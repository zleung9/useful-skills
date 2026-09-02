#!/usr/bin/env node
// fetch_papers.mjs
// Fetch configured Nature RSS feeds, parse RSS 1.0 (RDF), dedup by DOI across
// feeds, drop DOIs already present in data/seen.json, and write the remaining
// *new* candidates (compact) to --out. Deterministic — no LLM here.
//
// Usage:
//   node fetch_papers.mjs --out data/new_candidates.json
//   node fetch_papers.mjs --out data/new_candidates.json --max-new 60
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(__dirname, "..");

function parseArgs(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) o[a.slice(2)] = argv[++i];
  }
  return o;
}

const args = parseArgs(process.argv.slice(2));
const feedsPath = args.feeds || join(SKILL_DIR, "config", "feeds.json");
const seenPath = args.seen || join(SKILL_DIR, "data", "seen.json");
const outPath = args.out || join(SKILL_DIR, "data", "new_candidates.json");
const maxNew = args["max-new"] ? parseInt(args["max-new"], 10) : 100;
const abstractCap = 400;

// ---------- RSS 1.0 parsing helpers ----------
function stripCdata(s) {
  // Tolerant: strip a leading <![CDATA[ and a trailing ]]> if present.
  let t = s;
  if (t.startsWith("<![CDATA[")) t = t.slice(9);
  if (t.endsWith("]]>")) t = t.slice(0, -3);
  return t;
}
function unescapeHtml(s) {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'");
}
function stripTags(html) {
  let t = html.replace(/<[^>]+>/g, " ");
  t = unescapeHtml(t);
  t = t.replace(/\s+/g, " ").trim();
  return t;
}
function textOf(item, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "i");
  const m = item.match(re);
  return m ? stripCdata(m[1]).trim() : "";
}
function allText(item, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, "gi");
  const out = [];
  let m;
  while ((m = re.exec(item))) out.push(stripCdata(m[1]).trim());
  return out.filter(Boolean);
}
function attr(item, tag, attrName) {
  const re = new RegExp(`<${tag}[^>]*?\\s${attrName}=["']([^"']+)["']`, "i");
  const m = item.match(re);
  return m ? m[1] : "";
}
function inferType(doi, link) {
  if (/^10\.1038\/d41586/.test(doi)) return "news";
  if (/^10\.1038\/s41586/.test(doi)) return "research";
  if (/^10\.1038\/s42256/.test(doi)) return "research"; // Nature Machine Intelligence
  if (/\/articles\/d41586-/.test(link)) return "news";
  return "article";
}
function cleanAbstract(text) {
  if (!text) return "";
  // strip leading "Journal, Published online: <date>; doi:<doi> " preamble
  return text
    .replace(/^[A-Za-z][A-Za-z &]+,\s*Published online:[^;]*;\s*doi:\S+\s*/i, "")
    .trim();
}
function shortAuthors(authors) {
  if (!authors.length) return "";
  const head = authors.slice(0, 3).join(", ");
  return authors.length > 3 ? `${head}, et al.` : head;
}

async function fetchFeed(url) {
  const res = await fetch(url, {
    headers: {
      "User-Agent":
        "nature-digest/0.1 (pi-agent skill; +https://www.nature.com)",
    },
    signal: AbortSignal.timeout(20000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.text();
}

function parseFeed(xml, feedMeta) {
  const items = xml.match(/<item\b[\s\S]*?<\/item>/gi) || [];
  const out = [];
  for (const raw of items) {
    const title = stripTags(textOf(raw, "title"));
    const link =
      textOf(raw, "link") ||
      attr(raw, "item", "rdf:about") ||
      textOf(raw, "guid");
    let doi = textOf(raw, "prism:doi");
    if (!doi) {
      const id = textOf(raw, "dc:identifier");
      if (id && id.toLowerCase().startsWith("doi:")) doi = id.slice(4);
    }
    if (!doi || !title || !link) continue;
    const authors = allText(raw, "dc:creator");
    const journal =
      textOf(raw, "prism:publicationName") || feedMeta.journal || "";
    const date =
      textOf(raw, "dc:date") ||
      textOf(raw, "prism:publicationDate") ||
      textOf(raw, "pubDate");
    let abstract = stripTags(textOf(raw, "content:encoded"));
    if (!abstract) abstract = stripTags(textOf(raw, "description"));
    abstract = cleanAbstract(abstract).slice(0, abstractCap);
    out.push({
      doi,
      title,
      link,
      authors: shortAuthors(authors),
      journal,
      date,
      type: inferType(doi, link),
      abstract,
    });
  }
  return out;
}

function loadSeenDois() {
  if (!existsSync(seenPath)) return new Set();
  try {
    const j = JSON.parse(readFileSync(seenPath, "utf8"));
    return new Set(Object.keys(j.dois || {}));
  } catch {
    return new Set();
  }
}

(async () => {
  const feeds = JSON.parse(readFileSync(feedsPath, "utf8"));
  const seen = loadSeenDois();
  const byDoi = new Map();
  let totalParsed = 0;

  for (const f of feeds) {
    try {
      const xml = await fetchFeed(f.url);
      const items = parseFeed(xml, f);
      totalParsed += items.length;
      let added = 0;
      for (const it of items) {
        if (byDoi.has(it.doi)) {
          const ex = byDoi.get(it.doi);
          if (!ex.journal && it.journal) ex.journal = it.journal;
          continue;
        }
        byDoi.set(it.doi, it);
        added++;
      }
      process.stderr.write(
        `[fetch] ${f.name}: ${items.length} parsed, ${added} unique\n`,
      );
    } catch (e) {
      process.stderr.write(`[fetch] ${f.name}: FAILED ${e.message}\n`);
    }
  }

  // Drop already-seen DOIs, keep only new candidates.
  const allNew = [];
  for (const it of byDoi.values()) {
    if (!seen.has(it.doi)) allNew.push(it);
  }
  const fresh = allNew.slice(0, maxNew);
  const alreadySeen = byDoi.size - allNew.length;

  const json = JSON.stringify(fresh);
  writeFileSync(outPath, json);
  process.stderr.write(
    `[fetch] total parsed=${totalParsed}, unique=${byDoi.size}, ` +
      `already-seen=${alreadySeen}, new=${allNew.length}` +
      (fresh.length < allNew.length
        ? ` (capped to ${maxNew}; ${allNew.length - maxNew} backfill next run)`
        : "") +
      ` -> wrote ${fresh.length} to ${outPath}\n`,
  );
})();
