#!/usr/bin/env bash
# Daily runner for the nature-digest skill. Intended for cron.
# Usage (cron): 0 8 * * * /Users/zliang/Documents/nature-digest/run.sh
set -euo pipefail

# cron runs with a minimal PATH (/usr/bin:/bin); ensure pi, node, msmtp are found.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SKILL_DIR"
mkdir -p logs data/digests

# Recipient + msmtp account for the local email skill backend.
export DIGEST_EMAIL_TO="zleung9@outlook.com"
export MSMTP_ACCOUNT="xmu"

LOG="logs/digest-$(date +%F).log"
{
  echo "=== $(date "+%Y-%m-%dT%H:%M:%S%z") nature-digest run ==="
  pi -p "/skill:nature-digest"
} >> "$LOG" 2>&1
