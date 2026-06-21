"""Tests for troll alert logic (no Reddit API)."""

import unittest
from unittest.mock import MagicMock, patch

import config
from troll_alerts import maybe_evaluate_troll_alert


class TestTrollAlerts(unittest.TestCase):
    @patch("troll_alerts.fetch_user_local_history")
    def test_skips_when_average_above_threshold(self, mock_history):
        mock_history.return_value = {
            "comments": [{"body": "ok", "score": 5}] * 12,
            "posts_count": 0,
        }
        state = {}
        with patch.object(config, "TROLL_ALERT_ENABLED", True):
            result = maybe_evaluate_troll_alert(
                MagicMock(), MagicMock(), "user1", state, dry_run=True,
            )
        self.assertFalse(result)

    @patch("troll_alerts.fetch_user_local_history")
    def test_triggers_when_average_low(self, mock_history):
        mock_history.return_value = {
            "comments": [{"body": "bad", "score": -50}] * 12,
            "posts_count": 0,
        }
        state = {}
        with patch.object(config, "TROLL_ALERT_ENABLED", True):
            result = maybe_evaluate_troll_alert(
                MagicMock(), MagicMock(), "user2", state, dry_run=True,
            )
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
