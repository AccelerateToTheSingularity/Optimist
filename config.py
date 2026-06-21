"""
Centralized configuration for Reddit Bot (r/accelerate).
"""

import os


def _env_on(name: str, default: bool = False) -> bool:
    """Read a BOT_* boolean env var; empty/unset uses default."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Subreddit configuration
SUBREDDIT = "accelerate"

# TLDR Settings (default: post TLDRs only — enable other features one at a time)
POST_TLDR_ENABLED = _env_on("BOT_POST_TLDR_ENABLED", True)
COMMENT_TLDR_ENABLED = _env_on("BOT_COMMENT_TLDR_ENABLED", False)
COMMENT_SUMMARY_ENABLED = _env_on("BOT_COMMENT_SUMMARY_ENABLED", False)

POST_WORD_THRESHOLD = 270  # Minimum words to trigger TLDR for posts
COMMENT_WORD_THRESHOLD = 400  # Minimum words to trigger TLDR for comments
MAX_TLDR_PER_RUN = 1  # Only 1 TLDR per run (~3 min between TLDRs)
MAX_TLDR_PER_DAY = 40  # Daily cap for TLDRs
MAX_AGE_HOURS = 24  # Only process posts/comments from last 24 hours
COMMENT_MILESTONES = [20, 50, 100]  # Comment thresholds for summaries
POST_TLDR_PIN = os.environ.get("BOT_POST_TLDR_PIN", "").lower() in ("1", "true", "yes", "on")
COMMENT_SUMMARY_PIN = os.environ.get("BOT_COMMENT_SUMMARY_PIN", "").lower() in ("1", "true", "yes", "on")
REDDIT_REFERENCE_TLDR_ENABLED = _env_on("BOT_REDDIT_REFERENCE_TLDR_ENABLED", False)
COMMENT_TLDR_PARENT_CONTEXT_ENABLED = _env_on("BOT_COMMENT_TLDR_PARENT_CONTEXT_ENABLED", False)

# Reply/Conversation Settings
CONVERSATIONAL_REPLIES_ENABLED = _env_on("BOT_CONVERSATIONAL_REPLIES_ENABLED", False)
MAX_REPLIES_PER_RUN = 1  # Limit conversational replies per execution (runs are ~3 min apart)
MAX_REPLIES_PER_DAY = 30  # Daily cap for conversational replies
MAX_REPLY_WORDS = 75  # Target max words for conversational replies (keep it tight)
MIN_REPLY_WORDS = 10  # Minimum words for replies (can be very short if appropriate)

# Rate limiting
SAME_USER_COOLDOWN_HOURS = 1  # Don't reply to same user within this window
SAME_USER_REPLIES_BEFORE_COOLDOWN = 10  # Allow this many replies to a user before cooldown kicks in
MOD_CACHE_REFRESH_DAYS = 3  # Refresh moderator list from Reddit every N days

# Summon detection patterns (case-insensitive)
# These patterns will trigger the bot to respond
# PHILOSOPHY: Only trigger when someone is DIRECTLY addressing the bot themselves
# NOT when they're telling others to summon it or mentioning AI in general
#
# ❌ "Why don't you ask ai?" - telling someone else to use AI
# ❌ "Ask the bot about this" - telling someone else to summon
# ❌ "Someone should summon the bot" - indirect suggestion
# ✅ "Hey bot, what do you think?" - directly addressing the bot
# ✅ "Optimist Prime, help me out" - using the bot's name
# ✅ "I summon the bot" - first-person summoning
SUMMON_PATTERNS = [
    # Direct name mentions (always triggers - they're talking TO the bot)
    r"\boptimist\s*prime\b",
    
    # Direct username mention (Reddit style - clearly intentional)
    r"u/Optimist[\-_]?Prime\b",
    
    # Greetings DIRECTLY addressing the bot (greeting + bot term = talking TO it)
    r"\b(hey|hi|hello|yo|sup)\s+(optimist\s*prime|bot|mod\s*bot|tldr\s*bot)\b",
    
    # First-person summons only ("I summon", "I'm calling", etc.)
    r"\bI('m| am)?\s*(summon|summoning|calling|paging)\s+(the\s+)?(bot|optimist)\b",
    
    # Mod bot as direct address (specific enough to be intentional)
    r"\bmod\s*bot\b",
]

# Patterns that indicate hostile/bad-faith comments to avoid
HOSTILE_PATTERNS = [
    r"\b(stupid|dumb|useless|trash|garbage)\s+(bot|ai)\b",
    r"\bfuck\s*(off|you|this)\b",
    r"\bshut\s*(up|the\s*fuck)\b",
    r"\bkill\s+yourself\b",
    r"\bgo\s+away\b",
    r"\bnobody\s+(asked|cares)\b",
]

# Bot identification patterns (to avoid responding to other bots)
BOT_INDICATORS = [
    r"bot\b",
    r"Bot\b", 
    r"auto[\-_]?mod",
    r"AutoModerator",
]

# Owned bot usernames (never respond to these)
BOT_OWNED_USERNAMES = ["OptimistPrime_AI_Bot", "ai-mod-suite-bot"]

# ===== CROSSPOST SETTINGS =====
# Crosspost top AI posts from r/accelerate to r/ProAI
CROSSPOST_ENABLED = _env_on("BOT_CROSSPOST_ENABLED", False)
CROSSPOST_SOURCE_SUB = "accelerate"         # Subreddit to pull posts from
CROSSPOST_TARGET_SUB = "ProAI"              # Subreddit to crosspost to
CROSSPOST_MAX_PER_DAY = 1                   # Max crossposts per day (start conservative)
CROSSPOST_MIN_SCORE = 10                    # Minimum upvotes to consider a post
CROSSPOST_MIN_HOURS_OLD = 12                # Post must be at least this old (hours)
CROSSPOST_MAX_HOURS_OLD = 48                # Don't crosspost posts older than this (hours)
CROSSPOST_SKIP_CHANCE = 0.05                # 5% chance to skip a day (human-like)
CROSSPOST_TIME_VARIATION_HOURS = (1, 5)     # Random hour range for daily crosspost (UTC)
CROSSPOST_LOOKBACK_DAYS = 2                 # How far back to check target sub for dupes

# ===== ACCELERATION FACTOR SETTINGS =====
# Opt-in flair showing user's karma from pro-AI subreddits
ACCELERATION_ENABLED = _env_on("BOT_ACCELERATION_ENABLED", False)

# Pro-AI subreddits to scan for karma (strongly pro-AI/singularity only)
# Override with BOT_ACCELERATION_PRO_AI_SUBS env var (comma-separated)
ACCELERATION_PRO_AI_SUBS = [
    s.strip()
    for s in os.environ.get("BOT_ACCELERATION_PRO_AI_SUBS", "").split(",")
    if s.strip()
] or [
    "accelerate",
    "ProAI",
    "TheMachineGod",
    "DefendingAIArt",
    "aiArt",
    "aivideos",
]

# Scanning limits
ACCELERATION_SCAN_LIMIT = 1000              # Max posts/comments to scan for opted-in users
ACCELERATION_BACKGROUND_SCAN_LIMIT = 500    # Max to scan for background checks (non-opted-in)
ACCELERATION_REFRESH_DAYS = 7               # Min days between flair recalculations (opted-in)
ACCELERATION_BACKGROUND_REFRESH_DAYS = 30   # Min days between background scans (non-opted-in)
ACCELERATION_MAX_SCANS_PER_RUN = 1          # Max users to scan per bot run cycle (rate limiting)

# Tier thresholds (ratio of pro-AI karma / total karma)
# Format: (min_ratio, tier_name) - checked in order, first match wins
ACCELERATION_TIERS = [
    (0.90, "Light-speed"),   # 90%+ focused on pro-AI
    (0.70, "Hypersonic"),    # 70-90%
    (0.50, "Supersonic"),    # 50-70%
    (0.30, "Speeding"),      # 30-50%
    (0.15, "Cruising"),      # 15-30%
    (0.01, "Crawling"),      # 1-15% (any positive focus)
]
ACCELERATION_ZERO_TIER = "Stationary"       # Tier for ratio <= 0

# Moderation thresholds
ACCELERATION_MODMAIL_THRESHOLD = -50        # Send modmail if karma below this
ACCELERATION_AUTOBAN_ENABLED = os.environ.get("BOT_ACCELERATION_AUTOBAN_ENABLED", "").lower() in (
    "1", "true", "yes", "on"
)
ACCELERATION_AUTOBAN_THRESHOLD = int(os.environ.get("BOT_ACCELERATION_AUTOBAN_THRESHOLD", "-40"))

# Contributor flair (milestone + specialist, local subreddit activity)
MILESTONE_FLAIR_ENABLED = os.environ.get("BOT_MILESTONE_FLAIR_ENABLED", "").lower() in (
    "1", "true", "yes", "on"
)
SPECIALIST_FLAIR_ENABLED = os.environ.get("BOT_SPECIALIST_FLAIR_ENABLED", "").lower() in (
    "1", "true", "yes", "on"
)
MILESTONE_TIERS_JSON = os.environ.get(
    "BOT_MILESTONE_TIERS_JSON",
    '[[100, "Veteran Accelerator"], [50, "Active Voice"], [25, "Regular"], [5, "Participant"], [1, "Newcomer"]]',
)
SPECIALIST_ROLES = os.environ.get(
    "BOT_SPECIALIST_ROLES",
    "Capability Booster, Alignment Debater, Policy & Governance, Research Linker, "
    "Builder / Practitioner, Good-Faith Skeptic, Community Welcomer, Generalist",
)
SPECIALIST_PROMPT = os.environ.get(
    "BOT_SPECIALIST_PROMPT",
    "Analyze the user's comment history below and choose the single most appropriate role "
    "that describes their engagement style in a pro-AI acceleration community. "
    "Respond with ONLY the selected role name.",
)
SPECIALIST_REFRESH_DAYS = int(os.environ.get("BOT_SPECIALIST_REFRESH_DAYS", "7"))
USER_FLAIR_TEMPLATE = os.environ.get("BOT_USER_FLAIR_TEMPLATE", "{acceleration} | {milestone} | {specialist}")
USER_FLAIR_MAX_LEN = 64

# Troll alerts (local comment score average)
TROLL_ALERT_ENABLED = os.environ.get("BOT_TROLL_ALERT_ENABLED", "").lower() in ("1", "true", "yes", "on")
TROLL_MIN_COMMENTS = int(os.environ.get("BOT_TROLL_MIN_COMMENTS", "10"))
TROLL_AVG_SCORE_THRESHOLD = float(os.environ.get("BOT_TROLL_AVG_SCORE_THRESHOLD", "-30"))
TROLL_EVAL_COOLDOWN_HOURS = int(os.environ.get("BOT_TROLL_EVAL_COOLDOWN_HOURS", "1"))
TROLL_ALERT_COOLDOWN_DAYS = int(os.environ.get("BOT_TROLL_ALERT_COOLDOWN_DAYS", "7"))

# Auto-ban from automod negative-karma removals (ban_handler.py)
NEGATIVE_KARMA_BAN_REASON = "Auto-ban: Excessive negative karma (automod removal)"

# Safe mode: all actions log-only, nothing posted to Reddit
SAFE_MODE = os.environ.get("BOT_SAFE_MODE", "").lower() in ("1", "true", "yes", "on")

# Content moderation (LLM-based rule violation detection)
CONTENT_MODERATION_ENABLED = os.environ.get("BOT_CONTENT_MODERATION_ENABLED", "").lower() in ("1", "true", "yes", "on")
_CONTENT_MODERATION_ACTION_RAW = os.environ.get("BOT_CONTENT_MODERATION_ACTION", "log")
_VALID_MODERATION_ACTIONS = {"report", "remove", "modmail", "log"}
CONTENT_MODERATION_ACTION = _CONTENT_MODERATION_ACTION_RAW if _CONTENT_MODERATION_ACTION_RAW in _VALID_MODERATION_ACTIONS else "log"
CONTENT_MODERATION_RULES = os.environ.get("BOT_CONTENT_MODERATION_RULES", "")  # Rules prompt for the LLM

# Discrete rule-based moderation (new system)
MODERATION_RULES_FILE = os.environ.get("BOT_MODERATION_RULES_FILE", "data/rules.json")
MODERATION_RULES_JSON = os.environ.get("BOT_MODERATION_RULES_JSON", "")  # Inline JSON override
MODERATION_RULES_WIKI_PAGE = os.environ.get("BOT_MODERATION_RULES_WIKI_PAGE", "config/moderation_rules")

# LLM provider preset (minimax, openai, deepseek, gemini, custom)
LLM_PROVIDER = os.environ.get("BOT_LLM_PROVIDER", "minimax")
