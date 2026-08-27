# Cloudflare Content Agent — GitHub Actions replacement

The Rare Plant production site and scheduled Pinterest/content automation are being moved from GitHub Actions to Cloudflare Workers Builds.

## Architecture

1. Production Worker builds `main` with `bash scripts/cloudflare-build.sh` and deploys `public/` as static assets.
2. A dedicated content-agent Worker uses stable marker branch `cf-agent-content` and runs `bash scripts/cloudflare-agent-build.sh` only when its Deploy Hook is triggered.
3. A dedicated evergreen Worker uses stable marker branch `cf-agent-promo` and runs `bash scripts/cloudflare-promo-build.sh` only when its Deploy Hook is triggered.
4. Each automation script immediately fetches and resets to the latest `main` before reading the queue, so marker branches can stay unchanged.
5. Generated Markdown, images and queue state are committed to `main` using a fine-grained GitHub token.
6. That `main` push triggers the production Cloudflare build automatically.
7. Pinterest is published only after the production article is available; queue-status-only commits are excluded from production build watch paths.
8. `rareplant-content-scheduler` calls the Deploy Hooks on the existing Pinterest schedule.

No scheduled GitHub Action is required.

## Production Worker build

Connected repository: `pentacam-hub/rareplantguide`

- Production branch: `main`
- Build command: `bash scripts/cloudflare-build.sh`
- Deploy command: `npx wrangler deploy --assets ./public/`
- Version command: `npx wrangler versions upload --assets ./public/`
- Root directory: blank
- Include paths: `*`
- Exclude paths: `content-queue.yaml`
- Build variable: `HUGO_VERSION=0.148.2`

## Content-agent Worker build

Create a second Worker connected to the same repository.

Suggested Worker name: `rareplant-content-agent`

- Production branch: `cf-agent-content`
- Disable builds for non-production branches.
- Build command: `bash scripts/cloudflare-agent-build.sh`
- Deploy command: `npx wrangler deploy --assets ./.agent-output --name rareplant-content-agent`
- Version command: `npx wrangler versions upload --assets ./.agent-output --name rareplant-content-agent`
- Root directory: blank
- Include paths: `*`

Build secrets:
- `GEMINI_API_KEY`
- `PINTEREST_APP_ID`
- `PINTEREST_APP_SECRET`
- `GITHUB_CONTENT_TOKEN`

Optional secrets:
- `UNSPLASH_ACCESS_KEY`
- `PINTEREST_REFRESH_TOKEN`

Build variable:
- `PYTHON_VERSION=3.11`

`GITHUB_CONTENT_TOKEN` must be a fine-grained token restricted to `pentacam-hub/rareplantguide` with Contents: Read and write.

Create Deploy Hook:
- Name: `scheduled-content-agent`
- Branch: `cf-agent-content`

## Evergreen-agent Worker build

Create a third Worker connected to the same repository.

Suggested Worker name: `rareplant-evergreen-agent`

- Production branch: `cf-agent-promo`
- Disable builds for non-production branches.
- Build command: `bash scripts/cloudflare-promo-build.sh`
- Deploy command: `npx wrangler deploy --assets ./.agent-output --name rareplant-evergreen-agent`
- Version command: `npx wrangler versions upload --assets ./.agent-output --name rareplant-evergreen-agent`
- Root directory: blank
- Include paths: `*`

Build secrets:
- `PINTEREST_APP_ID`
- `PINTEREST_APP_SECRET`
- `GITHUB_CONTENT_TOKEN`

Optional secret:
- `PINTEREST_REFRESH_TOKEN`

Build variable:
- `PYTHON_VERSION=3.11`

Create Deploy Hook:
- Name: `scheduled-evergreen-agent`
- Branch: `cf-agent-promo`

## Scheduler Worker

Repository files:
- `cloudflare/content-scheduler/src/index.ts`
- `cloudflare/content-scheduler/wrangler.jsonc`

Cron schedule (UTC):
- `30 14 * * *` → evergreen Pin every day
- `30 19 * * 0,2,3,5,6` → second evergreen Pin on non-article days
- `30 19 * * 1,4` → new article + original Pin Monday and Thursday

Scheduler secrets:
- `CONTENT_DEPLOY_HOOK_URL`
- `PROMO_DEPLOY_HOOK_URL`

Optional:
- `MANUAL_TRIGGER_TOKEN`

Endpoints:
- `GET /health`
- `POST /run-content`
- `POST /run-promo`

## GitHub Actions state

The legacy build, content-agent, evergreen, and Pinterest CI workflows are manual-only emergency fallbacks. They have no push or cron triggers.
