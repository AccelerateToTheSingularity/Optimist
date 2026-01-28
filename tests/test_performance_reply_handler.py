
import unittest
from unittest.mock import MagicMock
import sys
from datetime import datetime

# Mock config to avoid import errors
sys.modules['config'] = MagicMock()
sys.modules['config'].SUBREDDIT = 'test_subreddit'
sys.modules['config'].MAX_REPLIES_PER_RUN = 10
sys.modules['config'].MAX_AGE_HOURS = 24
sys.modules['config'].HOSTILE_PATTERNS = []
sys.modules['config'].BOT_INDICATORS = []
sys.modules['config'].SAME_USER_COOLDOWN_HOURS = 1
sys.modules['config'].SAME_USER_REPLIES_BEFORE_COOLDOWN = 3
sys.modules['config'].MOD_CACHE_REFRESH_DAYS = 1
sys.modules['config'].ACCELERATION_ENABLED = False

# Mock persona and acceleration_handler
sys.modules['persona'] = MagicMock()
sys.modules['persona'].generate_conversational_response.return_value = ("Response", {"total_tokens": 10, "cost": 0.0})
sys.modules['acceleration_handler'] = MagicMock()

from reply_handler import check_inbox_replies

class TestReplyHandlerPerformance(unittest.TestCase):
    def test_no_parent_calls(self):
        # Setup mocks
        reddit = MagicMock()
        gemini_model = MagicMock()
        state = {}
        bot_username = "OptimistPrimeBot"

        # Create a list of mock items
        num_items = 5
        items = []
        for i in range(num_items):
            item = MagicMock()
            item.id = f"item_{i}"
            item.created_utc = datetime.utcnow().timestamp()
            item.subreddit.display_name = "test_subreddit"
            item.body = "Hello bot"
            item.author.name = f"user_{i}"

            # This is the crucial part: mocking parent()
            parent = MagicMock()
            parent.author.name = bot_username
            item.parent.return_value = parent
            item.parent_id = f"t1_parent_{i}" # Standard PRAW attribute

            items.append(item)

        reddit.inbox.comment_replies.return_value = items

        # Run the function
        replies_sent, _, _, _ = check_inbox_replies(
            reddit, gemini_model, state, bot_username, dry_run=True
        )

        # Verify calls
        total_parent_calls = sum(item.parent.call_count for item in items)
        print(f"Total items: {num_items}")
        print(f"Total parent() calls: {total_parent_calls}")

        self.assertEqual(total_parent_calls, 0, "Should NOT call parent() for items, as it triggers API calls")

if __name__ == '__main__':
    unittest.main()
