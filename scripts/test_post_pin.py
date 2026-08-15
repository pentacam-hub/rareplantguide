import unittest

from scripts.post_pin import pick_pending_pin


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

    def test_ignores_unpublished_article(self):
        queue = {"topics": [{"status": "pending", "pin_status": "pending"}]}
        self.assertIsNone(pick_pending_pin(queue))


if __name__ == "__main__":
    unittest.main()
