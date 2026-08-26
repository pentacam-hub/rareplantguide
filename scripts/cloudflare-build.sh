#!/usr/bin/env bash
set -euo pipefail

# Cloudflare Pages production build.
# Always rebuild from source so a previously committed public/ directory can never go stale.
rm -rf public

hugo --minify
python3 scripts/inject_google_analytics.py

test -s public/index.html

echo "Cloudflare Pages build complete: public/index.html generated."
