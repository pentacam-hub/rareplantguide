"""Build-time SEO refinements for pages already earning Google impressions.

These are deliberately narrow, data-driven edits based on the 2026-08-31 Search
Console review. They improve existing URLs rather than creating competing pages.
The script is idempotent and fails if a targeted page disappears.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
REVIEW_DATE = "2026-08-31"

OVERRIDES = {
    "posts/the-heartbreak-of-reversion-why-your-variegated-monstera-is-turning-green-and-how-to-save-it.md": {
        "title": "Variegated Monstera Turning Green? How to Stop Reversion",
        "description": "Is your Monstera Albo producing greener leaves? Learn how to check the stem and nodes, when pruning can restore variegated growth, and when light can help.",
    },
    "posts/why-your-variegated-syngonium-is-losing-its-color.md": {
        "title": "Why Is My Variegated Syngonium Turning Green? How to Fix It",
        "description": "If your Syngonium is losing pink or white variegation, check light, stem color and new growth. Learn when better light helps and when pruning is needed.",
        "intro_old": "When a variegated syngonium suddenly begins producing plain, solid green leaves, the cause is typically a shift in environmental conditions or a natural genetic response to stress. Variegated plants contain less chlorophyll than their solid green counterparts, which means they must work harder to photosynthesize. If the growing environment does not support this extra effort, or if the plant undergoes a genetic shift, the vibrant cream, white, or yellow patches will begin to fade or disappear entirely in new growth. Understanding why this happens and taking prompt action can help encourage the plant to produce those highly sought-after patterns once again.",
        "intro_new": "If your **variegated Syngonium is losing color**, do not diagnose reversion from one green leaf. Look at the newest leaves together with the **stem and active growth point**.\n\n**Quick answer:** several solid-green leaves plus an increasingly green stem are stronger signs of reversion. Better light can support healthy growth, but it cannot recreate variegated tissue in a growth point that has become fully green. If a lower node still crosses variegated stem tissue, pruning back to that node may give the next growth point a better chance of producing variegation.",
    },
    "posts/guide-to-houseplant-variegation-chimeric-pattern-and-viral.md": {
        "title": "Why Do Houseplants Have Variegated Leaves? 3 Types Explained",
        "description": "Learn the difference between chimeric, genetic and viral variegation, how to identify each type, and what it means for growth and propagation.",
    },
    "posts/is-sphagnum-moss-actually-the-holy-grail-for-rare-plant-propagation.md": {
        "title": "Sphagnum Moss for Rare Plant Propagation: Pros, Rot Risks & Transfer",
        "description": "Use sphagnum moss for Monstera and rare plant propagation without suffocating the node. Learn moisture level, rot warning signs and when to transfer rooted cuttings.",
        "intro_old": "Long-fiber sphagnum moss is popular for rooting Monstera, Philodendron, and other aroid cuttings because it can hold moisture while leaving space for air. It is not a foolproof medium: when saturated, compressed, or sealed without ventilation, it can keep a node too wet and contribute to rot.\n\nThe result depends more on preparation, container design, temperature, and monitoring than on the moss itself.",
        "intro_new": "Long-fiber sphagnum moss can work very well for Monstera, Philodendron and other rare-plant cuttings, but only when the node gets **moisture and oxygen at the same time**.\n\n**Quick answer:** use sphagnum loose and evenly damp—not dripping wet or tightly packed. Saturated, airless moss is the main rot risk. Transfer a cutting after it has several healthy roots, preferably with some secondary branching, and keep the new potting mix consistently but not excessively moist during acclimation.",
    },
}

BROKEN_LINK = "/posts/rare-plant-losing-variegation/"
CORRECT_LINK = "/plant-problems/losing-variegation/"
LINK_FILES = ["rare-plant-care.md", "variegated-monstera.md"]


def set_frontmatter_value(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf'(?m)^{re.escape(key)}:\s*".*"\s*$')
    replacement = f'{key}: "{value}"'
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    raise RuntimeError(f"Missing front-matter field: {key}")


def set_lastmod(text: str) -> str:
    if re.search(r"(?m)^lastmod:", text):
        return re.sub(r"(?m)^lastmod:.*$", f"lastmod: {REVIEW_DATE}", text, count=1)
    date_match = re.search(r"(?m)^date:.*$", text)
    if not date_match:
        raise RuntimeError("Missing date field while adding lastmod")
    end = date_match.end()
    return text[:end] + f"\nlastmod: {REVIEW_DATE}" + text[end:]


def patch_winner(relative: str, config: dict) -> None:
    path = CONTENT / relative
    if not path.exists():
        raise RuntimeError(f"Search-winner page missing: {relative}")
    text = path.read_text(encoding="utf-8")
    text = set_frontmatter_value(text, "title", config["title"])
    text = set_frontmatter_value(text, "description", config["description"])
    text = set_lastmod(text)

    old_intro = config.get("intro_old")
    if old_intro:
        new_intro = config["intro_new"]
        if new_intro not in text:
            if old_intro not in text:
                raise RuntimeError(f"Expected intro not found in {relative}")
            text = text.replace(old_intro, new_intro, 1)

    if config["title"] not in text or config["description"] not in text:
        raise RuntimeError(f"SEO verification failed for {relative}")
    path.write_text(text, encoding="utf-8")


def fix_cluster_links() -> None:
    for relative in LINK_FILES:
        path = CONTENT / relative
        if not path.exists():
            raise RuntimeError(f"Hub page missing: {relative}")
        text = path.read_text(encoding="utf-8")
        if BROKEN_LINK in text:
            text = text.replace(BROKEN_LINK, CORRECT_LINK)
        if BROKEN_LINK in text or CORRECT_LINK not in text:
            raise RuntimeError(f"Variegation hub-link verification failed: {relative}")
        path.write_text(text, encoding="utf-8")


def main() -> None:
    for relative, config in OVERRIDES.items():
        patch_winner(relative, config)
    fix_cluster_links()
    print(
        "Search winner optimization PASS: 4 proven URLs refreshed; "
        "variegation hub links corrected; no new URLs created."
    )


if __name__ == "__main__":
    main()
