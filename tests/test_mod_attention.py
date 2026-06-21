"""Tests for mod_attention.py."""
import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_attention import (
    build_violation_modmail_body,
    build_removal_modmail_body,
    build_removal_public_reply,
    build_troll_modmail_body,
    build_audit_message,
)


class TestModmailBodyBuilders(unittest.TestCase):
    def test_violation_modmail_body(self):
        body = build_violation_modmail_body(
            "testuser", True, "Spam detected", "AI review summary", "https://reddit.com/r/test/123"
        )
        self.assertIn("Moderation Alert", body)
        self.assertIn("testuser", body)
        self.assertIn("Spam detected", body)
        self.assertIn("AI review summary", body)
    
    def test_removal_modmail_body(self):
        body = build_removal_modmail_body(
            "testuser", False, "Rule violation", None, "https://reddit.com/r/test/123"
        )
        self.assertIn("Content Removed", body)
        self.assertIn("testuser", body)
        self.assertIn("Rule violation", body)
    
    def test_removal_public_reply(self):
        body = build_removal_public_reply(True, "Spam", "Details here")
        self.assertIn("post was removed", body)
        self.assertIn("Spam", body)
        self.assertIn("Details here", body)
    
    def test_troll_modmail_body(self):
        metrics = {"username": "troll123", "subreddit": "test", "average_score": -50.5, "comment_count": 15}
        body = build_troll_modmail_body(metrics, "This user is trolling")
        self.assertIn("troll123", body)
        self.assertIn("-50.50", body)
        self.assertIn("This user is trolling", body)
    
    def test_audit_message(self):
        msg = build_audit_message("ban", "Spam", "AI summary", extra="Action: ban")
        self.assertIn("Action: ban", msg)
        self.assertIn("Spam", msg)
        self.assertIn("AI summary", msg)


if __name__ == "__main__":
    unittest.main()
