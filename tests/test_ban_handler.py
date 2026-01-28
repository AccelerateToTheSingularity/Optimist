
import unittest
from unittest.mock import MagicMock, Mock
import sys
import os
from io import StringIO
from datetime import datetime

# Add parent directory to path to import ban_handler
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ban_handler import check_and_ban_negative_karma_users

class TestBanHandler(unittest.TestCase):
    def test_performance_optimization(self):
        """Verify that ban list is fetched only once."""
        subreddit = MagicMock()

        # Mock mod log to return 3 users to ban
        log_entries = []
        users_to_ban_names = ["user1", "user2", "user3"]

        for name in users_to_ban_names:
            log = Mock()
            log.action = "removelink"
            log.details = "User has negative local reputation"
            log.target_author = name
            log.created_utc = datetime.utcnow().timestamp()
            log_entries.append(log)

        subreddit.mod.log.return_value = log_entries

        # Mock subreddit.banned
        user1 = Mock()
        user1.name = "banned_user_1"
        user2 = Mock()
        user2.name = "banned_user_2"
        banned_users_list = [user1, user2]

        banned_mock = MagicMock()
        banned_mock.side_effect = lambda limit=None: iter(banned_users_list)
        subreddit.banned = banned_mock

        state = {"banned_users": [], "stats": {}}

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            check_and_ban_negative_karma_users(subreddit, state, dry_run=False)
        finally:
            sys.stdout = sys.__stdout__

        # Assert that subreddit.banned is called once total (optimized)
        self.assertEqual(banned_mock.call_count, 1)

    def test_skips_already_banned_users(self):
        """Verify that users already in the ban list are skipped."""
        subreddit = MagicMock()

        # Log has 2 users: user1 (already banned), user2 (new)
        log1 = Mock()
        log1.action = "removelink"
        log1.details = "User has negative local reputation"
        log1.target_author = "user1"
        log1.created_utc = datetime.utcnow().timestamp()

        log2 = Mock()
        log2.action = "removelink"
        log2.details = "User has negative local reputation"
        log2.target_author = "user2"
        log2.created_utc = datetime.utcnow().timestamp()

        subreddit.mod.log.return_value = [log1, log2]

        # Mock banned list containing user1
        user1 = Mock()
        user1.name = "User1" # Case insensitivity check

        banned_mock = MagicMock()
        banned_mock.side_effect = lambda limit=None: iter([user1])
        subreddit.banned = banned_mock

        state = {"banned_users": [], "stats": {}}

        # Run
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            users_banned, new_state = check_and_ban_negative_karma_users(subreddit, state, dry_run=False)
        finally:
            sys.stdout = sys.__stdout__

        # Verify call to subreddit.banned.add
        banned_calls = banned_mock.add.call_args_list
        # We expect 1 call (for user2)
        self.assertEqual(len(banned_calls), 1)
        args, _ = banned_calls[0]
        self.assertEqual(args[0], "user2")

        # Output should mention skipping user1
        output = captured_output.getvalue()
        self.assertIn("u/user1 already banned, skipping", output)
        self.assertIn("Banned u/user2", output)

if __name__ == "__main__":
    unittest.main()
