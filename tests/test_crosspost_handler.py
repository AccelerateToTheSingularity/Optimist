"""Tests for crosspost_handler.py."""
import unittest
from unittest.mock import MagicMock
from datetime import date

from crosspost_handler import (
    is_already_crossposted,
    get_todays_schedule,
)


class TestIsAlreadyCrossposted(unittest.TestCase):
    def test_detects_crosspost_by_url(self):
        submission = MagicMock()
        submission.id = "abc123"
        submission.permalink = "/r/accelerate/comments/abc123/test/"
        submission.url = "https://example.com/article"

        existing_urls = {"https://example.com/article"}
        history = []

        self.assertTrue(is_already_crossposted(submission, existing_urls, history))

    def test_detects_crosspost_by_history(self):
        submission = MagicMock()
        submission.id = "abc123"
        submission.permalink = "/r/accelerate/comments/abc123/test/"
        submission.url = "https://example.com/article"

        existing_urls = set()
        history = [{"source_post_id": "abc123"}]

        self.assertTrue(is_already_crossposted(submission, existing_urls, history))

    def test_not_crossposted(self):
        submission = MagicMock()
        submission.id = "abc123"
        submission.permalink = "/r/accelerate/comments/abc123/test/"
        submission.url = "https://example.com/article"

        existing_urls = set()
        history = []

        self.assertFalse(is_already_crossposted(submission, existing_urls, history))


class TestGetTodaysSchedule(unittest.TestCase):
    def test_new_day_sets_schedule(self):
        state = {"crosspost": {}}
        scheduled_hour, should_skip = get_todays_schedule(state)

        self.assertIsNotNone(state["crosspost"].get("scheduled_date"))
        self.assertFalse(should_skip)

    def test_returns_cached_schedule(self):
        today = date.today().isoformat()
        state = {
            "crosspost": {
                "scheduled_date": today,
                "scheduled_hour": 3,
                "skip_today": False,
            }
        }
        scheduled_hour, should_skip = get_todays_schedule(state)

        self.assertEqual(scheduled_hour, 3)
        self.assertFalse(should_skip)


if __name__ == "__main__":
    unittest.main()
