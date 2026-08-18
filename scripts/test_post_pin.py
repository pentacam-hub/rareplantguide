import unittest

from scripts.post_pin import (
    build_alt_text,
    build_pin_description,
    canonical_link,
    get_board_config,
    pick_pending_pin,
    pick_pending_pins,
)


class PinterestQueueTests(unittest.TestCase):
    def test_returns_only_oldest_pending_pin(self):
        queue = {
            "topics": [
                {"slug": "already-posted", "status": "done", "pin_status": "posted"},
                {"slug": "retry-first", "status": "done", "pin_status": "pending"},
                {"slug": "wait-until-tomorrow", "status": "done", "pin_status": "pending"},
            ]
        }
        self.assertEqual(pick_pending_pin(queue)["slug"], "retry-first")

    def test_can_select_two_pending_pins_for_backlog_recovery(self):
        queue = {
            "topics": [
                {"slug": "first", "status": "done", "pin_status": "pending"},
                {"slug": "second", "status": "done", "pin_status": "pending"},
                {"slug": "third", "status": "done", "pin_status": "pending"},
            ]
        }
        self.assertEqual(
            [item["slug"] for item in pick_pending_pins(queue, 2)],
            ["first", "second"],
        )

    def test_ignores_unpublished_article(self):
        queue = {"topics": [{"status": "pending", "pin_status": "pending"}]}
        self.assertIsNone(pick_pending_pin(queue))


class PinterestSeoTests(unittest.TestCase):
    def setUp(self):
        self.topic = {
            "title": "How to Treat Philodendron Root Rot",
            "pin_title": "How to Treat Philodendron Root Rot Before It Spreads",
            "pin_description": "Learn the warning signs and the rescue steps for an overwatered philodendron.",
            "keywords": ["root rot", "philodendron care", "overwatering"],
            "cluster": "care-troubleshooting",
        }

    def test_description_contains_keywords_and_save_cta(self):
        description = build_pin_description(self.topic)
        self.assertIn("root rot", description)
        self.assertIn("philodendron care", description)
        self.assertIn("Save this guide", description)
        self.assertLessEqual(len(description), 500)

    def test_alt_text_is_descriptive(self):
        alt_text = build_alt_text(self.topic)
        self.assertIn(self.topic["pin_title"], alt_text)
        self.assertIn("overwatering", alt_text)
        self.assertLessEqual(len(alt_text), 500)

    def test_topic_routes_to_search_friendly_board(self):
        board_name, board_description = get_board_config(self.topic)
        self.assertEqual(board_name, "Rare Plant Problems & Care Solutions")
        self.assertIn("root rot", board_description.lower())

    def test_unknown_cluster_uses_default_board(self):
        board_name, _ = get_board_config({"cluster": "unknown"})
        self.assertEqual(board_name, "Rare Plant Care Tips")

    def test_canonical_link_ignores_query_and_trailing_slash(self):
        self.assertEqual(
            canonical_link("https://therareplantguide.com/posts/example/?utm_source=pinterest"),
            canonical_link("https://therareplantguide.com/posts/example"),
        )


if __name__ == "__main__":
    unittest.main()
