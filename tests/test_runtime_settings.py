import os
import unittest
from unittest.mock import patch

import config
from runtime_settings import apply_runtime_settings, resolve_runtime_settings

_ORIGINAL_SUMMON_PATTERNS = list(config.SUMMON_PATTERNS)


class TestRuntimeSettings(unittest.TestCase):
    def tearDown(self):
        config.SUBREDDIT = "accelerate"
        config.CROSSPOST_ENABLED = True
        config.ACCELERATION_ENABLED = True
        config.SUMMON_PATTERNS = list(_ORIGINAL_SUMMON_PATTERNS)

    def test_proai_limited_profile(self):
        with patch.dict(os.environ, {"BOT_PROFILE": "proai_limited"}, clear=False):
            settings = resolve_runtime_settings(bot_username="random")
        self.assertEqual(settings.subreddit, "ProAI")
        self.assertFalse(settings.crosspost_enabled)
        self.assertFalse(settings.acceleration_enabled)
        self.assertFalse(settings.ban_phase_enabled)
        self.assertFalse(settings.inbox_replies_enabled)
        self.assertEqual(settings.max_llm_calls_per_run, 1)
        self.assertIn(r"\bu/random\b", settings.extra_summon_patterns)

    def test_empty_bot_subreddit_env_uses_preset(self):
        with patch.dict(
            os.environ,
            {"BOT_PROFILE": "proai_limited", "BOT_SUBREDDIT": ""},
            clear=False,
        ):
            settings = resolve_runtime_settings()
        self.assertEqual(settings.subreddit, "ProAI")

    def test_apply_updates_config_module(self):
        with patch.dict(os.environ, {"BOT_PROFILE": "proai_limited"}, clear=False):
            settings = resolve_runtime_settings(bot_username="random")
            apply_runtime_settings(settings)
        self.assertEqual(config.SUBREDDIT, "ProAI")
        self.assertFalse(config.CROSSPOST_ENABLED)


if __name__ == "__main__":
    unittest.main()
