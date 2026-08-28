#!/usr/bin/env bash
set -euo pipefail

# Workers Builds injects WORKERS_CI_BRANCH. Keep CF_PAGES_BRANCH as a fallback
# so the same script remains portable if the project is ever moved back to Pages.
MODE_BRANCH="${WORKERS_CI_BRANCH:-${CF_PAGES_BRANCH:-}}"

# Only the two stable automation branches are allowed to execute agent work.
# All other branches are successful no-ops.
case "$MODE_BRANCH" in
  cf-agent-content|cf-agent-promo)
    ;;
  *)
    echo "Cloudflare agent no-op for branch: ${MODE_BRANCH:-<unset>}"
    exit 0
    ;;
esac

# Always run the latest automation code from main, even though Deploy Hooks use
# stable marker branches.
git fetch origin main
git checkout -B cloudflare-agent-runtime origin/main

if [ "$MODE_BRANCH" = "cf-agent-promo" ]; then
  # Kept for compatibility if preview-trigger build secrets are configured later.
  exec bash scripts/cloudflare-promo-build.sh
fi

# cf-agent-content is the production branch and therefore has the production
# build secrets. Use that one production trigger for both scheduled jobs.
# Scheduler cadence (UTC):
#   14:30 every day                 -> promo
#   19:30 Monday and Thursday       -> content
#   19:30 Tue/Wed/Fri/Sat/Sun       -> promo
# Any ad-hoc/manual production build defaults to promo, which is the safer job:
# it only creates a Pin and never creates a new article.
UTC_HOUR="$(date -u +%H)"
UTC_DOW="$(date -u +%u)"  # 1=Mon ... 7=Sun

if [ "$UTC_HOUR" = "19" ] && { [ "$UTC_DOW" = "1" ] || [ "$UTC_DOW" = "4" ]; }; then
  echo "Agent mode: content (scheduled ${UTC_DOW}/${UTC_HOUR} UTC)."
  exec bash scripts/cloudflare-agent-build.sh
fi

echo "Agent mode: promo (branch=${MODE_BRANCH}, dow=${UTC_DOW}, hour=${UTC_HOUR} UTC)."
exec bash scripts/cloudflare-promo-build.sh
