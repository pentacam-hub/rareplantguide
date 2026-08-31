#!/usr/bin/env bash
set -euo pipefail

# Cloudflare Pages production build.
# Always rebuild from source so a previously committed public/ directory can never go stale.
rm -rf public

# Refresh only URLs that already show proven Search Console traction.
# This runs before Hugo so title, description, H1 and internal-link changes are
# present in the rendered HTML that search engines receive.
python3 scripts/optimize_search_winners.py

hugo --minify
python3 scripts/inject_google_analytics.py

test -s public/index.html

echo "Cloudflare Pages build complete: public/index.html generated."
