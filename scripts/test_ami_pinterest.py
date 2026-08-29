import os
import tempfile
import unittest

import yaml
from PIL import Image

from scripts.ami_pinterest import (
    build_alt_text,
    build_pin_image,
    canonical_link,
    pick_pending_pin,
)


class AnalyzeMyIncomePinterestTests(unittest.TestCase):
    def test_pick_pending_pin_uses_queue_order(self):
        queue = {
            "pins": [
                {"id": "one", "status": "posted"},
                {"id": "two", "status": "pending"},
                {"id": "three", "status": "pending"},
            ]
        }
        self.assertEqual(pick_pending_pin(queue)["id"], "two")

    def test_canonical_link_removes_query_fragment_and_trailing_slash(self):
        self.assertEqual(
            canonical_link("https://AnalyzeMyIncome.com/1099-tax-calculator/?utm_source=pinterest#x"),
            "https://analyzemyincome.com/1099-tax-calculator",
        )

    def test_alt_text_is_bounded(self):
        pin = {
            "kicker": "1099 TAX CALCULATOR",
            "graphic_title": "See What You May Owe in 2026",
        }
        self.assertLessEqual(len(build_alt_text(pin)), 500)
        self.assertIn("Analyze My Income", build_alt_text(pin))

    def test_generated_pin_is_pinterest_vertical_jpeg(self):
        previous = os.environ.get("RUNNER_TEMP")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RUNNER_TEMP"] = tmp
            pin = {
                "id": "test-pin",
                "title": "1099 Tax Calculator",
                "kicker": "1099 TAX CALCULATOR",
                "graphic_title": "See What You May Owe in 2026",
            }
            path = build_pin_image(pin)
            self.assertTrue(os.path.isfile(path))
            with Image.open(path) as image:
                self.assertEqual(image.size, (1000, 1500))
                self.assertEqual(image.format, "JPEG")
        if previous is None:
            os.environ.pop("RUNNER_TEMP", None)
        else:
            os.environ["RUNNER_TEMP"] = previous

    def test_seed_queue_has_required_fields(self):
        with open("ami-pinterest-queue.yaml", "r", encoding="utf-8") as handle:
            queue = yaml.safe_load(handle)
        pins = queue["pins"]
        self.assertGreaterEqual(len(pins), 12)
        for pin in pins:
            for field in ["id", "status", "title", "description", "board", "destination", "kicker", "graphic_title"]:
                self.assertTrue(pin.get(field), f"{pin.get('id')} missing {field}")
            self.assertTrue(pin["destination"].startswith("https://analyzemyincome.com/"))


if __name__ == "__main__":
    unittest.main()
