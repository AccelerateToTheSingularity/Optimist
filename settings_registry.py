"""
Registry of bot settings exposed in the local settings GUI.

All runtime toggles map to environment variables read by config.py / bot_runner.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm_client import PROVIDER_PRESETS


# Always-visible safety / identity controls (Application Standard 10).
NON_HIDEABLE_KEYS = frozenset({
    "BOT_SAFE_MODE",
    "BOT_CONTENT_MODERATION_ENABLED",
    "BOT_SUBREDDIT",
    "BOT_PROFILE",
})

# Advanced / uncommon fields stay collapsed until Show advanced (Standards 25/31).
ADVANCED_KEYS = frozenset({
    "LLM_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GLM_API_KEY",
    "ZHIPU_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "TOGETHER_API_KEY",
    "XAI_API_KEY",
    "LLM_API_KEY",
    "REDDIT_USERNAME",
    "REDDIT_PASSWORD",
    "BOT_CONTENT_MODERATION_RULES",
    "BOT_ACCELERATION_PRO_AI_SUBS",
    "BOT_ACCELERATION_AUTOBAN_ENABLED",
    "BOT_ACCELERATION_AUTOBAN_THRESHOLD",
    "BOT_TROLL_MIN_COMMENTS",
    "BOT_TROLL_AVG_SCORE_THRESHOLD",
    "BOT_TROLL_EVAL_COOLDOWN_HOURS",
    "BOT_TROLL_ALERT_COOLDOWN_DAYS",
    "REDDIT_APP_NAME",
    "BOT_MILESTONE_TIERS_JSON",
    "BOT_SPECIALIST_ROLES",
    "BOT_SPECIALIST_PROMPT",
    "BOT_SPECIALIST_REFRESH_DAYS",
    "BOT_USER_FLAIR_TEMPLATE",
    "BOT_BAN_PHASE_ENABLED",
    "BOT_MAX_LLM_CALLS_PER_RUN",
    "BOT_MAX_TLDR_PER_RUN",
    "BOT_MAX_TLDR_PER_DAY",
    "BOT_POST_SCAN_LIMIT",
    "BOT_POST_WORD_THRESHOLD",
    "BOT_MAX_MODERATION_LLM_CALLS_PER_RUN",
    "BOT_MODERATION_RULES_WIKI_PAGE",
    "BOT_COMMENT_TLDR_PARENT_CONTEXT_ENABLED",
    "BOT_POST_TLDR_PIN",
    "BOT_COMMENT_SUMMARY_PIN",
})


@dataclass
class SettingField:
    key: str
    label: str
    section: str
    field_type: str  # bool, int, float, str, text, password, choice
    default: str = ""
    choices: list[str] = field(default_factory=list)
    help_text: str = ""
    hideable: bool = True
    advanced: bool = False


def _provider_choices() -> list[str]:
    return [k for k in PROVIDER_PRESETS if k != "custom"] + ["custom"]


def _field(
    key: str,
    label: str,
    section: str,
    field_type: str,
    default: str = "",
    choices: list[str] | None = None,
    help_text: str = "",
) -> SettingField:
    return SettingField(
        key=key,
        label=label,
        section=section,
        field_type=field_type,
        default=default,
        choices=choices or [],
        help_text=help_text,
        hideable=key not in NON_HIDEABLE_KEYS,
        advanced=key in ADVANCED_KEYS,
    )


SETTING_FIELDS: list[SettingField] = [
    # --- LLM ---
    _field("BOT_LLM_PROVIDER", "LLM provider preset", "LLM", "choice", "minimax", _provider_choices()),
    _field("LLM_MODEL", "Model ID (overrides preset)", "LLM", "str", "", help_text="e.g. deepseek-chat, claude-sonnet-4-20250514"),
    _field("OPENAI_BASE_URL", "Custom API base URL", "LLM", "str", "", help_text="Optional override for any OpenAI-compatible endpoint"),
    _field("OPENAI_API_KEY", "OpenAI / MiniMax API key", "LLM", "password"),
    _field("ANTHROPIC_API_KEY", "Anthropic (Claude) API key", "LLM", "password"),
    _field("GEMINI_API_KEY", "Google Gemini API key", "LLM", "password"),
    _field("DEEPSEEK_API_KEY", "DeepSeek API key", "LLM", "password"),
    _field("GLM_API_KEY", "Zhipu GLM API key", "LLM", "password"),
    _field("ZHIPU_API_KEY", "Zhipu API key (alias)", "LLM", "password"),
    _field("GROQ_API_KEY", "Groq API key", "LLM", "password"),
    _field("MISTRAL_API_KEY", "Mistral API key", "LLM", "password"),
    _field("TOGETHER_API_KEY", "Together AI API key", "LLM", "password"),
    _field("XAI_API_KEY", "xAI (Grok) API key", "LLM", "password"),
    _field("LLM_API_KEY", "Generic LLM API key", "LLM", "password", help_text="Fallback for custom provider"),
    # --- Reddit ---
    _field("REDDIT_CLIENT_ID", "Reddit client ID", "Reddit", "str"),
    _field("REDDIT_CLIENT_SECRET", "Reddit client secret", "Reddit", "password"),
    _field("REDDIT_REFRESH_TOKEN", "Reddit refresh token", "Reddit", "password"),
    _field("REDDIT_USERNAME", "Reddit username (legacy auth)", "Reddit", "str"),
    _field("REDDIT_PASSWORD", "Reddit password (legacy auth)", "Reddit", "password"),
    _field("BOT_SUBREDDIT", "Target subreddit", "Reddit", "str", "accelerate"),
    _field("BOT_PROFILE", "Runtime profile", "Reddit", "choice", "post_tldr_only", ["", "post_tldr_only", "minimax_starter", "proai_limited"]),
    # --- Safety ---
    _field("BOT_SAFE_MODE", "Safe mode (log only)", "Safety", "bool", "false"),
    _field("BOT_CONTENT_MODERATION_ENABLED", "AI moderation enabled", "Safety", "bool", "false"),
    _field(
        "BOT_CONTENT_MODERATION_ACTION", "Default moderation action", "Safety", "choice", "log",
        ["log", "report", "remove", "modmail"],
    ),
    # --- TLDR ---
    _field("BOT_POST_TLDR_ENABLED", "Post TLDRs", "TLDR", "bool", "true"),
    _field("BOT_COMMENT_TLDR_ENABLED", "Comment TLDRs", "TLDR", "bool", "false"),
    _field("BOT_COMMENT_SUMMARY_ENABLED", "Discussion summaries", "TLDR", "bool", "false"),
    _field("BOT_REDDIT_REFERENCE_TLDR_ENABLED", "Reddit link/crosspost TLDRs", "TLDR", "bool", "false"),
    _field("BOT_POST_TLDR_PIN", "Pin post TLDRs", "TLDR", "bool", "false"),
    _field("BOT_COMMENT_SUMMARY_PIN", "Pin discussion summaries", "TLDR", "bool", "false"),
    _field("BOT_COMMENT_TLDR_PARENT_CONTEXT_ENABLED", "Comment TLDR parent context", "TLDR", "bool", "false"),
    # --- Engagement ---
    _field("BOT_CONVERSATIONAL_REPLIES_ENABLED", "Conversational inbox replies", "Engagement", "bool", "false"),
    _field("BOT_INBOX_REPLIES_ENABLED", "Inbox replies (profile)", "Engagement", "bool", "false"),
    _field("BOT_SUMMONS_ENABLED", "Summon responses", "Engagement", "bool", "false"),
    # --- Flair ---
    _field("BOT_ACCELERATION_ENABLED", "Acceleration flair", "Flair", "bool", "false"),
    _field("BOT_MILESTONE_FLAIR_ENABLED", "Milestone flairs", "Flair", "bool", "false"),
    _field("BOT_SPECIALIST_FLAIR_ENABLED", "Specialist flairs", "Flair", "bool", "false"),
    _field(
        "BOT_ACCELERATION_PRO_AI_SUBS", "Pro-AI subs for acceleration karma", "Flair", "str",
        "accelerate,ProAI,TheMachineGod,DefendingAIArt,aiArt,aivideos",
    ),
    _field("BOT_ACCELERATION_AUTOBAN_ENABLED", "Acceleration auto-ban", "Flair", "bool", "false"),
    _field("BOT_ACCELERATION_AUTOBAN_THRESHOLD", "Auto-ban karma threshold", "Flair", "int", "-40"),
    # --- Troll alerts ---
    _field("BOT_TROLL_ALERT_ENABLED", "Troll alerts", "Troll alerts", "bool", "false"),
    _field("BOT_TROLL_MIN_COMMENTS", "Min comments for troll eval", "Troll alerts", "int", "10"),
    _field("BOT_TROLL_AVG_SCORE_THRESHOLD", "Avg score threshold", "Troll alerts", "float", "-30"),
    _field("BOT_TROLL_EVAL_COOLDOWN_HOURS", "Hours between troll re-checks", "Troll alerts", "int", "1"),
    _field("BOT_TROLL_ALERT_COOLDOWN_DAYS", "Days between repeat alerts", "Troll alerts", "int", "7"),
    _field("REDDIT_APP_NAME", "Reddit app name (User-Agent)", "Reddit", "str", "OptimistPrimeModBot"),
    _field("BOT_CONTENT_MODERATION_RULES", "Legacy LLM moderation rules prompt", "Safety", "text", ""),
    _field(
        "BOT_MILESTONE_TIERS_JSON", "Milestone flair tiers (JSON)", "Flair", "text",
        '[[100, "Veteran Accelerator"], [50, "Active Voice"], [25, "Regular"], [5, "Participant"], [1, "Newcomer"]]',
    ),
    _field(
        "BOT_SPECIALIST_ROLES", "Specialist role names (comma-separated)", "Flair", "str",
        "Capability Booster, Alignment Debater, Policy & Governance, Research Linker, "
        "Builder / Practitioner, Good-Faith Skeptic, Community Welcomer, Generalist",
    ),
    _field("BOT_SPECIALIST_PROMPT", "Specialist classification prompt", "Flair", "text", ""),
    _field("BOT_SPECIALIST_REFRESH_DAYS", "Days between specialist re-classify", "Flair", "int", "7"),
    _field("BOT_USER_FLAIR_TEMPLATE", "User flair template", "Flair", "str", "{acceleration} | {milestone} | {specialist}"),
    # --- Crosspost ---
    _field("BOT_CROSSPOST_ENABLED", "Crosspost to r/ProAI", "Crosspost", "bool", "false"),
    # --- Runtime limits ---
    _field("BOT_BAN_PHASE_ENABLED", "Auto-ban phase (negative karma)", "Runtime limits", "bool", "false"),
    _field("BOT_MAX_LLM_CALLS_PER_RUN", "Max LLM calls per run", "Runtime limits", "int", "", help_text="Empty = unlimited or profile default"),
    _field("BOT_MAX_TLDR_PER_RUN", "Max TLDRs per run", "Runtime limits", "int", "1"),
    _field("BOT_MAX_TLDR_PER_DAY", "Max TLDRs per day", "Runtime limits", "int", "40"),
    _field("BOT_POST_SCAN_LIMIT", "Posts scanned per run", "Runtime limits", "int", ""),
    _field("BOT_POST_WORD_THRESHOLD", "Min words for post TLDR", "Runtime limits", "int", "270"),
    _field("BOT_MAX_MODERATION_LLM_CALLS_PER_RUN", "Max moderation LLM calls/run", "Runtime limits", "int", ""),
    # --- Rules ---
    _field("BOT_MODERATION_RULES_FILE", "Rules JSON path", "Moderation rules", "str", "data/rules.json"),
    _field("BOT_MODERATION_RULES_WIKI_PAGE", "Wiki page for rule sync", "Moderation rules", "str", "config/moderation_rules"),
]


def sections() -> list[str]:
    seen: list[str] = []
    for f in SETTING_FIELDS:
        if f.section not in seen:
            seen.append(f.section)
    return seen


def fields_by_section() -> dict[str, list[SettingField]]:
    out: dict[str, list[SettingField]] = {}
    for f in SETTING_FIELDS:
        out.setdefault(f.section, []).append(f)
    return out
