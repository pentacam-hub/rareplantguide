# The Rare Plant Guide — Automation Setup

Production builds and scheduled Rare Plant content/Pinterest automation are configured for Cloudflare Workers Builds rather than scheduled GitHub Actions.

Current source of truth:

`CLOUDFLARE_CONTENT_AGENT.md`

Legacy GitHub workflows remain manual-only emergency fallbacks and should not have `push` or `schedule` triggers.

Main repository:

`pentacam-hub/rareplantguide`

Production branch:

`main`

Cloudflare marker branches:

- `cf-agent-content` — content article + original Pinterest Pin runner
- `cf-agent-promo` — evergreen Pinterest runner

The marker branches are intentionally stable. Each Cloudflare automation build synchronizes its checkout to the latest `main` before reading or modifying the editorial queue.

Do not place API keys, Pinterest credentials, GitHub write tokens or Deploy Hook URLs in repository files. Store them as Cloudflare build secrets / Worker secrets.
