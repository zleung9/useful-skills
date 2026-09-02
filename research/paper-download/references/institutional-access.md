# Institutional Access on This Mac

The machine is on the **XMU (Xiamen University) campus-recognized network**. Institutional subscriptions are granted by **IP recognition**, not by a logged-in session — so a fresh Chrome profile with no credentials will still get full-text PDFs, provided the browser egresses through the recognized network.

## Key fact

**Do not diagnose "no access" from the egress IP's org string.** During development, a subagent saw `117.28.251.154 (AS4809 China Telecom)` and concluded XMU had no access. That was **wrong** — ACS served the full PDF anyway. Institutional recognition is a publisher-side IP-allowlist that can include non-CERNET ranges the campus NATs through. Verify access from rendered-page evidence (the footer imprint), never from the egress IP.

## How to confirm access worked

After Cloudflare clears and the landing/PDF page renders, the page footer imprints text like:

> `by XIAMEN UNIV user` (ACS)
> `Access provided by Xiamen University` (Wiley)
> `Xiamen University — Sponsored by …` (Elsevier/ScienceDirect)

The helper script's `has_access()` checks for the `by <INST> user` pattern plus presence of article body text (`abstract`/`introduction`/`received`) and absence of paywall markers (`purchase access`, `get access`, `sign in to`).

## Publishers known to recognize XMU on this network

| Publisher | Domain | Confirmed |
|---|---|---|
| ACS | pubs.acs.org | ✅ (this session) |
| AIP | pubs.aip.org (Physics of Fluids, etc.) | ✅ IP recognition, 2026-08-16 (DOI 10.1063/5.0232224) — no CARSI; Cloudflare gate requires the Chrome+cookie path; `has_access()` footer heuristic reads False on AIP even when access works, so trust the final `%PDF` over the flag |
| Wiley | onlinelibrary.wiley.com | likely (IP recognition) |
| Elsevier | sciencedirect.com | likely |
| RSC | pubs.rsc.org | likely |
| Springer/Nature | link.springer.com, nature.com | likely |

Treat "likely" as unverified — confirm via the footer imprint on first use for each publisher.

## When access does NOT work (CARSI handoff)

If the page shows paywall markers and **no** institutional imprint, do **not** enter the user's credentials automatically. Instead:

1. Leave the Chrome window open (the script keeps it open `--keep-open` seconds; bump this if needed).
2. Tell the user: "Please complete institutional login in the open Chrome window" and point them at the CARSI / Shibboleth login link on the page.
3. After the user logs in, re-run the cookie-export + curl step (the session cookies will now carry the auth). The persistent profile retains the login for subsequent runs.

## Proxy / network notes

- Local Clash (verge-mihomo) runs a SOCKS proxy on `127.0.0.1:7897` and a system proxy. **TUN mode must be OFF** (user confirms; if TUN is on, it intercepts at the routing layer and `--no-proxy-server` is insufficient).
- The helper script clears all `*_proxy` env vars before importing Playwright and launches Chrome with `--no-proxy-server`, so the browser egresses directly.
- For `curl`, always pass `--noproxy '*'` so it ignores the system proxy too.
- Campus-internal IPs (`10.26.x.x`) need `NO_PROXY` — see memory `feedback_campus_network_no_proxy`. Not relevant here (publishers are external) but keep in mind if a publisher resolves to a campus mirror.

See also memory `feedback_paper_download_browser_cookies` for the full session history.
