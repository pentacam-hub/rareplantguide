import datetime
import unittest

from scripts.post_promo_pin import (
    build_promo_description,
    build_promo_title,
    pick_promo_candidate,
)


class EvergreenPinterestTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.date(2026, 8, 17)
        self.topic = {
            "title": "Signs of Root Rot in Philodendrons (And How to Save Them)",
            "pin_title": "How to Spot and Treat Philodendron Root Rot Before It's Too Late",
            "pin_description": "Learn the early warning signs of root rot and a practical rescue plan.",
            "keywords": ["root rot", "philodendron care", "overwatering"],
            "cluster": "care-troubleshooting",
            "status": "done",
            "published_date": "2026-08-10",
            "slug": "root-rot-guide",
            "pin_status": "posted_manual",
        }

    def test_picks_oldest_eligible_article(self):
        newer = dict(self.topic, slug="newer", published_date="2026-08-12")
        older = dict(self.topic, slug="older", published_date="2026-08-04")
        queue = {"topics": [newer, older]}
        self.assertEqual(pick_promo_candidate(queue, today=self.today)["slug"], "older")

    def test_requires_original_pin_to_be_posted(self):
        unposted = dict(self.topic, pin_status="pending")
        self.assertIsNone(pick_promo_candidate({"topics": [unposted]}, today=self.today))

    def test_waits_three_days_before_second_pin(self):
        too_new = dict(self.topic, published_date="2026-08-16")
        self.assertIsNone(pick_promo_candidate({"topics": [too_new]}, today=self.today))

    def test_does_not_repeat_completed_promo(self):
        completed = dict(self.topic, promo_pin_status="posted")
        self.assertIsNone(pick_promo_candidate({"topics": [completed]}, today=self.today))

    def test_pending_promo_is_retried_first(self):
        pending = dict(self.topic, promo_pin_status="pending", slug="retry-me")
        older = dict(self.topic, slug="older", published_date="2026-08-04")
        queue = {"topics": [pending, older]}
        self.assertEqual(pick_promo_candidate(queue, today=self.today)["slug"], "retry-me")

    def test_promo_title_is_distinct_from_original_pin_title(self):
        self.assertEqual(build_promo_title(self.topic), self.topic["title"])
        self.assertNotEqual(build_promo_title(self.topic), self.topic["pin_title"])

    def test_promo_description_has_primary_keyword_and_save_cta(self):
        description = build_promo_description(self.topic)
        self.assertIn("root rot", description)
        self.assertIn("Save this practical", description)
        self.assertLessEqual(len(description), 500)


if __name__ == "__main__":
    unittest.main()
