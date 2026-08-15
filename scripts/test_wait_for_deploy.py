import unittest

from scripts.wait_for_deploy import pending_urls


class DeployWaitTests(unittest.TestCase):
    def test_builds_urls_for_oldest_pending_pin(self):
        queue = {
            "topics": [
                {
                    "status": "done",
                    "pin_status": "pending",
                    "slug": "root-rot-guide",
                    "pin_image_path": "/images/pins/root-rot-guide.jpg",
                }
            ]
        }
        urls = pending_urls(queue)
        self.assertTrue(urls["article"].endswith("/posts/root-rot-guide/"))
        self.assertTrue(urls["image"].endswith("/images/pins/root-rot-guide.jpg"))

    def test_returns_none_without_pending_pin(self):
        self.assertIsNone(pending_urls({"topics": []}))


if __name__ == "__main__":
    unittest.main()
