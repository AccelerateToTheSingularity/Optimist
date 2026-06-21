"""Tests for the discrete rule-based moderation system."""

import json
import os
import tempfile
import unittest

from moderation_rules import (
    ModerationRule,
    RuleLoadError,
    load_rules,
    filter_rules,
)
from content_moderation import (
    parse_rule_response,
    evaluate_rules,
)


# ---------------------------------------------------------------------------
# ModerationRule dataclass
# ---------------------------------------------------------------------------

class TestModerationRule(unittest.TestCase):
    def test_basic_properties(self):
        rule = ModerationRule(
            name="test_rule",
            description="Is this a test?",
            conditions={"stop_on_match": True, "skip_mods": True, "skip_approved": False},
        )
        self.assertTrue(rule.stop_on_match)
        self.assertTrue(rule.skip_mods)
        self.assertFalse(rule.skip_approved)

    def test_defaults(self):
        rule = ModerationRule(name="r", description="d")
        self.assertTrue(rule.active)
        self.assertEqual(rule.order, 100)
        self.assertEqual(rule.target, "both")
        self.assertEqual(rule.actions, ["report"])
        self.assertFalse(rule.stop_on_match)
        self.assertFalse(rule.skip_mods)
        self.assertFalse(rule.skip_approved)
        self.assertFalse(rule.use_vision)

    def test_applies_to(self):
        rule_both = ModerationRule(name="r", description="d", target="both")
        rule_posts = ModerationRule(name="r", description="d", target="posts")
        rule_comments = ModerationRule(name="r", description="d", target="comments")

        self.assertTrue(rule_both.applies_to("posts"))
        self.assertTrue(rule_both.applies_to("comments"))
        self.assertTrue(rule_posts.applies_to("posts"))
        self.assertFalse(rule_posts.applies_to("comments"))
        self.assertTrue(rule_comments.applies_to("comments"))
        self.assertFalse(rule_comments.applies_to("posts"))


# ---------------------------------------------------------------------------
# Rule loading and validation
# ---------------------------------------------------------------------------

class TestLoadRules(unittest.TestCase):
    def _write_rules(self, rules_list):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(rules_list, f)
        f.close()
        return f.name

    def test_load_valid_rules(self):
        path = self._write_rules([
            {"name": "rule_a", "description": "Is it A?", "order": 20},
            {"name": "rule_b", "description": "Is it B?", "order": 10},
        ])
        try:
            rules = load_rules(path)
            self.assertEqual(len(rules), 2)
            # Should be sorted by order
            self.assertEqual(rules[0].name, "rule_b")
            self.assertEqual(rules[1].name, "rule_a")
        finally:
            os.unlink(path)

    def test_missing_name_raises(self):
        path = self._write_rules([{"description": "No name"}])
        try:
            with self.assertRaises(RuleLoadError):
                load_rules(path)
        finally:
            os.unlink(path)

    def test_missing_description_raises(self):
        path = self._write_rules([{"name": "rule_a"}])
        try:
            with self.assertRaises(RuleLoadError):
                load_rules(path)
        finally:
            os.unlink(path)

    def test_space_in_name_raises(self):
        path = self._write_rules([{"name": "has space", "description": "d"}])
        try:
            with self.assertRaises(RuleLoadError):
                load_rules(path)
        finally:
            os.unlink(path)

    def test_invalid_target_raises(self):
        path = self._write_rules([{"name": "r", "description": "d", "target": "images"}])
        try:
            with self.assertRaises(RuleLoadError):
                load_rules(path)
        finally:
            os.unlink(path)

    def test_invalid_action_raises(self):
        path = self._write_rules([{"name": "r", "description": "d", "actions": ["explode"]}])
        try:
            with self.assertRaises(RuleLoadError):
                load_rules(path)
        finally:
            os.unlink(path)

    def test_non_array_raises(self):
        path = self._write_rules({"name": "r", "description": "d"})
        try:
            with self.assertRaises(RuleLoadError):
                load_rules(path)
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with self.assertRaises(RuleLoadError):
            load_rules("/nonexistent/path/rules.json")

    def test_env_var_override(self):
        rules_json = json.dumps([
            {"name": "env_rule", "description": "From env"}
        ])
        os.environ["BOT_MODERATION_RULES_JSON"] = rules_json
        try:
            rules = load_rules()
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].name, "env_rule")
        finally:
            del os.environ["BOT_MODERATION_RULES_JSON"]

    def test_env_var_invalid_json_raises(self):
        os.environ["BOT_MODERATION_RULES_JSON"] = "not valid json"
        try:
            with self.assertRaises(RuleLoadError):
                load_rules()
        finally:
            del os.environ["BOT_MODERATION_RULES_JSON"]

    def test_inactive_rule_loaded(self):
        path = self._write_rules([
            {"name": "active_rule", "description": "A", "active": True},
            {"name": "inactive_rule", "description": "I", "active": False},
        ])
        try:
            rules = load_rules(path)
            self.assertEqual(len(rules), 2)
            active = [r for r in rules if r.active]
            inactive = [r for r in rules if not r.active]
            self.assertEqual(len(active), 1)
            self.assertEqual(len(inactive), 1)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Rule filtering
