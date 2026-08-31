import datetime
import unittest

from scripts.post_pin import DEFAULT_BOARD
from scripts.post_promo_pin_strategic import (
    build_promo_description,
    build_promo_title,
    get_board_config,
    pick_promo_candidate,
)


class PinterestPromoStrategyTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.date(2026, 8, 31)

    def topic(self, slug, published="2026-08-10", cluster="care-troubleshooting"):
        return {
            "title": "Generic editorial title",
            "pin_title": "Original Pin title",
            "pin_description": "Useful rare plant guide.",
            "keywords": ["rare plant care"],
            "cluster": cluster,
            "status": "done",
            "published_date": published,
            "slug": slug,
            "pin_status": "posted",
        }

    def test_syngonium_beats_older_generic_candidate(self):
        generic = self.topic("generic-old-guide", published="2026-08-01")
        syngonium = self.topic(
            "why-your-variegated-syngonium-is-losing-its-color",
            published="2026-08-19",
            cluster="variegation-care",
        )
        selected = pick_promo_candidate({"topics": [generic, syngonium]}, today=self.today)
        self.assertEqual(selected["slug"], syngonium["slug"])

    def test_pending_retry_still_has_absolute_priority(self):
        pending = self.topic("retry-existing")
        pending["promo_pin_status"] = "pending"
        syngonium = self.topic("why-your-variegated-syngonium-is-losing-its-color")
        selected = pick_promo_candidate({"topics": [syngonium, pending]}, today=self.today)
        self.assertEqual(selected["slug"], "retry-existing")

    def test_care_winner_uses_high_reach_care_tips_board(self):
        syngonium = self.topic(
            "why-your-variegated-syngonium-is-losing-its-color",
            cluster="variegation-care",
        )
        self.assertEqual(get_board_config(syngonium), DEFAULT_BOARD)

    def test_buying_content_keeps_buying_board(self):
        buying = self.topic(
            "spotting-rare-plant-scams-online-a-houseplant-buyer-s-guide",
            cluster="buying-market",
        )
        board_name, _ = get_board_config(buying)
        self.assertEqual(board_name, "Rare Plant Buying, Prices & Collecting")

    def test_syngonium_hook_matches_search_language(self):
        syngonium = self.topic("why-your-variegated-syngonium-is-losing-its-color")
        title = build_promo_title(syngonium)
        self.assertEqual(title, "Why Is My Variegated Syngonium Turning Green?")
        self.assertLessEqual(len(title), 100)

    def test_variegation_hook_is_accessible(self):
        topic = self.topic("guide-to-houseplant-variegation-chimeric-pattern-and-viral")
        self.assertEqual(
            build_promo_title(topic),
            "Why Do Houseplants Have Variegated Leaves? 3 Types Explained",
        )

    def test_syngonium_description_does_not_promise_green_leaf_reversal(self):
        syngonium = self.topic("why-your-variegated-syngonium-is-losing-its-color")
        description = build_promo_description(syngonium)
        self.assertIn("Check light, stem color", description)
        self.assertNotIn("restore its beautiful variegation", description.lower())
        self.assertLessEqual(len(description), 500)


if __name__ == "__main__":
    unittest.main()
