"""Tests for action idempotency helpers."""

import unittest

from bot_utils import claim_action, has_action_claim


class TestClaimAction(unittest.TestCase):
    def test_first_claim_succeeds(self):
        state = {}
        self.assertTrue(claim_action(state, "tldr:t3_abc"))
        self.assertIn("tldr:t3_abc", state["action_keys"])

    def test_second_claim_fails(self):
        state = {}
        self.assertTrue(claim_action(state, "mod:t1_x"))
        self.assertFalse(claim_action(state, "mod:t1_x"))
        self.assertTrue(has_action_claim(state, "mod:t1_x"))


if __name__ == "__main__":
    unittest.main()
