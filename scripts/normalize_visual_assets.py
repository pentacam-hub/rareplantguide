"""Normalize visual assets before Hugo renders the production site.

This is a production-safety layer for old content/data that can otherwise leak blank
or duplicate imagery into the rendered site. It runs only in the build workspace.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAD = "/images/monstera-node-vs-axillary-bud-comparison.webp"
REPLACEMENT = "/images/guide-to-houseplant-variegation-chimeric-pattern-and-viral.jpg"
SCAN_DIRS = (ROOT / "data", ROOT / "content", ROOT / "layouts")
TEXT_SUFFIXES = {".yaml", ".yml", ".md", ".html", ".toml", ".json"}

# Exact contextual repairs for places where two otherwise-valid references would
# produce the same photograph in one visual grid after normalization.
CONTEXTUAL_REPLACEMENTS = (
    (
        '    - title: "Run a consistent schedule"\n'
        '      text: "Stable daily timing is easier for plants than constant manual changes."\n'
        '      image: "/images/grow-light-setup.jpg"',
        '    - title: "Run a consistent schedule"\n'
        '      text: "Stable daily timing is easier for plants than constant manual changes."\n'
        '      image: "/images/humidity-tents-vs-greenhouse-cabinets-for-rare-plants.jpg"',
    ),
    (
        '    - title: "Monstera Node vs Axillary Bud"\n'
        '      text: "Identify the structures that matter before pruning."\n'
        '      url: "/posts/monstera-node-vs-axillary-bud-variegated-cutting/"\n'
        f'      image: "{REPLACEMENT}"',
        '    - title: "Monstera Node vs Axillary Bud"\n'
        '      text: "Identify the structures that matter before pruning."\n'
        '      url: "/posts/monstera-node-vs-axillary-bud-variegated-cutting/"\n'
        '      image: "/images/plant-propagation-cutting.jpg"',
    ),
)


def main() -> None:
    replacement_asset = ROOT / "static" / REPLACEMENT.lstrip("/")
    if not replacement_asset.is_file() or replacement_asset.stat().st_size < 1024:
        raise RuntimeError(f"Replacement visual missing or invalid: {replacement_asset.relative_to(ROOT)}")

    files_changed: set[Path] = set()
    refs_replaced = 0
    contextual_repairs = 0

    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            original = text

            count = text.count(BAD)
            if count:
                text = text.replace(BAD, REPLACEMENT)
                refs_replaced += count

            for before, after in CONTEXTUAL_REPLACEMENTS:
                count = text.count(before)
                if count:
                    text = text.replace(before, after)
                    contextual_repairs += count

            if text != original:
                path.write_text(text, encoding="utf-8")
                files_changed.add(path)

    print(
        f"Visual asset normalization PASS: {refs_replaced} unreliable references and "
        f"{contextual_repairs} duplicate-grid references repaired across "
        f"{len(files_changed)} source files."
    )


if __name__ == "__main__":
    main()
