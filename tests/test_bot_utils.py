"""Tests for action idempotency helpers."""

import unittest

from bot_utils import claim_action, has_action_claim, is_bot_owned_author, is_likely_bot


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


class TestBotOwnedAuthor(unittest.TestCase):
    def test_runtime_identity_is_owned(self):
        self.assertTrue(is_bot_owned_author("random87643", "random87643"))

    def test_legacy_aliases_are_owned(self):
        self.assertTrue(is_bot_owned_author("OptimistPrime_AI_Bot", "different-runtime-name"))
        self.assertTrue(is_bot_owned_author("AI-MOD-SUITE-BOT", "different-runtime-name"))

    def test_runtime_identity_is_case_insensitive(self):
        self.assertTrue(is_bot_owned_author("Future-App-Name", "future-app-name"))

    def test_regular_user_is_not_owned(self):
        self.assertFalse(is_bot_owned_author("ordinary-user", "random87643"))

    def test_migrated_name_is_likely_a_bot(self):
        self.assertTrue(is_likely_bot("random87643"))

    def test_runtime_identity_is_likely_a_bot(self):
        self.assertTrue(is_likely_bot("future-runtime-name", "future-runtime-name"))
        self.assertFalse(is_likely_bot("ordinary-user", "future-runtime-name"))

    def test_simulated_automated_reply_chain_stops_immediately(self):
        processed = 0
        for _ in range(20):
            if is_likely_bot("random87643", "future-runtime-name"):
                break
            processed += 1
        self.assertEqual(processed, 0)


if __name__ == "__main__":
    unittest.main()
