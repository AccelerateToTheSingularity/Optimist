"""Tests for bot_runner.find_bot_comment owned-alias matching."""

import unittest
from unittest.mock import MagicMock

from bot_runner import find_bot_comment


def _submission_with_comments(comments):
    submission = MagicMock()
    comment_forest = MagicMock()
    comment_forest.replace_more = MagicMock()
    comment_forest.__iter__ = lambda self: iter(comments)
    submission.comments = comment_forest
    return submission


class TestFindBotComment(unittest.TestCase):
    def test_finds_distinguished_comment_from_migrated_alias(self):
        legacy = MagicMock()
        legacy.author = MagicMock()
        legacy.author.name = "OptimistPrime_AI_Bot"
        legacy.distinguished = True

        other = MagicMock()
        other.author = MagicMock()
        other.author.name = "ordinary-user"
        other.distinguished = True

        found = find_bot_comment(
            _submission_with_comments([other, legacy]),
            "future-runtime-name",
        )
        self.assertIs(found, legacy)

    def test_ignores_undistinguished_owned_comment(self):
        owned = MagicMock()
        owned.author = MagicMock()
        owned.author.name = "random87643"
        owned.distinguished = False

        self.assertIsNone(
            find_bot_comment(
                _submission_with_comments([owned]),
                "future-runtime-name",
            )
        )


if __name__ == "__main__":
    unittest.main()
