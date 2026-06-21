"""Tests for contributor flair helpers."""

import unittest

from contributor_flair import (
    build_user_flair_text,
    calculate_milestone_tier,
    parse_milestone_tiers,
    truncate_flair_text,
)


class TestContributorFlair(unittest.TestCase):
    def test_milestone_tiers(self):
        self.assertEqual(calculate_milestone_tier(100), "Veteran Accelerator")
        self.assertEqual(calculate_milestone_tier(3), "Newcomer")
        self.assertIsNone(calculate_milestone_tier(0))

    def test_build_flair_text_omits_empty(self):
        text = build_user_flair_text(acceleration="Hypersonic", milestone="Regular", specialist=None)
        self.assertEqual(text, "Hypersonic | Regular")

    def test_truncate(self):
        long = "A" * 80
        self.assertLessEqual(len(truncate_flair_text(long)), 64)

    def test_parse_tiers_descending(self):
        tiers = parse_milestone_tiers('[[10, "Ten"], [50, "Fifty"]]')
        self.assertEqual(tiers[0][0], 50)


if __name__ == "__main__":
    unittest.main()
