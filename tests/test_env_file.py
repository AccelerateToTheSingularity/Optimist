"""Tests for .env load/save helpers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from env_file import load_env_file, load_local_env, save_env_file


class TestEnvFile(unittest.TestCase):
    def test_roundtrip_quoted_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            save_env_file(path, {"BOT_SAFE_MODE": "true", "BOT_SUBREDDIT": "accelerate"})
            loaded = load_env_file(path)
            self.assertEqual(loaded["BOT_SAFE_MODE"], "true")
            self.assertEqual(loaded["BOT_SUBREDDIT"], "accelerate")

    def test_load_local_env_does_not_override_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("BOT_LLM_PROVIDER=openai\n", encoding="utf-8")
            import os

            with patch.dict(os.environ, {"BOT_LLM_PROVIDER": "gemini"}, clear=False):
                load_local_env(path)
                self.assertEqual(os.environ["BOT_LLM_PROVIDER"], "gemini")


if __name__ == "__main__":
    unittest.main()
