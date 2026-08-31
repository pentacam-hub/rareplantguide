import unittest
import yaml

from scripts.post_buying_guide_pin import build_commercial_description, build_commercial_title


QUEUE_PATH = "promo-buying-guides.yaml"
TARGET_SLUGS = {
    "best-grow-lights-rare-houseplants",
    "best-humidifiers-for-rare-plants",
    "best-propagation-supplies-variegated-monstera",
}


class CommercialPinCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(QUEUE_PATH, "r", encoding="utf-8") as handle:
            queue = yaml.safe_load(handle) or {"topics": []}
        cls.topics = {
            topic["slug"]: topic
            for topic in queue.get("topics", [])
            if topic.get("slug") in TARGET_SLUGS
        }

    def test_all_target_topics_are_present(self):
        self.assertEqual(set(self.topics), TARGET_SLUGS)

    def test_image_hook_is_not_the_pinterest_title(self):
        for topic in self.topics.values():
            self.assertTrue(topic.get("image_hook"))
            self.assertNotEqual(topic["image_hook"].strip(), build_commercial_title(topic).strip())

    def test_description_adds_information_instead_of_generic_compare_copy(self):
        for topic in self.topics.values():
            description = build_commercial_description(topic)
            self.assertNotIn("Compare options for", description)
            self.assertNotIn("Open the buying guide to compare", description)
            self.assertGreater(len(topic.get("pin_description", "")), 150)

    def test_discovery_hashtags_are_preserved(self):
        for topic in self.topics.values():
            hashtags = topic.get("hashtags", [])
            self.assertGreaterEqual(len(hashtags), 4)
            self.assertLessEqual(len(hashtags), 5)
            description = build_commercial_description(topic)
            for tag in hashtags:
                self.assertIn(tag, description)
            self.assertLessEqual(len(description), 500)


if __name__ == "__main__":
    unittest.main()
