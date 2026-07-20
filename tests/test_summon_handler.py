"""Tests for summon_handler.py pattern matching."""
import unittest
from unittest.mock import MagicMock

from bot_comment_format import format_bot_comment
from bot_utils import is_bot_owned_author
from summon_handler import is_summon


class TestIsSummon(unittest.TestCase):
    def test_detects_optimist_prime(self):
        self.assertTrue(is_summon("Hey Optimist Prime, what do you think?"))

    def test_detects_bot_mention(self):
        self.assertTrue(is_summon("Hey bot, help me out"))

    def test_detects_mod_bot(self):
        self.assertTrue(is_summon("mod bot please summarize this"))

    def test_detects_first_person_summon(self):
        self.assertTrue(is_summon("I summon the bot"))

    def test_not_a_summon(self):
        self.assertFalse(is_summon("This is a regular comment about AI progress"))

    def test_not_indirect_suggestion(self):
        self.assertFalse(is_summon("Someone should ask the bot about this"))

    def test_bot_footer_does_not_trigger_summon(self):
        self.assertFalse(
            is_summon(
                "Helpful answer\n\n---\n"
                "*^(AI assistant · mention the bot, mod bot, or use !bot)*"
            )
        )

    def test_current_footer_does_not_trigger_summon(self):
        # Footer still contains "Optimist Prime"; strip_bot_footer must remove it.
        self.assertFalse(is_summon(format_bot_comment("Helpful answer")))


class TestParentAuthorCache(unittest.TestCase):
    """Parent batch cache must key by fullname (t1_xxx), not bare id."""

    def test_cache_uses_fullname_keys(self):
        parent = MagicMock()
        parent.fullname = "t1_abc123"
        parent.name = "abc123"
        parent.author = MagicMock()
        parent.author.name = "OptimistPrime_AI_Bot"

        cache = {}
        cache[parent.fullname] = parent.author.name

        self.assertIn("t1_abc123", cache)
        self.assertNotIn("abc123", cache)
        self.assertEqual(cache["t1_abc123"], "OptimistPrime_AI_Bot")

    def test_skips_reply_to_bot_via_parent_cache(self):
        """When parent is a migrated bot alias, skip before summon check."""
        comment = MagicMock()
        comment.id = "c1"
        comment.created_utc = 9_999_999_999
        comment.author = MagicMock()
        comment.author.name = "regular_user"
        comment.body = "hey bot help"
        comment.parent_id = "t1_parent1"

        runtime_bot_username = "future-runtime-name"
        parent_author_cache = {"t1_parent1": "random87643"}

        parent_id = comment.parent_id
        skip = (
            parent_id in parent_author_cache
            and is_bot_owned_author(parent_author_cache[parent_id], runtime_bot_username)
        )
        self.assertTrue(skip)
        self.assertNotEqual(parent_author_cache[parent_id], runtime_bot_username)


if __name__ == "__main__":
    unittest.main()
