from pathlib import Path
import re

MEASUREMENT_ID = "G-2XPYDX7QRW"
PUBLIC_DIR = Path(__file__).resolve().parents[1] / "public"

TAG = '''<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2XPYDX7QRW"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-2XPYDX7QRW');
</script>'''

# Remove an existing gtag loader plus the immediately following config block
# for this exact GA4 property before inserting the canonical copy.
EXISTING_TAG = re.compile(
    r'<script[^>]*src=["\']https://www\.googletagmanager\.com/gtag/js\?id='
    + re.escape(MEASUREMENT_ID)
    + r'["\'][^>]*></script>\s*<script[^>]*>[\s\S]*?'
    + re.escape(MEASUREMENT_ID)
    + r'[\s\S]*?</script>',
    re.IGNORECASE,
)

HEAD = re.compile(r'<head\b[^>]*>', re.IGNORECASE)

if not PUBLIC_DIR.exists():
    raise SystemExit(f"Missing public directory: {PUBLIC_DIR}")

files = list(PUBLIC_DIR.rglob("*.html"))
if not files:
    raise SystemExit("No HTML files found in public/")

updated = 0
for path in files:
    html = path.read_text(encoding="utf-8")
    html = EXISTING_TAG.sub("", html)

    match = HEAD.search(html)
    if not match:
        raise SystemExit(f"Missing <head> in {path.relative_to(PUBLIC_DIR)}")

    html = html[: match.end()] + "\n" + TAG + "\n" + html[match.end() :]

    # The ID must occur exactly twice: loader URL + gtag config.
    if html.count(MEASUREMENT_ID) != 2:
        raise SystemExit(
            f"Unexpected {MEASUREMENT_ID} count in {path.relative_to(PUBLIC_DIR)}: "
            f"{html.count(MEASUREMENT_ID)}"
        )

    after_head = html[match.end() :].lstrip()
    if not after_head.startswith("<!-- Google tag (gtag.js) -->"):
        raise SystemExit(f"Google tag is not first after <head> in {path.relative_to(PUBLIC_DIR)}")

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Google Analytics {MEASUREMENT_ID} placed immediately after <head> in {updated} HTML files.")
