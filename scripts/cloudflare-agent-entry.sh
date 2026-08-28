#!/usr/bin/env bash
set -euo pipefail

# Workers Builds injects WORKERS_CI_BRANCH. Keep CF_PAGES_BRANCH as a fallback
# so the same script remains portable if the project is ever moved back to Pages.
MODE_BRANCH="${WORKERS_CI_BRANCH:-${CF_PAGES_BRANCH:-}}"

# The agent project may have non-production builds enabled so its promo Deploy Hook
# can target cf-agent-promo. Git pushes to unrelated branches (especially main)
# must never run either automation. Exit successfully before doing any work.
case "$MODE_BRANCH" in
  cf-agent-content|cf-agent-promo)
    ;;
  *)
    echo "Cloudflare agent no-op for branch: ${MODE_BRANCH:-<unset>}"
    exit 0
    ;;
esac

# Always run the latest automation code from main, even though Deploy Hooks use
# stable marker branches to distinguish content vs evergreen executions.
git fetch origin main
git checkout -B cloudflare-agent-runtime origin/main

case "$MODE_BRANCH" in
  cf-agent-content)
    exec bash scripts/cloudflare-agent-build.sh
    ;;
  cf-agent-promo)
    exec bash scripts/cloudflare-promo-build.sh
    ;;
esac
