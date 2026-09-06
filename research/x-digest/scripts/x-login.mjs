#!/usr/bin/env node
// x-login.mjs — open X.com login in a visible Playwright Chromium window
// and wait until the user logs in. Cookies persist in browser-profile/,
// so this is only needed on first run or after a session expiry.
//
// Usage: node scripts/x-login.mjs [--timeout-minutes 10]
import { launchX, isLoggedIn, waitFor } from "./pw-common.mjs";

const argv = process.argv.slice(2);
function getArg(name, dflt) {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
}
const TIMEOUT_MS = parseInt(getArg("--timeout-minutes", "10"), 10) * 60 * 1000;

const ctx = await launchX({ headed: true });
let exitCode = 0;
try {
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto("https://x.com/login", { waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});

  if (await isLoggedIn(ctx)) {
    console.log("ALREADY_LOGGED_IN");
  } else {
    console.log("OPEN_BROWSER_WINDOW: please sign in to x.com now (Google / Apple / email all work).");
    console.log(`Waiting up to ${Math.round(TIMEOUT_MS / 60000)} min for login...`);

    const ok = await waitFor(
      () => isLoggedIn(ctx),
      {
        timeoutMs: TIMEOUT_MS,
        intervalMs: 5000,
        onTick: (s) => {
          if (s % 30 === 0 && s > 0) process.stderr.write(`... still waiting (${s}s)\n`);
        },
      }
    );

    if (ok) {
      // give X a moment to settle the session (ct0, guest tokens, etc.)
      await new Promise((r) => setTimeout(r, 3000));
      console.log("LOGGED_IN");
    } else {
      console.error("LOGIN_TIMEOUT: no auth_token detected; the window is closed. Re-run when ready.");
      exitCode = 1;
    }
  }
} finally {
  await ctx.close();
}
process.exit(exitCode);
