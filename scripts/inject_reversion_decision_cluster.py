"""Connect the proven reversion/variegation cluster to decision and commercial pages.

The source articles already cover diagnosis well. This script avoids cannibalizing them
with duplicate articles and instead creates a clear path:
reversion diagnosis -> node/bud identification -> corrective cut -> propagation -> light setup.

It runs before Hugo and is deliberately idempotent. Missing anchors fail the build so
these links cannot silently disappear after future content edits.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"

NEW_GUIDE = "/posts/where-to-cut-reverting-variegated-monstera/"
NODE_GUIDE = "/posts/monstera-node-vs-axillary-bud-variegated-cutting/"
REVERSION_GUIDE = "/posts/the-heartbreak-of-reversion-why-your-variegated-monstera-is-turning-green-and-how-to-save-it/"
PROPAGATION_GUIDE = "/posts/propagate-variegated-monstera/"
GROW_LIGHT_BUYING = "/buying-guides/best-selling-grow-lights/"


def read(relative: str) -> tuple[Path, str]:
    path = CONTENT / relative
    if not path.exists():
        raise RuntimeError(f"Reversion-cluster target missing: {relative}")
    return path, path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def insert_once(text: str, anchor: str, block: str, marker: str, label: str) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"Reversion-cluster anchor missing: {label}")
    return text.replace(anchor, anchor + block, 1)


def patch_reversion_article() -> None:
    path, text = read(
        "posts/the-heartbreak-of-reversion-why-your-variegated-monstera-is-turning-green-and-how-to-save-it.md"
    )
    anchor = (
        "**Can Monstera reversion be reversed?** Sometimes—but only if a lower node or axillary bud "
        "still intersects variegated stem tissue. A fully green active growth point will not turn "
        "variegated again simply because you add more light or fertilizer."
    )
    marker = "<!-- REVERSION_DECISION_PATH -->"
    block = f"""

{marker}
## What Should You Do Next?

If Google already gave you the short answer, use the next step that matches the decision you still need to make:

- **Not sure which structure will regrow?** See [Monstera Node vs Axillary Bud]({NODE_GUIDE}).
- **Confirmed reversion and ready to prune?** Use [Where to Cut a Reverting Variegated Monstera]({NEW_GUIDE}).
- **Want to save the removed top?** Follow [How to Propagate Variegated Monstera]({PROPAGATION_GUIDE}) if it contains a viable node.
- **Need supplemental light after pruning?** Compare the [3 Best Grow Lights for Rare Plants]({GROW_LIGHT_BUYING}) after confirming that light is actually limiting.

The important distinction is that **light supports growth; it does not recreate variegated tissue in a fully green growth point**. If true reversion is confirmed, the actionable decision is which lower node to keep.
"""
    text = insert_once(text, anchor, block, marker, "reversion decision path")
    if NEW_GUIDE not in text or GROW_LIGHT_BUYING not in text:
        raise RuntimeError("Reversion article is missing decision/commercial links")
    write(path, text)


def patch_node_article() -> None:
    path, text = read("posts/monstera-node-vs-axillary-bud-variegated-cutting.md")
    anchor = (
        "That distinction is especially important when trying to correct a reverting Monstera. "
        "The detailed guide [Variegated Monstera Turning Green? How to Stop Reversion]"
        f"({REVERSION_GUIDE}) explains how to trace the vine back to a more promising node."
    )
    marker = "<!-- NODE_TO_REVERSION_CUT -->"
    block = f"""

{marker}
If you have already confirmed reversion and the remaining question is **where to make the corrective cut**, use [Where to Cut a Reverting Variegated Monstera]({NEW_GUIDE}). It focuses on choosing the lower node to keep and protecting its axillary bud during the cut.
"""
    text = insert_once(text, anchor, block, marker, "node-to-cut decision link")
    if NEW_GUIDE not in text:
        raise RuntimeError("Node article is missing corrective-cut link")
    write(path, text)


def patch_problem_page(relative: str, insert_after: str, label: str) -> None:
    path, text = read(relative)
    if NEW_GUIDE in text:
        return
    block = f'''{insert_after}
  - title: "Where to Cut a Reverting Variegated Monstera"
    text: "If reversion is confirmed, choose the lower node and protect the axillary bud before making the corrective cut."
    url: "{NEW_GUIDE}"'''
    if insert_after not in text:
        raise RuntimeError(f"Reversion-cluster problem-page anchor missing: {label}")
    text = text.replace(insert_after, block, 1)
    if NEW_GUIDE not in text:
        raise RuntimeError(f"Problem page missing new decision guide: {label}")
    write(path, text)


def patch_problem_pages() -> None:
    turning_anchor = '''  - title: "How Variegation Works"
    text: "Understand chimeric, pattern-gene and viral variegation."
    url: "/posts/guide-to-houseplant-variegation-chimeric-pattern-and-viral/"'''
    losing_anchor = '''  - title: "Guide to Houseplant Variegation"
    text: "Learn the main mechanisms behind variegated foliage."
    url: "/posts/guide-to-houseplant-variegation-chimeric-pattern-and-viral/"'''
    patch_problem_page("plant-problems/turning-green.md", turning_anchor, "turning-green")
    patch_problem_page("plant-problems/losing-variegation.md", losing_anchor, "losing-variegation")


def patch_monstera_hub() -> None:
    path, text = read("variegated-monstera.md")
    if NEW_GUIDE in text:
        return
    anchor = f'''      - kicker: "Top guide"
        title: "Variegated Monstera Turning Green? Can Reversion Be Reversed?"
        text: "Check the stem, node and axillary bud, then learn when pruning back can help."
        url: "{REVERSION_GUIDE}"'''
    block = f'''{anchor}
      - kicker: "Action guide"
        title: "Where to Cut a Reverting Variegated Monstera"
        text: "Once reversion is confirmed, choose the lower node to keep and make the corrective cut without damaging the axillary bud."
        url: "{NEW_GUIDE}"
      - kicker: "Node anatomy"
        title: "Monstera Node vs Axillary Bud"
        text: "Identify the node, dormant bud and aerial root before pruning or buying a cutting."
        url: "{NODE_GUIDE}"'''
    if anchor not in text:
        raise RuntimeError("Variegated Monstera hub anchor missing")
    text = text.replace(anchor, block, 1)
    if NEW_GUIDE not in text or NODE_GUIDE not in text:
        raise RuntimeError("Variegated Monstera hub missing decision links")
    write(path, text)


def verify() -> None:
    targets = [
        "posts/the-heartbreak-of-reversion-why-your-variegated-monstera-is-turning-green-and-how-to-save-it.md",
        "posts/monstera-node-vs-axillary-bud-variegated-cutting.md",
        "plant-problems/turning-green.md",
        "plant-problems/losing-variegation.md",
        "variegated-monstera.md",
    ]
    for relative in targets:
        path, text = read(relative)
        if NEW_GUIDE not in text:
            raise RuntimeError(f"Reversion decision cluster verification failed: {relative}")


def main() -> None:
    patch_reversion_article()
    patch_node_article()
    patch_problem_pages()
    patch_monstera_hub()
    verify()
    print(
        "Reversion decision cluster PASS: diagnosis -> node -> cut -> propagation -> grow-light path connected."
    )


if __name__ == "__main__":
    main()
