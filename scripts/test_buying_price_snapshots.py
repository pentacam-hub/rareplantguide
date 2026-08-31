import unittest

from scripts.inject_buying_price_snapshots import SNAPSHOT_NOTE, patch_html


class BuyingGuidePriceSnapshotTests(unittest.TestCase):
    def test_replaces_price_placeholder_for_known_asin(self):
        html = (
            '<div class="amazon-live-price amazon-live-price-compact" '
            'data-amazon-price="B091DLFDL9">'
            '<span class="amazon-price-label">Amazon price</span>'
            '<strong class="amazon-price-value">Check current price</strong>'
            '<small class="amazon-price-updated">Current price opens on Amazon</small>'
            '</div>'
        )
        patched, count = patch_html(html)
        self.assertEqual(count, 1)
        self.assertIn('$8.99', patched)
        self.assertIn(SNAPSHOT_NOTE, patched)
        self.assertNotIn('Check current price', patched)

    def test_leaves_unknown_asin_unchanged(self):
        html = (
            '<div class="amazon-live-price" data-amazon-price="UNKNOWN">'
            '<strong class="amazon-price-value">Check current price</strong>'
            '</div>'
        )
        patched, count = patch_html(html)
        self.assertEqual(count, 0)
        self.assertEqual(patched, html)


if __name__ == "__main__":
    unittest.main()
