#!/usr/bin/env node
// send_email.mjs
// Send the digest email. Backends (first match wins):
//   1. msmtp (local email skill) — reads ~/.config/msmtp/config, sends via
//      `msmtp -a <account> <recipients>`. Default account: "163".
//      Set MSMTP_ACCOUNT to override. This is the primary backend when msmtp
//      is installed and configured.
//   2. Resend API  — set RESEND_API_KEY (and DIGEST_EMAIL_TO).
//   3. Dry-run     — no backend available: print to stdout, exit 0.
//
// The digest body is Markdown; this script converts it to HTML for email.
//
// Usage:
//   node send_email.mjs --subject "..." --html-file data/digests/2026-08-27.md --to you@example.com
//   node send_email.mjs --subject "..." --to you@example.com < data/digests/2026-08-27.md
import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { resolve, join } from "node:path";
import { execFileSync } from "node:child_process";

function parseArgs(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) o[a.slice(2)] = argv[++i];
  }
  return o;
}

const args = parseArgs(process.argv.slice(2));
const subject = args.subject || "Nature 智能体 & AI for Science 日报";
const to = (args.to || process.env.DIGEST_EMAIL_TO || "").trim();
const account = args.account || process.env.MSMTP_ACCOUNT || "163";
const msmtpBin = args["msmtp-bin"] || "msmtp";
const msmtpConfig =
  process.env.MSMTP_CONFIG || join(homedir(), ".config", "msmtp", "config");

let bodyMd;
if (args["html-file"]) {
  bodyMd = readFileSync(resolve(process.cwd(), args["html-file"]), "utf8");
} else if (args.body) {
  bodyMd = args.body;
} else {
  bodyMd = readFileSync(0, "utf8");
}

// ---------- Markdown -> HTML (lightweight, email-safe) ----------
function esc(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function inline(s) {
  // bold **x**, links [t](u), code `x`
  let t = esc(s);
  t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>');
  return t;
}
function mdToHtml(md) {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^#{1,3}\s/.test(line)) {
      closeList();
      const m = line.match(/^(#{1,3})\s+(.*)$/);
      const lvl = m[1].length;
      out.push(`<h${lvl}>${inline(m[2])}</h${lvl}>`);
    } else if (/^---+$/.test(line)) {
      closeList();
      out.push("<hr>");
    } else if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
    } else if (line.trim() === "") {
      closeList();
      out.push("");
    } else {
      closeList();
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  closeList();
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:15px;line-height:1.6;color:#222;max-width:720px;margin:0 auto;">
${out.join("\n")}
</body></html>`;
}

function dryRun(reason) {
  console.error(`[email] ${reason} → DRY-RUN (not sent).`);
  console.log(`DRY-RUN | to: ${to || "(unset)"} | subject: ${subject}`);
  console.log("---- body (markdown) ----");
  console.log(bodyMd);
  process.exit(0);
}

if (!to) dryRun("No recipient (--to / DIGEST_EMAIL_TO not set)");

// ---------- msmtp backend (local email skill) ----------
function msmtpAvailable() {
  try {
    execFileSync("which", [msmtpBin], { stdio: "ignore" });
  } catch {
    return false;
  }
  return existsSync(msmtpConfig);
}
function readFromFromConfig(acct) {
  // Parse account blocks; return the `from` of the matching account (or default).
  if (!existsSync(msmtpConfig)) return "";
  const text = readFileSync(msmtpConfig, "utf8");
  const blocks = []; // {account, lines}
  let cur = null;
  for (const line of text.split("\n")) {
    const m = line.match(/^\s*account\s+(\S+)\s*$/);
    if (m) {
      if (cur) blocks.push(cur);
      cur = { account: m[1], lines: [] };
      continue;
    }
    const def = line.match(/^\s*account\s+default\s*:\s*(\S+)\s*$/);
    if (def) {
      if (cur) blocks.push(cur);
      cur = { account: `default:${def[1]}`, lines: [] };
      continue;
    }
    if (cur) cur.lines.push(line);
  }
  if (cur) blocks.push(cur);
  // find block for acct or for default:<acct>
  const block =
    blocks.find((b) => b.account === acct) ||
    blocks.find((b) => b.account === `default:${acct}`) ||
    blocks.find((b) => b.account.startsWith("default:"));
  if (!block) return "";
  for (const l of block.lines) {
    const fm = l.match(/^\s*from\s+(\S+)\s*$/i);
    if (fm) return fm[1];
  }
  return "";
}

if (msmtpAvailable()) {
  const from = readFromFromConfig(account) || "zleung9@163.com";
  const recipients = to.split(",").map((s) => s.trim()).filter(Boolean);
  const html = mdToHtml(bodyMd);
  const rfc822 =
    `From: ${from}\r\n` +
    `To: ${recipients.join(", ")}\r\n` +
    `Subject: ${subject}\r\n` +
    `X-Source: pi-x-digest\r\n` +
    `MIME-Version: 1.0\r\n` +
    `Content-Type: text/html; charset=UTF-8\r\n` +
    `\r\n` +
    html;
  try {
    execFileSync(msmtpBin, ["-a", account, ...recipients], {
      input: rfc822,
      encoding: "utf8",
      stdio: ["pipe", "inherit", "inherit"],
    });
    console.log(
      `[email] sent via msmtp (account=${account}) from ${from} to ${recipients.join(", ")}`,
    );
    process.exit(0);
  } catch (e) {
    console.error("[email] msmtp failed: " + (e.message || e));
    process.exit(1);
  }
}

// ---------- Resend backend ----------
if (process.env.RESEND_API_KEY) {
  const from =
    process.env.DIGEST_EMAIL_FROM || "Nature Digest <digest@resend.dev>";
  const html = mdToHtml(bodyMd);
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + process.env.RESEND_API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from,
        to: to.split(",").map((s) => s.trim()),
        subject,
        html,
      }),
      signal: AbortSignal.timeout(20000),
    });
    if (!r.ok) {
      const t = await r.text();
      console.error(`[email] Resend failed ${r.status}: ${t}`);
      process.exit(1);
    }
    const data = await r.json();
    console.log(`[email] sent via Resend id=${data.id || "?"} to ${to}`);
    process.exit(0);
  } catch (e) {
    console.error("[email] Resend error: " + e.message);
    process.exit(1);
  }
}

dryRun("No backend configured (msmtp not found and RESEND_API_KEY unset)");
