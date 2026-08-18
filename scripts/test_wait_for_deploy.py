import unittest

from scripts.wait_for_deploy import pending_urls


class DeployWaitTests(unittest.TestCase):
    def test_builds_urls_for_pending_original_pins(self):
        queue = {
            "topics": [
                {
                    "status": "done",
                    "pin_status": "pending",
                    "slug": "root-rot-guide",
                    "pin_image_path": "/images/pins/root-rot-guide.jpg",
                },
                {
                    "status": "done",
                    "pin_status": "pending",
                    "slug": "second-guide",
                    "pin_image_path": "/images/pins/second-guide.jpg",
                },
            ]
        }
        urls = pending_urls(queue, kind="original", limit=2)
        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[0]["article"].endswith("/posts/root-rot-guide/"))
        self.assertTrue(urls[1]["image"].endswith("/images/pins/second-guide.jpg"))

    def test_builds_urls_for_pending_promo_pin(self):
        queue = {
            "topics": [
                {
                    "status": "done",
                    "slug": "root-rot-guide",
                    "promo_pin_status": "pending",
                    "promo_pin_image_path": "/images/pins/root-rot-guide-save-guide.jpg",
                }
            ]
        }
        urls = pending_urls(queue, kind="promo", limit=1)
        self.assertEqual(len(urls), 1)
        self.assertTrue(urls[0]["image"].endswith("root-rot-guide-save-guide.jpg"))

    def test_returns_empty_without_pending_pin(self):
        self.assertEqual(pending_urls({"topics": []}), [])


if __name__ == "__main__":
    unittest.main()
