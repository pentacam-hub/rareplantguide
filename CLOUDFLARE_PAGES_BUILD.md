# Cloudflare Pages direct build

This repository is prepared to let Cloudflare Pages build the Hugo site directly from `main`, without requiring a GitHub Actions build on every source commit.

## Cloudflare Pages settings

Use these values in the existing Pages project:

- Production branch: `main`
- Root directory: repository root / blank
- Build command: `bash scripts/cloudflare-build.sh`
- Build output directory: `public`
- Environment variable: `HUGO_VERSION=0.148.2`

The build script removes any previously committed `public/` directory, rebuilds Hugo from source, injects the existing GA4 tag, and verifies that `public/index.html` exists.

## GitHub Actions

`.github/workflows/build-site.yml` is intentionally manual-only as a fallback. Normal site builds should be performed by Cloudflare Pages Git integration.

The separate Pinterest + Content Agent still uses GitHub Actions until it is migrated independently.
