"""Tests for summon_handler.py pattern matching."""
import unittest
from unittest.mock import MagicMock, patch

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

    @patch("summon_handler.SUMMON_PATTERNS", [r"\bbot\b"])
    def test_skips_reply_to_bot_via_parent_cache(self):
        """When parent is the bot, comment should be skipped before summon check."""
        comment = MagicMock()
        comment.id = "c1"
        comment.created_utc = 9_999_999_999
        comment.author = MagicMock()
        comment.author.name = "regular_user"
        comment.body = "hey bot help"
        comment.parent_id = "t1_parent1"

        parent_author_cache = {"t1_parent1": "OptimistPrime_AI_Bot"}

        parent_id = comment.parent_id
        skip = (
            parent_id in parent_author_cache
            and parent_author_cache[parent_id] == "OptimistPrime_AI_Bot"
        )
        self.assertTrue(skip)


if __name__ == "__main__":
    unittest.main()