# ---------------------------------------------------------------------------

class TestFilterRules(unittest.TestCase):
    def _make_rules(self):
        return [
            ModerationRule(name="post_only", description="d", target="posts", active=True),
            ModerationRule(name="comment_only", description="d", target="comments", active=True),
            ModerationRule(name="both_active", description="d", target="both", active=True),
            ModerationRule(name="both_inactive", description="d", target="both", active=False),
        ]

    def test_filter_posts(self):
        rules = filter_rules(self._make_rules(), "posts")
        names = [r.name for r in rules]
        self.assertIn("post_only", names)
        self.assertIn("both_active", names)
        self.assertNotIn("comment_only", names)
        self.assertNotIn("both_inactive", names)

    def test_filter_comments(self):
        rules = filter_rules(self._make_rules(), "comments")
        names = [r.name for r in rules]
        self.assertIn("comment_only", names)
        self.assertIn("both_active", names)
        self.assertNotIn("post_only", names)

    def test_active_only(self):
        rules = filter_rules(self._make_rules(), "both", active_only=True)
        names = [r.name for r in rules]
        self.assertNotIn("both_inactive", names)

    def test_include_inactive(self):
        rules = filter_rules(self._make_rules(), "both", active_only=False)
        names = [r.name for r in rules]
        self.assertIn("both_inactive", names)

    def test_sorted_by_order(self):
        rules = [
            ModerationRule(name="c", description="d", order=30),
            ModerationRule(name="a", description="d", order=10),
            ModerationRule(name="b", description="d", order=20),
        ]
        filtered = filter_rules(rules, "both")
        self.assertEqual([r.name for r in filtered], ["a", "b", "c"])


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestParseRuleResponse(unittest.TestCase):
    def _rules(self):
        return [
            ModerationRule(name="spam_detector", description="d"),
            ModerationRule(name="toxicity_detector", description="d"),
            ModerationRule(name="off_topic_detector", description="d"),
        ]

    def test_basic_parsing(self):
        response = "spam_detector: YES - obvious spam\noff_topic_detector: NO"
        results = parse_rule_response(response, self._rules())
        self.assertTrue(results["spam_detector"]["matched"])
        self.assertIn("obvious spam", results["spam_detector"]["reason"])
        self.assertFalse(results["toxicity_detector"]["matched"])
        self.assertFalse(results["off_topic_detector"]["matched"])

    def test_all_yes(self):
        response = (
            "spam_detector: YES\n"
            "toxicity_detector: YES\n"
            "off_topic_detector: YES"
        )
        results = parse_rule_response(response, self._rules())
        for rule in self._rules():
            self.assertTrue(results[rule.name]["matched"])

    def test_all_no(self):
        response = (
            "spam_detector: NO\n"
            "toxicity_detector: NO\n"
            "off_topic_detector: NO"
        )
        results = parse_rule_response(response, self._rules())
        for rule in self._rules():
            self.assertFalse(results[rule.name]["matched"])

    def test_case_insensitive(self):
        response = "SPAM_DETECTOR: Yes - spam"
        results = parse_rule_response(response, self._rules())
        self.assertTrue(results["spam_detector"]["matched"])

    def test_unmentioned_rules_default_no(self):
        response = "spam_detector: YES"
        results = parse_rule_response(response, self._rules())
        self.assertTrue(results["spam_detector"]["matched"])
        self.assertFalse(results["toxicity_detector"]["matched"])
        self.assertFalse(results["off_topic_detector"]["matched"])

    def test_empty_response(self):
        results = parse_rule_response("", self._rules())
        for rule in self._rules():
            self.assertFalse(results[rule.name]["matched"])

    def test_dashes_in_reason(self):
        response = "spam_detector: YES - this is spam - clearly"
        results = parse_rule_response(response, self._rules())
        self.assertTrue(results["spam_detector"]["matched"])
        self.assertIn("this is spam", results["spam_detector"]["reason"])

    def test_normalized_name_matching(self):
        response = "off-topic-detector: YES"
        results = parse_rule_response(response, self._rules())
        self.assertTrue(results["off_topic_detector"]["matched"])


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestGetRuleEvaluationPrompt(unittest.TestCase):
    """Tests for prompt construction.

    Note: We test the prompt indirectly through evaluate_rules() because
    other test files mock sys.modules['prompts'] at import time, which
    persists across the test session.
    """

    def test_prompt_reaches_llm_with_rules(self):
        """Verify the prompt sent to the LLM contains rule names and content."""
        captured_prompts = []

        class CapturingModel:
            def generate_content(self, contents, generation_config=None):
                prompt = contents[0]["parts"][0] if isinstance(contents, list) else str(contents)
                captured_prompts.append(prompt)

                class R:
                    text = "rule_a: NO\nrule_b: NO"
                    usage_metadata = type("M", (), {
                        "prompt_token_count": 50,
                        "candidates_token_count": 20,
                    })()
                return R()

        rules = [
            ModerationRule(name="rule_a", description="Is it A?"),
            ModerationRule(name="rule_b", description="Is it B?"),
        ]
        evaluate_rules("test content here", rules, CapturingModel())

        self.assertEqual(len(captured_prompts), 1)
        prompt = captured_prompts[0]
        self.assertIn("rule_a: Is it A?", prompt)
        self.assertIn("rule_b: Is it B?", prompt)
        self.assertIn("test content here", prompt)

    def test_prompt_has_structured_format(self):
        """Verify the prompt requests structured YES/NO output."""
        captured_prompts = []

        class CapturingModel:
            def generate_content(self, contents, generation_config=None):
                prompt = contents[0]["parts"][0] if isinstance(contents, list) else str(contents)
                captured_prompts.append(prompt)

                class R:
                    text = "r: NO"
                    usage_metadata = type("M", (), {
                        "prompt_token_count": 50,
                        "candidates_token_count": 20,
                    })()
                return R()

        rules = [ModerationRule(name="r", description="d")]
        evaluate_rules("content", rules, CapturingModel())

        prompt = captured_prompts[0]
        self.assertIn("<rules>", prompt)
        self.assertIn("</rules>", prompt)
        self.assertIn("<user_content>", prompt)
        self.assertIn("</user_content>", prompt)
        self.assertIn("YES", prompt)
        self.assertIn("NO", prompt)


