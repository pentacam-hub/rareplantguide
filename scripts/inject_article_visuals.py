"""Ensure every editorial post has a relevant, local cover image before Hugo renders it.

This is intentionally deterministic: existing covers are preserved; posts without a
cover receive a topic-matched image that already exists under static/images. The
script is idempotent and fails if a configured asset disappears.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "content" / "posts"
STATIC = ROOT / "static"

RULES = [
    (("node", "axillary bud"), "/images/monstera-node-vs-axillary-bud-comparison.webp", "Monstera node and axillary bud comparison"),
    (("reversion", "turning green", "reverting"), "/images/the-heartbreak-of-reversion-why-your-variegated-monstera-is-turning-green-and-how-to-save-it.jpg", "Variegated Monstera showing green and white variegation"),
    (("syngonium",), "/images/why-your-variegated-syngonium-is-losing-its-color.jpg", "Variegated Syngonium foliage"),
    (("variegation", "variegated"), "/images/guide-to-houseplant-variegation-chimeric-pattern-and-viral.jpg", "Variegated houseplant foliage pattern"),
    (("root rot", "root-rot"), "/images/how-to-spot-and-treat-philodendron-root-rot-before-it-s-too-late.jpg", "Philodendron roots being inspected for root rot"),
    (("thrips", "mites", "pest"), "/images/houseplant-pest-inspection.jpg", "Houseplant leaf being inspected for pests"),
    (("sphagnum",), "/images/is-sphagnum-moss-actually-the-holy-grail-for-rare-plant-propagation.jpg", "Sphagnum moss used for rare plant propagation"),
    (("propagat", "cutting", "wet stick"), "/images/propagation-water-rooting.jpg", "Rare plant cutting developing roots during propagation"),
    (("soil", "repot", "potting"), "/images/chunky-aroid-soil-mix.jpg", "Chunky aroid soil mix for rare houseplants"),
    (("grow light", "light requirement", "light needs"), "/images/grow-light-setup.jpg", "Indoor rare plants growing under a grow light"),
    (("humidity", "humidifier", "greenhouse cabinet"), "/images/humidity-tents-vs-greenhouse-cabinets-for-rare-plants.jpg", "Rare plants growing in a controlled humidity setup"),
    (("tissue culture", "tissue-cultur"), "/images/is-it-worth-buying-tissue-cultured-rare-plants-a-honest-guide-for-hobbyists.jpg", "Young tissue-cultured rare plants"),
    (("scam", "buying rare plants"), "/images/spotting-rare-plant-scams-online-a-houseplant-buyer-s-guide.jpg", "Buying rare houseplants online"),
]

DEFAULT = (
    "/images/monstera-variegated-hero.jpg",
    "Variegated Monstera and rare houseplant foliage",
)


def choose_cover(path: Path, text: str):
    haystack = f"{path.stem} {text[:2200]}".lower()
    for keywords, image, alt in RULES:
        if any(keyword in haystack for keyword in keywords):
            return image, alt
    return DEFAULT


def add_cover(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if len(text) < 350 or not text.startswith("---\n"):
        return False

    end = text.find("\n---", 4)
    if end == -1:
        raise RuntimeError(f"Invalid front matter: {path.relative_to(ROOT)}")

    front = text[4:end]
    if re.search(r"(?m)^cover:\s*$", front):
        return False

    image, alt = choose_cover(path, text)
    asset = STATIC / image.lstrip("/")
    if not asset.exists():
        raise RuntimeError(f"Cover asset missing: {asset.relative_to(ROOT)}")

    block = (
        f'\ncover:\n'
        f'    image: "{image}"\n'
        f'    alt: "{alt}"\n'
        f'    relative: false\n'
    )
    patched = text[:end] + block + text[end:]
    path.write_text(patched, encoding="utf-8")
    return True


def main():
    changed = 0
    checked = 0
    for path in sorted(POSTS.glob("*.md")):
        if path.name == "_index.md":
            continue
        checked += 1
        changed += int(add_cover(path))

    # Verify the rendered editorial set can never silently return to text-only posts.
    missing = []
    for path in sorted(POSTS.glob("*.md")):
        if path.name == "_index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if len(text) >= 350 and not re.search(r"(?m)^cover:\s*$", text):
            missing.append(path.name)
    if missing:
        raise RuntimeError("Posts still missing covers: " + ", ".join(missing))

    print(f"Article visual coverage PASS: {checked} posts checked; {changed} fallback covers added.")


if __name__ == "__main__":
    main()
