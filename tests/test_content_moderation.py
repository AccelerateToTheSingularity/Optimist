"""Tests for content_moderation.py parsing logic."""

import unittest
from unittest.mock import MagicMock

from llm_client import LLMQuotaExhausted
from content_moderation import (
    IMPLEMENTED_ACTIONS,
    evaluate_content_violation,
    evaluate_rules,
    handle_moderation_action,
    _rule_eval_max_output_tokens,
)
from moderation_rules import ModerationRule


class MockLLMModel:
    """Mock LLM model for testing."""
    def __init__(self, response_text: str):
        self._response_text = response_text

    def generate_content(self, contents, generation_config=None):
        class MockResponse:
            def __init__(self, text):
                self.text = text
        return MockResponse(self._response_text)


class TestContentModeration(unittest.TestCase):
    def test_violation_detected(self):
        mock = MockLLMModel("VIOLATES: YES\nREASON: Contains spam")
        result = evaluate_content_violation("test content", "No spam allowed", mock)
        self.assertTrue(result["violates"])
        self.assertEqual(result["reason"], "Contains spam")

    def test_no_violation(self):
        mock = MockLLMModel("VIOLATES: NO")
        result = evaluate_content_violation("test content", "No spam allowed", mock)
        self.assertFalse(result["violates"])
        self.assertEqual(result["reason"], "")

    def test_malformed_response_no_violates(self):
        mock = MockLLMModel("Some random response")
        result = evaluate_content_violation("test content", "No spam allowed", mock)
        self.assertFalse(result["violates"])

    def test_llm_error_returns_none(self):
        class FailingModel:
            def generate_content(self, contents, generation_config=None):
                raise Exception("API error")
        result = evaluate_content_violation("test content", "rules", FailingModel())
        self.assertIsNone(result)

    def test_no_violation_does_not_extract_reason(self):
        mock = MockLLMModel("VIOLATES: NO\nREASON: should not appear")
        result = evaluate_content_violation("test content", "rules", mock)
        self.assertFalse(result["violates"])
        self.assertEqual(result["reason"], "")

    def test_quota_exhausted_propagates(self):
        class QuotaModel:
            def generate_content(self, contents, generation_config=None):
                raise LLMQuotaExhausted("limit reached")
        with self.assertRaises(LLMQuotaExhausted):
            evaluate_content_violation("test", "rules", QuotaModel())


class TestModerationActions(unittest.TestCase):
    def test_unsupported_action_returns_false(self):
        subreddit = MagicMock()
        content = MagicMock()
        content.permalink = "/r/test/1"
        result = handle_moderation_action(
            subreddit, content, "user", "reason", "notify_discord", dry_run=False,
        )
        self.assertFalse(result)

    def test_supported_actions_set(self):
        self.assertIn("report", IMPLEMENTED_ACTIONS)
        self.assertNotIn("notify_discord", IMPLEMENTED_ACTIONS)


class TestRuleEvalTokens(unittest.TestCase):
    def test_scales_with_rule_count(self):
        self.assertEqual(_rule_eval_max_output_tokens(10), 500)
        self.assertEqual(_rule_eval_max_output_tokens(21), 840)

    def test_quota_exhausted_propagates_from_evaluate_rules(self):
        class QuotaModel:
            def generate_content(self, contents, generation_config=None):
                raise LLMQuotaExhausted("limit reached")
        rules = [ModerationRule(name="spam_detector", description="spam?")]
        with self.assertRaises(LLMQuotaExhausted):
            evaluate_rules("content", rules, QuotaModel())


if __name__ == "__main__":
    unittest.main()
