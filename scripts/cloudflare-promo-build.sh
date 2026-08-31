#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

required=(PINTEREST_APP_ID PINTEREST_APP_SECRET GITHUB_CONTENT_TOKEN)
for name in "${required[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "Missing required Cloudflare build secret: $name" >&2
    exit 1
  fi
done

export PYTHONUNBUFFERED=1

git config user.name "rareplantguide-cloudflare-bot"
git config user.email "bot@users.noreply.github.com"
git remote set-url origin "https://x-access-token:${GITHUB_CONTENT_TOKEN}@github.com/pentacam-hub/rareplantguide.git"

# Start from the latest source/queue state even though the Deploy Hook is tied to
# a stable marker branch.
git fetch origin main
git reset --hard origin/main

python3 -m pip install --user -r scripts/requirements.txt
python3 -m unittest \
  scripts.test_post_pin \
  scripts.test_post_promo_pin \
  scripts.test_promo_strategy \
  scripts.test_wait_for_deploy

PROMO_KIND=""
set +e
python3 -m scripts.post_buying_guide_pin --prepare
BUYING_PREPARE_STATUS=$?
set -e

if [ "$BUYING_PREPARE_STATUS" -eq 0 ]; then
  PROMO_KIND="buying"
elif [ "$BUYING_PREPARE_STATUS" -eq 3 ]; then
  # Evergreen fallback is now ordered by current GSC/Pinterest evidence rather
  # than simply choosing the oldest eligible article every time.
  python3 -m scripts.post_promo_pin_strategic --prepare
  PROMO_KIND="evergreen"
else
  echo "Buying-guide Pin preparation failed with exit code $BUYING_PREPARE_STATUS" >&2
  exit "$BUYING_PREPARE_STATUS"
fi

git add static/images/pins/ content-queue.yaml promo-buying-guides.yaml
if ! git diff --staged --quiet; then
  git commit -m "Auto: prepare Pinterest promo Pin"
  git fetch origin main
  git rebase origin/main
  git push origin HEAD:main
else
  echo "No new Pinterest promo creative to commit."
fi

# The generated Pin is uploaded to Pinterest as base64, but waiting here also
# gives the linked article time to reach production before the Pin goes live.
python3 -m scripts.wait_for_deploy \
  --kind promo \
  --max-pins 1 \
  --article-only \
  --timeout 180 \
  --interval 15 || true

if [ "$PROMO_KIND" = "buying" ]; then
  python3 -m scripts.post_buying_guide_pin --publish
else
  python3 -m scripts.post_promo_pin_strategic --publish
fi

git add content-queue.yaml promo-buying-guides.yaml
if ! git diff --staged --quiet; then
  git commit -m "Auto: record Pinterest promo Pin"
  git fetch origin main
  git rebase origin/main
  git push origin HEAD:main
else
  echo "No Pinterest promo status change to commit."
fi

mkdir -p .agent-output
cat > .agent-output/index.html <<'EOF'
<!doctype html><html><body><p>Rare Plant Pinterest promo agent completed.</p></body></html>
EOF

# Workers Builds uses the preview deploy command for non-production branches.
# The repository's normal wrangler.toml targets the public site, so replace it
# only inside this ephemeral build workspace with the promo agent configuration.
cat > wrangler.toml <<'EOF'
name = "rareplant-content-agent"
compatibility_date = "2026-08-01"

[assets]
directory = "./.agent-output"
not_found_handling = "404-page"
EOF

echo "Cloudflare Pinterest promo agent completed successfully ($PROMO_KIND)."
