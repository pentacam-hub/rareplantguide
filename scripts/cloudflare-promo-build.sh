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

python3 -m pip install --user -r scripts/requirements.txt
python3 -m unittest \
  scripts.test_post_pin \
  scripts.test_post_promo_pin \
  scripts.test_wait_for_deploy

python3 scripts/post_promo_pin.py --prepare

git config user.name "rareplantguide-cloudflare-bot"
git config user.email "bot@users.noreply.github.com"
git remote set-url origin "https://x-access-token:${GITHUB_CONTENT_TOKEN}@github.com/pentacam-hub/rareplantguide.git"

git add static/images/pins/ content-queue.yaml
if ! git diff --staged --quiet; then
  git commit -m "Auto: prepare evergreen Pinterest Pin"
  git pull --rebase origin main
  git push origin HEAD:main
else
  echo "No new evergreen creative to commit."
fi

python3 -m scripts.wait_for_deploy \
  --kind promo \
  --max-pins 1 \
  --article-only \
  --timeout 180 \
  --interval 15 || true

python3 scripts/post_promo_pin.py --publish

git add content-queue.yaml
if ! git diff --staged --quiet; then
  git commit -m "Auto: record evergreen Pinterest Pin"
  git pull --rebase origin main
  git push origin HEAD:main
else
  echo "No evergreen Pinterest status change to commit."
fi

mkdir -p .agent-output
cat > .agent-output/index.html <<'EOF'
<!doctype html><html><body><p>Rare Plant evergreen Pinterest agent completed.</p></body></html>
EOF

echo "Cloudflare evergreen Pinterest agent completed successfully."
