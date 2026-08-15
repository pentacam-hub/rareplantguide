import unittest

from scripts.generate_post import (
    BODY_MARK,
    DESCRIPTION_MARK,
    TAGS_MARK,
    TITLE_MARK,
    build_markdown_file,
    extract_faq,
    parse_article_response,
    validate_article,
)


def make_body(first_person=False):
    pronoun = " My collection confirms this." if first_person else ""
    padding = " ".join(["careful plant observation supports practical decisions"] * 145)
    return f"""Start by checking the whole plant before changing its care routine.{pronoun}

## Identify the visible signs

{padding}

## Check the growing conditions

Compare moisture, light, temperature, and airflow before choosing a treatment.
Read the [root rot guide](/posts/root-rot-guide/) for a careful inspection process.

## Correct the immediate problem

Make one change at a time and monitor new growth rather than damaged leaves.

## Prevent the problem from returning

Use the [rare plant care guide](/posts/rare-plant-care-guide/) to build a consistent routine.

## Frequently Asked Questions

### Can one yellow leaf be normal?

Yes. An older lower leaf can yellow naturally when the rest of the plant remains healthy.

### Should damaged leaves be removed immediately?

Remove a leaf only when it is fully damaged or creating a sanitation problem.

### How quickly should care changes work?

Judge recovery through stable new growth over several weeks rather than changes to old damage.
"""


class GeneratorQualityTests(unittest.TestCase):
    def test_parse_response(self):
        response = f"""{TITLE_MARK}
How to Diagnose Common Rare Houseplant Problems
{DESCRIPTION_MARK}
Learn how to inspect common rare houseplant symptoms, narrow down likely causes, and choose safe next steps without guesswork.
{TAGS_MARK}
plant care, troubleshooting
{BODY_MARK}
{make_body()}
"""
        article = parse_article_response(response)
        self.assertEqual(article["title"], "How to Diagnose Common Rare Houseplant Problems")
        self.assertEqual(article["tags"], ["plant care", "troubleshooting"])

    def test_valid_article_passes_quality_gate(self):
        article = {
            "title": "How to Diagnose Common Rare Houseplant Problems",
            "description": "Learn how to inspect common rare houseplant symptoms, narrow down likely causes, and choose safe next steps without guesswork.",
            "tags": ["plant care", "troubleshooting"],
            "body_markdown": make_body(),
        }
        links = [("Root Rot Guide", "root-rot-guide"), ("Care Guide", "rare-plant-care-guide")]
        self.assertEqual(validate_article(article, internal_links=links), [])
        self.assertEqual(len(article["faq"]), 3)

    def test_first_person_claim_is_rejected(self):
        article = {
            "title": "How to Diagnose Common Rare Houseplant Problems",
            "description": "Learn how to inspect common rare houseplant symptoms, narrow down likely causes, and choose safe next steps without guesswork.",
            "tags": ["plant care", "troubleshooting"],
            "body_markdown": make_body(first_person=True),
        }
        errors = validate_article(article, internal_links=[])
        self.assertTrue(any("first-person language" in error for error in errors))

    def test_faq_is_extracted_and_serialized(self):
        faq = extract_faq(make_body())
        article = {
            "title": "How to Diagnose Common Rare Houseplant Problems",
            "description": "Learn how to inspect common rare houseplant symptoms, narrow down likely causes, and choose safe next steps without guesswork.",
            "tags": ["plant care", "troubleshooting"],
            "body_markdown": make_body(),
            "faq": faq,
        }
        markdown = build_markdown_file(article, None, "2026-08-15")
        self.assertIn("faq:", markdown)
        self.assertIn('question: "Can one yellow leaf be normal?"', markdown)


if __name__ == "__main__":
    unittest.main()
