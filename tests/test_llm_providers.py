"""Tests for multi-provider LLM configuration."""

import os
import unittest
from unittest.mock import patch

from llm_client import PROVIDER_PRESETS, create_llm_model, resolve_llm_config


class TestLLMProviders(unittest.TestCase):
    def test_all_presets_defined(self):
        for name in (
            "minimax", "openai", "claude", "gemini", "deepseek", "glm",
            "groq", "mistral", "together", "xai", "custom",
        ):
            self.assertIn(name, PROVIDER_PRESETS)

    def test_resolve_claude_preset(self):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "ant-test"},
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.provider, "claude")
        self.assertIn("anthropic.com", cfg.base_url)

    def test_resolve_glm_preset(self):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "glm", "GLM_API_KEY": "glm-test"},
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.provider, "glm")
        self.assertIn("bigmodel.cn", cfg.base_url)
        self.assertEqual(cfg.model, "glm-4-flash")

    def test_resolve_groq_preset(self):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "groq", "GROQ_API_KEY": "gsk-test"},
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.provider, "groq")
        self.assertIn("groq.com", cfg.base_url)

    def test_resolve_openai_preset(self):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"},
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.base_url, "https://api.openai.com/v1")
        self.assertEqual(cfg.model, "gpt-4o-mini")

    def test_resolve_deepseek_preset(self):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "ds-test"},
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.provider, "deepseek")
        self.assertIn("deepseek.com", cfg.base_url)
        self.assertEqual(cfg.model, "deepseek-chat")

    def test_env_overrides_model_and_base_url(self):
        with patch.dict(
            os.environ,
            {
                "BOT_LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "sk-test",
                "LLM_MODEL": "gpt-4o",
                "OPENAI_BASE_URL": "https://custom.example/v1",
            },
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.model, "gpt-4o")
        self.assertEqual(cfg.base_url, "https://custom.example/v1")

    def test_unknown_provider_falls_back_to_minimax(self):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "not-a-real-provider", "LLM_API_KEY": "key"},
            clear=False,
        ):
            cfg = resolve_llm_config()
        self.assertEqual(cfg.provider, "minimax")

    @patch("llm_client.OpenAI")
    def test_create_llm_model_uses_provider(self, mock_openai):
        with patch.dict(
            os.environ,
            {"BOT_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "g-key"},
            clear=False,
        ):
            create_llm_model()
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["api_key"], "g-key")
        self.assertIn("generativelanguage.googleapis.com", call_kwargs["base_url"])


if __name__ == "__main__":
    unittest.main()
