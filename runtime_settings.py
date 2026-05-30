"""
Environment-driven runtime overrides for safe, low-cost test runs.

Set BOT_PROFILE=proai_limited (or use workflow_dispatch) to run only on r/ProAI
with at most one LLM call per cycle and heavy features disabled.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import config


def _env_bool(name: str, default: bool | None = None) -> bool | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int | None = None) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


PROFILE_PRESETS: dict[str, dict] = {
    "proai_limited": {
        "subreddit": "ProAI",
        "post_tldr_enabled": True,
        "comment_tldr_enabled": False,
        "comment_summary_enabled": False,
        "crosspost_enabled": False,
        "acceleration_enabled": False,
        "ban_phase_enabled": False,
        "inbox_replies_enabled": False,
        "summons_enabled": True,
        "max_llm_calls_per_run": 1,
        "max_tldr_per_run": 1,
        "max_replies_per_run": 1,
        "max_tldr_per_day": 3,
        "max_replies_per_day": 3,
        "post_scan_limit": 15,
        "post_word_threshold": 200,
    },
}


@dataclass
class RuntimeSettings:
    profile: str = ""
    subreddit: str = config.SUBREDDIT
    post_tldr_enabled: bool = config.POST_TLDR_ENABLED
    comment_tldr_enabled: bool = config.COMMENT_TLDR_ENABLED
    comment_summary_enabled: bool = config.COMMENT_SUMMARY_ENABLED
    crosspost_enabled: bool = config.CROSSPOST_ENABLED
    acceleration_enabled: bool = config.ACCELERATION_ENABLED
    ban_phase_enabled: bool = True
    inbox_replies_enabled: bool = True
    summons_enabled: bool = True
    max_llm_calls_per_run: int | None = None
    max_tldr_per_run: int = config.MAX_TLDR_PER_RUN
    max_replies_per_run: int = config.MAX_REPLIES_PER_RUN
    max_tldr_per_day: int = config.MAX_TLDR_PER_DAY
    max_replies_per_day: int = config.MAX_REPLIES_PER_DAY
    post_scan_limit: int | None = None
    post_word_threshold: int = config.POST_WORD_THRESHOLD
    extra_summon_patterns: list[str] = field(default_factory=list)

    def describe(self) -> str:
        llm_cap = (
            str(self.max_llm_calls_per_run)
            if self.max_llm_calls_per_run is not None
            else "unlimited"
        )
        parts = [
            f"profile={self.profile or 'default'}",
            f"subreddit=r/{self.subreddit}",
            f"max_llm_calls={llm_cap}",
            f"post_tldr={self.post_tldr_enabled}",
            f"summons={self.summons_enabled}",
            f"inbox_replies={self.inbox_replies_enabled}",
            f"crosspost={self.crosspost_enabled}",
            f"acceleration={self.acceleration_enabled}",
            f"bans={self.ban_phase_enabled}",
        ]
        return ", ".join(parts)


def resolve_runtime_settings(bot_username: str | None = None) -> RuntimeSettings:
    profile = os.environ.get("BOT_PROFILE", "").strip().lower()
    preset = PROFILE_PRESETS.get(profile, {})

    subreddit = os.environ.get("BOT_SUBREDDIT", preset.get("subreddit", config.SUBREDDIT)).strip()

    settings = RuntimeSettings(
        profile=profile,
        subreddit=subreddit,
        post_tldr_enabled=preset.get("post_tldr_enabled", config.POST_TLDR_ENABLED),
        comment_tldr_enabled=preset.get("comment_tldr_enabled", config.COMMENT_TLDR_ENABLED),
        comment_summary_enabled=preset.get(
            "comment_summary_enabled", config.COMMENT_SUMMARY_ENABLED
        ),
        crosspost_enabled=preset.get("crosspost_enabled", config.CROSSPOST_ENABLED),
        acceleration_enabled=preset.get("acceleration_enabled", config.ACCELERATION_ENABLED),
        ban_phase_enabled=preset.get("ban_phase_enabled", True),
        inbox_replies_enabled=preset.get("inbox_replies_enabled", True),
        summons_enabled=preset.get("summons_enabled", True),
        max_llm_calls_per_run=preset.get("max_llm_calls_per_run"),
        max_tldr_per_run=preset.get("max_tldr_per_run", config.MAX_TLDR_PER_RUN),
        max_replies_per_run=preset.get("max_replies_per_run", config.MAX_REPLIES_PER_RUN),
        max_tldr_per_day=preset.get("max_tldr_per_day", config.MAX_TLDR_PER_DAY),
        max_replies_per_day=preset.get("max_replies_per_day", config.MAX_REPLIES_PER_DAY),
        post_scan_limit=preset.get("post_scan_limit"),
        post_word_threshold=preset.get("post_word_threshold", config.POST_WORD_THRESHOLD),
    )

    # Per-flag env overrides (win over preset)
    for attr, env_name in (
        ("post_tldr_enabled", "BOT_POST_TLDR_ENABLED"),
        ("comment_tldr_enabled", "BOT_COMMENT_TLDR_ENABLED"),
        ("comment_summary_enabled", "BOT_COMMENT_SUMMARY_ENABLED"),
        ("crosspost_enabled", "BOT_CROSSPOST_ENABLED"),
        ("acceleration_enabled", "BOT_ACCELERATION_ENABLED"),
        ("ban_phase_enabled", "BOT_BAN_PHASE_ENABLED"),
        ("inbox_replies_enabled", "BOT_INBOX_REPLIES_ENABLED"),
        ("summons_enabled", "BOT_SUMMONS_ENABLED"),
    ):
        value = _env_bool(env_name)
        if value is not None:
            setattr(settings, attr, value)

    if subreddit_env := os.environ.get("BOT_SUBREDDIT"):
        settings.subreddit = subreddit_env.strip()

    if (max_llm := _env_int("BOT_MAX_LLM_CALLS_PER_RUN")) is not None:
        settings.max_llm_calls_per_run = max_llm
    if (scan_limit := _env_int("BOT_POST_SCAN_LIMIT")) is not None:
        settings.post_scan_limit = scan_limit
    if (word_threshold := _env_int("BOT_POST_WORD_THRESHOLD")) is not None:
        settings.post_word_threshold = word_threshold
    if (max_tldr_run := _env_int("BOT_MAX_TLDR_PER_RUN")) is not None:
        settings.max_tldr_per_run = max_tldr_run
    if (max_tldr_day := _env_int("BOT_MAX_TLDR_PER_DAY")) is not None:
        settings.max_tldr_per_day = max_tldr_day

    if bot_username:
        safe_name = re.escape(bot_username)
        settings.extra_summon_patterns.append(rf"\bu/{safe_name}\b")
        settings.extra_summon_patterns.append(rf"\b{safe_name}\b")

    return settings


def apply_runtime_settings(settings: RuntimeSettings) -> None:
    """Push resolved settings into the config module for handlers to read."""
    config.SUBREDDIT = settings.subreddit
    config.POST_TLDR_ENABLED = settings.post_tldr_enabled
    config.COMMENT_TLDR_ENABLED = settings.comment_tldr_enabled
    config.COMMENT_SUMMARY_ENABLED = settings.comment_summary_enabled
    config.CROSSPOST_ENABLED = settings.crosspost_enabled
    config.ACCELERATION_ENABLED = settings.acceleration_enabled
    config.MAX_TLDR_PER_RUN = settings.max_tldr_per_run
    config.MAX_REPLIES_PER_RUN = settings.max_replies_per_run
    config.MAX_TLDR_PER_DAY = settings.max_tldr_per_day
    config.MAX_REPLIES_PER_DAY = settings.max_replies_per_day
    config.POST_WORD_THRESHOLD = settings.post_word_threshold

    if settings.extra_summon_patterns:
        config.SUMMON_PATTERNS = list(config.SUMMON_PATTERNS) + settings.extra_summon_patterns
