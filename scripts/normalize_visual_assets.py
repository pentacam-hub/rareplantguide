"""Normalize visual assets before Hugo renders the production site.

A legacy Node/Axillary-Bud WebP has rendered as a blank rectangle in production even
though the file exists in git. Production must prefer a proven local JPG until a new
verified botanical close-up asset replaces it.

The replacement happens in the build workspace only, so legacy references cannot leak
into HTML from data files, old front matter, partials or generated content.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAD = "/images/monstera-node-vs-axillary-bud-comparison.webp"
REPLACEMENT = "/images/guide-to-houseplant-variegation-chimeric-pattern-and-viral.jpg"
SCAN_DIRS = (ROOT / "data", ROOT / "content", ROOT / "layouts")
TEXT_SUFFIXES = {".yaml", ".yml", ".md", ".html", ".toml", ".json"}


def main() -> None:
    replacement_asset = ROOT / "static" / REPLACEMENT.lstrip("/")
    if not replacement_asset.is_file() or replacement_asset.stat().st_size < 1024:
        raise RuntimeError(f"Replacement visual missing or invalid: {replacement_asset.relative_to(ROOT)}")

    files_changed = 0
    refs_replaced = 0
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            count = text.count(BAD)
            if not count:
                continue
            path.write_text(text.replace(BAD, REPLACEMENT), encoding="utf-8")
            files_changed += 1
            refs_replaced += count

    print(
        f"Visual asset normalization PASS: {refs_replaced} unreliable references "
        f"replaced across {files_changed} source files."
    )


if __name__ == "__main__":
    main()
