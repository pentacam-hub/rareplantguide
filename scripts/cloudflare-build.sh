#!/usr/bin/env bash
set -euo pipefail

# Cloudflare Pages production build.
# Always rebuild from source so a previously committed public/ directory can never go stale.
rm -rf public

# Every editorial post must render with a relevant local image. This also repairs
# older source posts that were created when the Unsplash cover download failed.
python3 scripts/inject_article_visuals.py

# Refresh only URLs that already show proven Search Console traction.
# This runs before Hugo so title, description, H1 and internal-link changes are
# present in the rendered HTML that search engines receive.
python3 scripts/optimize_search_winners.py

# Turn the proven Reversion / Variegation cluster into a decision path instead
# of creating near-duplicate informational pages that could cannibalize ranking.
python3 scripts/inject_reversion_decision_cluster.py

hugo --minify

# Commercial pages must never show an empty "Check current price" placeholder.
# Inject a recent US price snapshot as the visible fallback; any live Amazon
# pricing layer may still replace it when available.
python3 scripts/inject_buying_price_snapshots.py

python3 scripts/inject_google_analytics.py

test -s public/index.html

echo "Cloudflare Pages build complete: article visuals verified and public/index.html generated."
