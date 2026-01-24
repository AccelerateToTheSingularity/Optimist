"""
Centralized configuration for Reddit Bot (r/accelerate).
"""

# Subreddit configuration
SUBREDDIT = "accelerate"

# TLDR Settings
POST_WORD_THRESHOLD = 270  # Minimum words to trigger TLDR for posts
COMMENT_WORD_THRESHOLD = 400  # Minimum words to trigger TLDR for comments
MAX_TLDR_PER_RUN = 1  # Only 1 TLDR per run (~3 min between TLDRs)
MAX_TLDR_PER_DAY = 40  # Daily cap for TLDRs
MAX_AGE_HOURS = 24  # Only process posts/comments from last 24 hours
COMMENT_MILESTONES = [20, 50, 100]  # Comment thresholds for summaries

# Reply/Conversation Settings
MAX_REPLIES_PER_RUN = 1  # Limit conversational replies per execution (runs are ~3 min apart)
MAX_REPLIES_PER_DAY = 30  # Daily cap for conversational replies
MAX_REPLY_WORDS = 75  # Target max words for conversational replies (keep it tight)
MIN_REPLY_WORDS = 10  # Minimum words for replies (can be very short if appropriate)

# Rate limiting
SAME_USER_COOLDOWN_HOURS = 1  # Don't reply to same user within this window
SAME_USER_REPLIES_BEFORE_COOLDOWN = 2  # Allow this many replies to a user before cooldown kicks in
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

# ===== CROSSPOST SETTINGS =====
# Crosspost top AI posts from r/accelerate to r/ProAI
CROSSPOST_ENABLED = True                    # Kill switch for crossposting
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
ACCELERATION_ENABLED = True                 # Kill switch for acceleration feature

# Pro-AI subreddits to scan for karma (strongly pro-AI/singularity only)
ACCELERATION_PRO_AI_SUBS = [
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
ACCELERATION_FORCE_REFRESH = True           # Force refresh ALL opted-in users on next run (set to False after)

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
ACCELERATION_AUTOBAN_ENABLED = False        # Auto-ban extremely negative users (OFF)
ACCELERATION_AUTOBAN_THRESHOLD = -200       # Karma threshold for auto-ban
