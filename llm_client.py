"""
OpenAI-compatible LLM client with a Gemini-shaped generate_content API.

Used for MiniMax, OpenAI, DeepSeek, Gemini (OpenAI-compat), and custom endpoints.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_MODEL = "MiniMax-M2.7"

# Preset providers (BOT_LLM_PROVIDER env). API keys resolved per provider.
# All providers use the OpenAI-compatible chat completions API unless noted.
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "minimax": {
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M2.7",
        "api_key_envs": "OPENAI_API_KEY,LLM_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_envs": "OPENAI_API_KEY,LLM_API_KEY",
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1/",
        "model": "claude-sonnet-4-20250514",
        "api_key_envs": "ANTHROPIC_API_KEY,LLM_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "api_key_envs": "GEMINI_API_KEY,LLM_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_envs": "DEEPSEEK_API_KEY,LLM_API_KEY,OPENAI_API_KEY",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4-flash",
        "api_key_envs": "GLM_API_KEY,ZHIPU_API_KEY,LLM_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "api_key_envs": "GROQ_API_KEY,LLM_API_KEY",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "api_key_envs": "MISTRAL_API_KEY,LLM_API_KEY",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "api_key_envs": "TOGETHER_API_KEY,LLM_API_KEY",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-2-1212",
        "api_key_envs": "XAI_API_KEY,LLM_API_KEY",
    },
    "custom": {
        "base_url": "",
        "model": "",
        "api_key_envs": "LLM_API_KEY,OPENAI_API_KEY,GEMINI_API_KEY,ANTHROPIC_API_KEY",
    },
}


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    provider: str


@dataclass
class UsageMetadata:
    prompt_token_count: int
    candidates_token_count: int


@dataclass
class GenerateContentResponse:
    text: str
    usage_metadata: UsageMetadata


def _first_env_key(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def resolve_api_key(env_list: str | None = None) -> str | None:
    """Return the first configured LLM API key from the environment."""
    if env_list:
        return _first_env_key(*(n.strip() for n in env_list.split(",") if n.strip()))
    return _first_env_key(
        "OPENAI_API_KEY",
        "LLM_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "GLM_API_KEY",
        "ZHIPU_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "XAI_API_KEY",
    )


def resolve_llm_config(provider: str | None = None) -> LLMConfig:
    """
    Resolve provider preset + env overrides into connection settings.

    BOT_LLM_PROVIDER selects preset (minimax, openai, claude, gemini, deepseek, glm,
    groq, mistral, together, xai, custom).
    OPENAI_BASE_URL / LLM_BASE_URL and LLM_MODEL override preset defaults.
    """
    raw_provider = (provider or os.environ.get("BOT_LLM_PROVIDER", "minimax")).strip().lower()
    if raw_provider not in PROVIDER_PRESETS:
        raw_provider = "minimax"

    preset = PROVIDER_PRESETS[raw_provider]
    api_key = resolve_api_key(preset.get("api_key_envs"))
    if not api_key:
        raise ValueError(
            f"Missing API key for LLM provider '{raw_provider}'. "
            f"Set one of: {preset.get('api_key_envs', 'LLM_API_KEY')}."
        )

    base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or preset.get("base_url")
        or DEFAULT_BASE_URL
    ).strip()

    model = (os.environ.get("LLM_MODEL") or preset.get("model") or DEFAULT_MODEL).strip()

    if raw_provider == "custom" and not base_url:
        raise ValueError("BOT_LLM_PROVIDER=custom requires OPENAI_BASE_URL or LLM_BASE_URL.")

    return LLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider=raw_provider,
    )


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

        if not response.choices:
            raise ValueError("LLM returned empty response (no choices)")

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
        result = self._inner.generate_content(contents, generation_config)
        self.calls_used += 1
        return result


def wrap_with_rate_limit(model: LLMModel, max_calls: int | None) -> LLMModel | RateLimitedLLMModel:
    if max_calls is None or max_calls <= 0:
        return model
    return RateLimitedLLMModel(model, max_calls)


# Cost estimation (configurable via env vars, defaults approximate MiniMax pricing)
_COST_INPUT_PER_M = float(os.environ.get("LLM_COST_INPUT_PER_MILLION_TOKENS", "0.10"))
_COST_OUTPUT_PER_M = float(os.environ.get("LLM_COST_OUTPUT_PER_MILLION_TOKENS", "0.40"))


def estimate_cost(token_info: dict) -> float:
    """Estimate cost in USD from token counts."""
    input_tokens = token_info.get("input_tokens", 0)
    output_tokens = token_info.get("output_tokens", 0)
    return (input_tokens * _COST_INPUT_PER_M + output_tokens * _COST_OUTPUT_PER_M) / 1_000_000


def extract_token_info(response) -> dict:
    """Extract token counts from an LLM response into a standard dict."""
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, "usage_metadata") else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, "usage_metadata") else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = estimate_cost(token_info)
    return token_info


def create_llm_model(provider: str | None = None) -> LLMModel:
    """Build the configured LLM client from environment variables."""
    cfg = resolve_llm_config(provider)
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    return LLMModel(client, cfg.model)
