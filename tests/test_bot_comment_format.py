"""Tests for bot_comment_format.py."""

import unittest

from bot_comment_format import (
    format_bot_comment,
    BOT_COMMENT_FOOTER,
    CURRENT_FOOTER_REGEX,
    strip_bot_footer,
)


class TestBotCommentFormat(unittest.TestCase):
    def test_appends_footer_to_plain_text(self):
        result = format_bot_comment("Hello world")
        self.assertTrue(result.startswith("Hello world"))
        self.assertTrue(result.endswith(BOT_COMMENT_FOOTER))

    def test_idempotent_does_not_duplicate_footer(self):
        first = format_bot_comment("Test comment")
        second = format_bot_comment(first)
        self.assertEqual(first, second)

    def test_replaces_old_footer_format(self):
        # Old footer format is different text - regex won't match it, so old footer stays
        # and new footer is appended. This is acceptable for migration.
        old_text = "Some text\n\n---\n**AI assistant - mention the bot**"
        result = format_bot_comment(old_text)
        self.assertIn(BOT_COMMENT_FOOTER, result)

    def test_handles_empty_body(self):
        result = format_bot_comment("")
        self.assertTrue(result.endswith(BOT_COMMENT_FOOTER))

    def test_handles_body_with_trailing_whitespace(self):
        result = format_bot_comment("Text  \n\n")
        self.assertTrue(result.startswith("Text"))
        self.assertTrue(result.endswith(BOT_COMMENT_FOOTER))

    def test_footer_regex_matches_standard_footer(self):
        text = f"Some text\n\n---\n{BOT_COMMENT_FOOTER}"
        match = CURRENT_FOOTER_REGEX.search(text)
        self.assertIsNotNone(match)

    def test_footer_regex_matches_bold_footer(self):
        text = f"Some text\n\n---\n**{BOT_COMMENT_FOOTER}**"
        match = CURRENT_FOOTER_REGEX.search(text)
        self.assertIsNotNone(match)

    def test_new_footer_does_not_contain_summon_phrase(self):
        result = format_bot_comment("Helpful answer")
        self.assertNotIn("!bot", result)
        self.assertNotIn("mod bot", result.lower())

    def test_legacy_footer_is_replaced(self):
        result = format_bot_comment(
            "Helpful answer\n\n---\n*^(AI assistant · mention the bot, mod bot, or use !bot)*"
        )
        self.assertEqual(result.count("AI assistant"), 1)
        self.assertNotIn("!bot", result)

    def test_strip_bot_footer_removes_legacy_and_current_footers(self):
        legacy = "Reply\n\n---\n*^(AI assistant · mention the bot, mod bot, or use !bot)*"
        current = f"Reply\n\n---\n{BOT_COMMENT_FOOTER}"
        self.assertEqual(strip_bot_footer(legacy), "Reply")
        self.assertEqual(strip_bot_footer(current), "Reply")


if __name__ == "__main__":
    unittest.main()
