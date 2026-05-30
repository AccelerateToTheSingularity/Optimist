"""
OpenAI-compatible LLM client with a Gemini-shaped generate_content API.

Used for MiniMax (and other OpenAI-compatible providers) without rewriting every caller.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_MODEL = "MiniMax-M2.7"


@dataclass
class UsageMetadata:
    prompt_token_count: int
    candidates_token_count: int


@dataclass
class GenerateContentResponse:
    text: str
    usage_metadata: UsageMetadata


def resolve_api_key() -> str | None:
    """Return the first configured LLM API key from the environment."""
    for name in ("OPENAI_API_KEY", "LLM_API_KEY", "GEMINI_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _prompt_from_contents(contents: str | list[Any]) -> str:
    if isinstance(contents, str):
        return contents

    parts: list[str] = []
    for item in contents:
        if isinstance(item, dict):
            for part in item.get("parts", []):
                parts.append(str(part))
        else:
            parts.append(str(item))
    return "\n\n".join(parts)


class LLMQuotaExhausted(Exception):
    """Raised when a per-run LLM call budget is exhausted."""


class LLMModel:
    """Thin wrapper: callers use generate_content like the old Gemini SDK."""

    def __init__(self, client: OpenAI, model: str):
        self._client = client
        self._model = model

    def generate_content(
        self,
        contents: str | list[Any],
        generation_config: dict[str, Any] | None = None,
    ) -> GenerateContentResponse:
        generation_config = generation_config or {}
        prompt = _prompt_from_contents(contents)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=generation_config.get("temperature", 0.3),
            max_tokens=generation_config.get("max_output_tokens", 1024),
        )

        choice = response.choices[0].message
        text = (choice.content or "").strip()

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return GenerateContentResponse(
            text=text,
            usage_metadata=UsageMetadata(
                prompt_token_count=input_tokens,
                candidates_token_count=output_tokens,
            ),
        )


class RateLimitedLLMModel:
    """Wraps an LLMModel with a hard per-run call cap."""

    def __init__(self, inner: LLMModel, max_calls: int):
        self._inner = inner
        self._max_calls = max_calls
        self.calls_used = 0

    def generate_content(
        self,
        contents: str | list[Any],
        generation_config: dict[str, Any] | None = None,
    ) -> GenerateContentResponse:
        if self.calls_used >= self._max_calls:
            raise LLMQuotaExhausted(
                f"Per-run LLM limit reached ({self._max_calls} call(s))"
            )
        self.calls_used += 1
        return self._inner.generate_content(contents, generation_config)


def wrap_with_rate_limit(model: LLMModel, max_calls: int | None) -> LLMModel | RateLimitedLLMModel:
    if max_calls is None or max_calls <= 0:
        return model
    return RateLimitedLLMModel(model, max_calls)


def create_llm_model() -> LLMModel:
    """Build the configured LLM client from environment variables."""
    api_key = resolve_api_key()
    if not api_key:
        raise ValueError(
            "Missing LLM API key. Set OPENAI_API_KEY (recommended), LLM_API_KEY, or GEMINI_API_KEY."
        )

    base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or DEFAULT_BASE_URL
    ).strip()
    model = (os.environ.get("LLM_MODEL") or DEFAULT_MODEL).strip()

    client = OpenAI(api_key=api_key, base_url=base_url)
    return LLMModel(client, model)