# ---------------------------------------------------------------------------
# Mock-based evaluate_rules test
# ---------------------------------------------------------------------------

class MockLLMModel:
    """Mock LLM that returns a preset response."""
    def __init__(self, response_text: str):
        self._response_text = response_text

    def generate_content(self, contents, generation_config=None):
        class MockResponse:
            def __init__(self, text):
                self.text = text
                self.usage_metadata = type("M", (), {
                    "prompt_token_count": 100,
                    "candidates_token_count": 50,
                })()
        return MockResponse(self._response_text)


class TestEvaluateRules(unittest.TestCase):
    def test_matches_returned(self):
        rules = [
            ModerationRule(name="spam", description="Is it spam?"),
            ModerationRule(name="toxic", description="Is it toxic?"),
        ]
        mock = MockLLMModel("spam: YES - clearly spam\ntoxic: NO")
        result = evaluate_rules("Buy this now!!!", rules, mock)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["rule"].name, "spam")

    def test_no_matches(self):
        rules = [ModerationRule(name="spam", description="Is it spam?")]
        mock = MockLLMModel("spam: NO")
        result = evaluate_rules("Great post!", rules, mock)
        self.assertEqual(len(result["matches"]), 0)

    def test_empty_rules(self):
        mock = MockLLMModel("")
        result = evaluate_rules("content", [], mock)
        self.assertEqual(result["matches"], [])

    def test_llm_error_returns_none(self):
        class FailingModel:
            def generate_content(self, contents, generation_config=None):
                raise Exception("API error")
        rules = [ModerationRule(name="r", description="d")]
        result = evaluate_rules("content", rules, FailingModel())
        self.assertIsNone(result)

    def test_matches_sorted_by_order(self):
        rules = [
            ModerationRule(name="late", description="d", order=30),
            ModerationRule(name="early", description="d", order=10),
        ]
        mock = MockLLMModel("late: YES\nearly: YES")
        result = evaluate_rules("content", rules, mock)
        self.assertEqual(result["matches"][0]["rule"].name, "early")
        self.assertEqual(result["matches"][1]["rule"].name, "late")


if __name__ == "__main__":
    unittest.main()
