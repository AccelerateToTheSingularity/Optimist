"""Tests for persona.py."""
import unittest
from unittest.mock import MagicMock

from persona import get_reply_prompt, build_full_context


class TestGetReplyPrompt(unittest.TestCase):
    def test_includes_context(self):
        prompt = get_reply_prompt("test message", "test context")
        self.assertIn("test context", prompt)
        self.assertIn("test message", prompt)

    def test_includes_persona(self):
        prompt = get_reply_prompt("test", "context")
        self.assertIn("Optimist Prime", prompt)

    def test_summon_note(self):
        prompt = get_reply_prompt("test", "context", is_summon=True)
        self.assertIn("SPECIAL NOTE", prompt)

    def test_no_summon_note(self):
        prompt = get_reply_prompt("test", "context", is_summon=False)
        self.assertNotIn("SPECIAL NOTE", prompt)


class TestBuildFullContext(unittest.TestCase):
    def test_includes_title(self):
        submission = MagicMock()
        submission.title = "Test Post Title"
        submission.selftext = "Test body"

        comment = MagicMock()
        comment.parent.return_value = MagicMock()
        comment.parent.return_value.body = None
        comment.parent.return_value.author = None

        context = build_full_context(comment, submission)
        self.assertIn("Test Post Title", context)
        self.assertIn("Test body", context)


if __name__ == "__main__":
    unittest.main()
