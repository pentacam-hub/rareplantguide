# The Rare Plant Guide — Automation Setup

The production automation now uses Cloudflare rather than scheduled GitHub Actions.

## Current architecture

- GitHub: source repository only
- Cloudflare Pages production project: builds and serves the Hugo site from `main`
- Cloudflare Pages agent project: runs the existing Python article/Pinterest automation when called by Deploy Hooks
- Cloudflare Worker: owns the schedules and triggers the appropriate agent Deploy Hook
- GitHub Actions: manual emergency fallbacks only

Full setup and cutover instructions are in:

`CLOUDFLARE_CONTENT_AGENT.md`

## Production site build

Production branch: `main`

Build command:

`bash scripts/cloudflare-build.sh`

Output directory:

`public`

Recommended environment variable:

`HUGO_VERSION=0.148.2`

Exclude `content-queue.yaml` from production Pages Build watch paths so Pinterest status-only commits do not cause redundant site builds.

## Content + Pinterest schedules

Cloudflare Worker configuration lives in:

`cloudflare/content-scheduler/`

Current UTC schedules:

- 14:30 daily → evergreen Pin
- 19:30 Sun/Tue/Wed/Fri/Sat → second evergreen Pin
- 19:30 Mon/Thu → new article + original Pin

## Agent runner

The dedicated Cloudflare agent Pages project runs:

`bash scripts/cloudflare-agent-entry.sh`

Output directory:

`.agent-output`

Marker branches:

- `cf-agent-content`
- `cf-agent-promo`

The entry script always fetches the latest `main` before running, so marker branches do not need manual synchronization.

Required Cloudflare agent secrets:

- `GEMINI_API_KEY`
- `PINTEREST_APP_ID`
- `PINTEREST_APP_SECRET`
- `GITHUB_CONTENT_TOKEN` — fine-grained GitHub token limited to this repository with Contents: Read and write

Optional:

- `UNSPLASH_ACCESS_KEY`
- `PINTEREST_REFRESH_TOKEN`

Never commit secret values to the repository.

## GitHub Actions

These workflows are retained only for manual emergency use and must have `workflow_dispatch` only:

- `.github/workflows/build-site.yml`
- `.github/workflows/auto-post.yml`
- `.github/workflows/pinterest-promo.yml`
- `.github/workflows/pinterest-ci.yml`

The Analyze My Income Pinterest workflows in this repository are also manual-only.

## Source queue

Future article topics remain in `content-queue.yaml` with `status: pending`. Published history remains in the same file.
