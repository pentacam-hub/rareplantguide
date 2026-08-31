import datetime
import unittest

from scripts.post_buying_guide_pin import (
    COMMERCIAL_MIN_GAP_DAYS,
    build_commercial_description,
    commercial_slot_open,
    destination_url,
    pick_topic,
)


class CommercialPinterestTests(unittest.TestCase):
    def topic(self, slug, status="pending", priority=999):
        return {
            "title": "Buying guide",
            "pin_title": "Buying guide Pin",
            "pin_description": "Compare practical options for rare plant growers.",
            "keywords": ["rare plant gear", "plant setup"],
            "slug": slug,
            "status": status,
            "priority": priority,
        }

    def test_destination_path_routes_to_buying_guide(self):
        topic = self.topic("best-grow-lights-rare-houseplants")
        topic["destination_path"] = "/buying-guides/best-selling-grow-lights/"
        self.assertEqual(
            destination_url(topic),
            "https://therareplantguide.com/buying-guides/best-selling-grow-lights/",
        )

    def test_destination_falls_back_to_legacy_post_url(self):
        topic = self.topic("legacy-guide")
        self.assertEqual(
            destination_url(topic),
            "https://therareplantguide.com/posts/legacy-guide/",
        )

    def test_lower_priority_number_wins(self):
        humidifier = self.topic("humidifier", priority=2)
        grow_lights = self.topic("grow-lights", priority=1)
        propagation = self.topic("propagation", priority=3)
        selected = pick_topic(
            {"topics": [humidifier, propagation, grow_lights]}, {"pending"}
        )
        self.assertEqual(selected["slug"], "grow-lights")

    def test_commercial_cooldown_blocks_same_and_next_day(self):
        posted = self.topic("already-posted", status="posted")
        posted["published_pin_date"] = "2026-08-31"
        queue = {"topics": [posted, self.topic("next")]}
        self.assertFalse(
            commercial_slot_open(queue, today=datetime.date(2026, 9, 1))
        )
        self.assertTrue(
            commercial_slot_open(
                queue,
                today=datetime.date(2026, 8, 31)
                + datetime.timedelta(days=COMMERCIAL_MIN_GAP_DAYS),
            )
        )

    def test_old_commercial_pin_allows_next_candidate(self):
        posted = self.topic("old", status="posted")
        posted["published_pin_date"] = "2026-08-28"
        queue = {"topics": [posted, self.topic("next")]}
        self.assertTrue(
            commercial_slot_open(queue, today=datetime.date(2026, 8, 31))
        )

    def test_description_is_buying_guide_led(self):
        description = build_commercial_description(self.topic("guide"))
        self.assertIn("Open the buying guide", description)
        self.assertLessEqual(len(description), 500)


if __name__ == "__main__":
    unittest.main()
