import os
import unittest
from unittest.mock import MagicMock, patch

from llm_client import (
    LLMModel,
    _prompt_from_contents,
    create_llm_model,
    resolve_api_key,
)


class TestLLMClient(unittest.TestCase):
    def test_prompt_from_string(self):
        self.assertEqual(_prompt_from_contents("hello"), "hello")

    def test_prompt_from_gemini_style_parts(self):
        contents = [{"role": "user", "parts": ["part one", "part two"]}]
        self.assertEqual(_prompt_from_contents(contents), "part one\n\npart two")

    def test_resolve_api_key_prefers_openai(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "GEMINI_API_KEY": "gemini-key",
            },
            clear=False,
        ):
            self.assertEqual(resolve_api_key(), "openai-key")

    def test_generate_content_maps_openai_response(self):
        mock_client = MagicMock()
        mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_choice = MagicMock()
        mock_choice.message.content = "  summary text  "
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_client.chat.completions.create.return_value = mock_response

        model = LLMModel(mock_client, "MiniMax-M2.7")
        response = model.generate_content(
            [{"role": "user", "parts": ["Summarize this"]}],
            generation_config={"temperature": 0.3, "max_output_tokens": 100},
        )

        self.assertEqual(response.text, "summary text")
        self.assertEqual(response.usage_metadata.prompt_token_count, 10)
        self.assertEqual(response.usage_metadata.candidates_token_count, 5)
        mock_client.chat.completions.create.assert_called_once_with(
            model="MiniMax-M2.7",
            messages=[{"role": "user", "content": "Summarize this"}],
            temperature=0.3,
            max_tokens=100,
        )

    @patch("llm_client.OpenAI")
    def test_create_llm_model_uses_env(self, mock_openai):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "https://api.minimax.io/v1",
                "LLM_MODEL": "MiniMax-M2.7",
            },
            clear=False,
        ):
            create_llm_model()
        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )


if __name__ == "__main__":
    unittest.main()
