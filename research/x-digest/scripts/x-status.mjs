#!/usr/bin/env node
// x-status.mjs — quick check whether the Playwright profile has a valid X login.
// Usage: node scripts/x-status.mjs   → prints JSON {loggedIn, hasAuthToken, cookieCount}
import { launchX, isLoggedIn, xCookies } from "./pw-common.mjs";

const ctx = await launchX({ headed: false });
try {
  const cookies = await xCookies(ctx);
  const loggedIn = await isLoggedIn(ctx);
  console.log(
    JSON.stringify({
      loggedIn,
      hasAuthToken: cookies.some((c) => c.name === "auth_token" && c.value),
      cookieCount: cookies.length,
    })
  );
  process.exit(loggedIn ? 0 : 1);
} finally {
  await ctx.close();
}
