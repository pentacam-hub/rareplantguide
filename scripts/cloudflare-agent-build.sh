#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

required=(GEMINI_API_KEY PINTEREST_APP_ID PINTEREST_APP_SECRET GITHUB_CONTENT_TOKEN)
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

# Deploy Hooks build a fixed marker branch. Always synchronize that checkout with
# the latest main before reading the editorial queue, otherwise a later run could
# reuse stale queue state and regenerate an already-published topic.
git fetch origin main
git reset --hard origin/main

python3 -m pip install --user -r scripts/requirements.txt
python3 -m unittest \
  scripts.test_generate_post \
  scripts.test_post_pin \
  scripts.test_wait_for_deploy

# Generate one new article/creative when a pending topic exists. The current
# priority wrapper intentionally allows article cadence to continue even if an
# older Pinterest Pin still needs a retry.
python3 scripts/run_daily_article.py

# Commit only source content/assets/state. public/ is built by Cloudflare.
git add content/posts/ static/images/ content-queue.yaml
if ! git diff --staged --quiet; then
  git commit -m "Auto: publish article and Pinterest creative"
  git fetch origin main
  git rebase origin/main
  git push origin HEAD:main
else
  echo "No new article changes; continuing with any pending Pinterest Pin."
fi

# Wait for the production Worker build to publish the oldest pending article
# and its image before asking Pinterest to create the Pin.
python3 -m scripts.wait_for_deploy \
  --kind original \
  --max-pins 1 \
  --timeout 420 \
  --interval 15

python3 scripts/post_pin.py --max-pins 1

# Persist only Pinterest delivery state. The production Worker excludes
# content-queue.yaml from build watch paths, so this status-only push does not
# cause a redundant site build.
git add content-queue.yaml
if ! git diff --staged --quiet; then
  git commit -m "Auto: record published Pinterest Pin"
  git fetch origin main
  git rebase origin/main
  git push origin HEAD:main
else
  echo "No Pinterest status change to commit."
fi

# Workers Builds still needs a deployable artifact after the automation step.
mkdir -p .agent-output
cat > .agent-output/index.html <<'EOF'
<!doctype html><html><body><p>Rare Plant content agent completed.</p></body></html>
EOF

echo "Cloudflare content agent completed successfully."
