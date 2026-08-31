"""Data-driven wrapper around the evergreen Pinterest publisher.

The base publisher remains generic and well-tested. This wrapper changes only three
things based on the 2026-08-31 Google/Pinterest review:
1) which eligible older article gets the next fresh creative;
2) the headline used on a few proven topics;
3) where selected care/setup promos are published.

Buying-market content keeps its dedicated board because that board currently has the
strongest outbound-click efficiency. High-intent care/setup refreshes use the broad
Rare Plant Care Tips board, which currently has the strongest reach.
"""

from scripts import post_promo_pin as base
from scripts.post_pin import DEFAULT_BOARD

ORIGINAL_PICK = base.pick_promo_candidate
ORIGINAL_TITLE = base.build_promo_title
ORIGINAL_BOARD = base.get_board_config

PRIORITY_SLUGS = (
    "why-your-variegated-syngonium-is-losing-its-color",
    "guide-to-houseplant-variegation-chimeric-pattern-and-viral",
    "spotting-rare-plant-scams-online-a-houseplant-buyer-s-guide",
    "best-soil-mix-recipes-for-rare-aroid-collections",
    "humidity-tents-vs-greenhouse-cabinets-for-rare-plants",
)

CARE_TIPS_PROMO_SLUGS = {
    "why-your-variegated-syngonium-is-losing-its-color",
    "guide-to-houseplant-variegation-chimeric-pattern-and-viral",
    "best-soil-mix-recipes-for-rare-aroid-collections",
    "humidity-tents-vs-greenhouse-cabinets-for-rare-plants",
}

TITLE_OVERRIDES = {
    "why-your-variegated-syngonium-is-losing-its-color": "Variegated Syngonium Losing Color? Causes & Fixes",
    "guide-to-houseplant-variegation-chimeric-pattern-and-viral": "Plant Variegation Explained: Chimeric, Pattern & Viral",
    "spotting-rare-plant-scams-online-a-houseplant-buyer-s-guide": "Rare Plant Scams: 7 Red Flags Before You Buy Online",
    "best-soil-mix-recipes-for-rare-aroid-collections": "Best Soil Mix for Rare Aroids: Chunky Recipes That Drain",
    "humidity-tents-vs-greenhouse-cabinets-for-rare-plants": "Rare Plant Cabinet or Humidity Tent? What Works Better?",
}


def pick_promo_candidate(queue, today=None):
    """Retry pending work first, then promote proven topics before generic oldest-first."""
    pending = base.pick_pending_promo(queue)
    if pending:
        return pending

    topics = queue.get("topics", [])
    by_slug = {topic.get("slug"): topic for topic in topics if topic.get("slug")}
    for slug in PRIORITY_SLUGS:
        topic = by_slug.get(slug)
        if not topic:
            continue
        eligible = ORIGINAL_PICK({"topics": [topic]}, today=today)
        if eligible:
            return eligible

    return ORIGINAL_PICK(queue, today=today)


def build_promo_title(topic):
    override = TITLE_OVERRIDES.get(topic.get("slug"))
    return (override or ORIGINAL_TITLE(topic))[:100]


def get_board_config(topic):
    if topic.get("slug") in CARE_TIPS_PROMO_SLUGS:
        return DEFAULT_BOARD
    return ORIGINAL_BOARD(topic)


# Patch the globals looked up by the base module at runtime. This keeps the base
# implementation unchanged while making the production promo run data-driven.
base.pick_promo_candidate = pick_promo_candidate
base.build_promo_title = build_promo_title
base.get_board_config = get_board_config


def main():
    base.main()


if __name__ == "__main__":
    main()
