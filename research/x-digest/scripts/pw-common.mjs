// pw-common.mjs — shared Playwright helpers for x-digest.
//
// Uses a dedicated persistent Chromium profile (browser-profile/) so:
//   - login cookies persist to disk across runs (no re-login needed)
//   - NO user extensions are ever loaded (the X.com "privacy extension"
//     error can't happen)
//   - no dependency on the user's Chrome or a CDP port (:9222)
//
// Only ONE process may hold the profile at a time (SingletonLock).
import { chromium } from "playwright";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_DIR = dirname(dirname(fileURLToPath(import.meta.url))); // /Users/zliang/Documents/x-digest
export const X_PROFILE = join(SKILL_DIR, "browser-profile");

/**
 * Launch the persistent X Chromium context.
 * @param {object} opts
 * @param {boolean} [opts.headed=true]  set false for headless (login requires headed)
 */
export async function launchX({ headed = true } = {}) {
  return chromium.launchPersistentContext(X_PROFILE, {
    headless: !headed,
    viewport: { width: 1380, height: 900 },
    locale: "zh-CN",
    args: [
      "--disable-blink-features=AutomationControlled",
      "--disable-features=IsolateOrigins,site-per-process",
    ],
  });
}

/** Return x.com cookies for the context. */
export async function xCookies(ctx) {
  return ctx.cookies("https://x.com");
}

/** True when the context has an X login (auth_token cookie). */
export async function isLoggedIn(ctx) {
  const cookies = await xCookies(ctx);
  return cookies.some((c) => c.name === "auth_token" && c.value);
}

/** Wait for a condition with a 5s poll. Returns true if it became true. */
export async function waitFor(fn, { timeoutMs = 300000, intervalMs = 5000, onTick = null } = {}) {
  const start = Date.now();
  for (;;) {
    if (await fn()) return true;
    if (Date.now() - start > timeoutMs) return false;
    if (onTick) onTick(Math.round((Date.now() - start) / 1000));
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
