#!/usr/bin/env bash
set -euo pipefail

MODE_BRANCH="${CF_PAGES_BRANCH:-}"

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
  *)
    echo "Unsupported Cloudflare agent branch: ${MODE_BRANCH:-<unset>}" >&2
    exit 1
    ;;
esac
