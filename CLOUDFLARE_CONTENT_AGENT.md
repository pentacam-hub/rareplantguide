# Cloudflare Content Agent — GitHub Actions replacement

This replaces the scheduled GitHub Actions content/Pinterest runner with Cloudflare.

## Architecture

1. `rareplant-content-scheduler` Cloudflare Worker runs Monday and Thursday at 19:30 UTC.
2. The Worker POSTs a secret Deploy Hook URL.
3. A dedicated Cloudflare Pages project (`rareplant-content-agent`) builds the same GitHub repository using `scripts/cloudflare-agent-build.sh`.
4. The build runs the existing Python article/Pinterest tests and generator.
5. It commits the new Markdown + images + queue state to `main` using `GITHUB_CONTENT_TOKEN`.
6. The production Rare Plant Pages project sees that source commit, runs `bash scripts/cloudflare-build.sh`, and publishes the site.
7. The agent build waits until the article/image are public, posts one pending Pin, then commits only the Pinterest status.
8. The production Pages project should exclude `content-queue.yaml` from Build watch paths so the status-only commit does not trigger a redundant site build.

No scheduled GitHub Action is required.

## A. Production Pages project

Use the existing Rare Plant Pages project.

- Production branch: `main`
- Build command: `bash scripts/cloudflare-build.sh`
- Build output directory: `public`
- Environment variable: `HUGO_VERSION=0.148.2`
- Settings > Build > Build watch paths > Exclude: `content-queue.yaml`

Keep automatic production deployments ON for this project.

## B. Dedicated agent runner Pages project

Create a second Pages project connected to the same repository `pentacam-hub/rareplantguide`.

Suggested name: `rareplant-content-agent`

- Production branch: `main`
- Build command: `bash scripts/cloudflare-agent-build.sh`
- Build output directory: `.agent-output`
- Automatic production deployments: OFF
- Preview deployments: OFF

Add these build secrets/variables:

Required secrets:
- `GEMINI_API_KEY`
- `PINTEREST_APP_ID`
- `PINTEREST_APP_SECRET`
- `GITHUB_CONTENT_TOKEN`

Optional:
- `UNSPLASH_ACCESS_KEY` (without it, the existing generator creates the post without an Unsplash cover)
- `PINTEREST_REFRESH_TOKEN` (fallback only; client credentials remain preferred)

Recommended variable:
- `PYTHON_VERSION=3.11`

`GITHUB_CONTENT_TOKEN` must be a fine-grained GitHub token restricted to `pentacam-hub/rareplantguide` with **Contents: Read and write**. Do not store it in the repository.

Create a Deploy Hook in this project:

- Settings > Builds > Deploy Hooks
- Name: `scheduled-content-agent`
- Branch: `main`

Copy the generated hook URL and treat it as a secret.

## C. Scheduler Worker

Create a Worker connected to the repository with root directory:

`cloudflare/content-scheduler`

Use:

- Deploy command: `npm run deploy`
- Worker name: `rareplant-content-scheduler`

The checked-in `wrangler.jsonc` already defines:

`30 19 * * 1,4`

Cloudflare Cron uses UTC, so this fires Monday and Thursday at 19:30 UTC.

Add Worker secret:

- `AGENT_DEPLOY_HOOK_URL` = the Deploy Hook URL from section B

Optional secret:

- `MANUAL_TRIGGER_TOKEN` = any long random value; when set, `POST /run` requires `Authorization: Bearer <token>`.

Health endpoint:

`GET /health`

Manual trigger endpoint:

`POST /run`

## D. GitHub Actions state

`.github/workflows/build-site.yml` and `.github/workflows/auto-post.yml` are retained only as manual emergency fallbacks. They must not have scheduled or push triggers.

## E. Safe cutover check

Before considering the migration closed:

1. Trigger the agent Deploy Hook manually once.
2. Confirm the agent build completes successfully.
3. Confirm a new source commit appears on `main` without `public/` changes.
4. Confirm the production Pages project builds that commit.
5. Confirm the new article and Pin image return HTTP 200.
6. Confirm Pinterest either publishes one Pin or recognizes an existing Pin.
7. Confirm the final queue-status-only commit does not trigger a production site build.
8. Confirm no scheduled GitHub Actions run appears.
