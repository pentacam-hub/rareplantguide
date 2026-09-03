"""Inject visible fallback prices into rendered buying-guide HTML.

Live Amazon pricing can still overwrite these values client-side when the price feed is
available. The fallback exists so a commercial landing never renders a useless
"Check current price" placeholder when the live feed is unavailable.

Prices below are recent US marketplace snapshots collected during the 2026-08-31
commercial review. They are deliberately labeled as snapshots because Amazon prices,
variants and availability can change at any time.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BUYING_DIR = ROOT / "public" / "buying-guides"

PRICE_SNAPSHOTS = {
    # Grow lights
    "B091DLFDL9": "$8.99",
    "B085CDPSMR": "$21.45",
    "B0C36WZBWC": "$25.99",
    # Humidifiers
    "B08HS45N13": "$63.96",
    "B0CCVX6FSD": "$44.98",
    "B013IJPTFK": "$39.99",
    # Propagation supplies
    "B01MU8CP1W": "$14.99",
    "B004Z71IHS": "$5.98",
    "B000BX1HGC": "$5.99",
    # Plant stands with grow lights
    "B0F5GTD4HN": "$42.99",
    "B0DGXF9B8S": "$35.99",
    "B0CL4WHFVS": "$137.99",
}

SNAPSHOT_NOTE = "Recent Amazon US price snapshot · verify current price"


def patch_price_block(block: str, price: str) -> str:
    block = re.sub(
        r'(<strong class="amazon-price-value">)(?:Check current price|[^<]*)(</strong>)',
        rf"\g<1>{price}\g<2>",
        block,
        count=1,
    )
    block = re.sub(
        r'(<small class="amazon-price-updated">)(?:Current price opens on Amazon|On Amazon|[^<]*)(</small>)',
        rf"\g<1>{SNAPSHOT_NOTE}\g<2>",
        block,
        count=1,
    )
    return block


def patch_html(html: str) -> tuple[str, int]:
    replacements = 0
    for asin, price in PRICE_SNAPSHOTS.items():
        pattern = re.compile(
            rf'(<div class="amazon-live-price[^\"]*"[^>]*data-amazon-price="{re.escape(asin)}"[^>]*>.*?</div>)',
            re.DOTALL,
        )

        def replace(match: re.Match[str]) -> str:
            nonlocal replacements
            original = match.group(1)
            patched = patch_price_block(original, price)
            if patched != original:
                replacements += 1
            return patched

        html = pattern.sub(replace, html)
    return html, replacements


def main() -> None:
    if not BUYING_DIR.exists():
        raise RuntimeError("Rendered buying-guides directory is missing; run Hugo first.")

    files_changed = 0
    replacements = 0
    unresolved_placeholders: list[str] = []

    for path in BUYING_DIR.rglob("*.html"):
        original = path.read_text(encoding="utf-8")
        patched, count = patch_html(original)
        if patched != original:
            path.write_text(patched, encoding="utf-8")
            files_changed += 1
            replacements += count
        final_html = patched
        if "Check current price" in final_html:
            unresolved_placeholders.append(str(path.relative_to(ROOT)))

    if unresolved_placeholders:
        joined = ", ".join(unresolved_placeholders[:8])
        raise RuntimeError(
            "Buying-guide price validation failed: unresolved 'Check current price' "
            f"placeholder remains in {joined}"
        )

    if replacements == 0:
        print(
            "Buying-guide price snapshots PASS: no unresolved placeholders; "
            "rendered pages already contain usable price/CTA output."
        )
        return

    print(
        f"Buying-guide price snapshots PASS: {replacements} visible price blocks "
        f"updated across {files_changed} rendered files."
    )


if __name__ == "__main__":
    main()
