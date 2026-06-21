"""
Shared utility functions for bot detection and common checks.
"""

import re
from datetime import datetime, timezone

import config
from config import BOT_INDICATORS, BOT_OWNED_USERNAMES, MAX_AGE_HOURS, HOSTILE_PATTERNS


def is_likely_bot(author_name: str | None) -> bool:
    """
    Check if an author is likely a bot based on username patterns.

    Checks:
    - BOT_OWNED_USERNAMES (our own bots)
    - BOT_INDICATORS regex patterns
    - Common bot username suffixes (endswith "bot", "-mod")
    - "automod" substring
    """
    if not author_name:
        return True  # Treat deleted users as bots

    name_lower = author_name.lower()

    # Check owned bot usernames first
    if author_name in BOT_OWNED_USERNAMES:
        return True

    # Check common bot suffixes
    if name_lower.endswith("bot") or name_lower.endswith("-mod") or "automod" in name_lower:
        return True

    # Check regex patterns
    for pattern in BOT_INDICATORS:
        if re.search(pattern.lower(), name_lower):
            return True

    return False


def is_too_old(created_utc: float) -> bool:
    """Check if a post/comment is older than MAX_AGE_HOURS."""
    age_seconds = datetime.now(timezone.utc).timestamp() - created_utc
    age_hours = age_seconds / 3600
    return age_hours > MAX_AGE_HOURS


def is_hostile_comment(text: str) -> bool:
    """Check if a comment appears hostile/bad-faith."""
    text_lower = text.lower()
    for pattern in HOSTILE_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def check_user_cooldown(author_name: str | None, recent_replies: dict) -> bool:
    """Check if we've recently replied to this user too many times."""
    from config import SAME_USER_COOLDOWN_HOURS, SAME_USER_REPLIES_BEFORE_COOLDOWN

    if not author_name or author_name not in recent_replies:
        return False

    user_data = recent_replies[author_name]
    reply_count = user_data.get("count", 0)
    first_reply_time = user_data.get("first_reply_time", 0)

    # If under the limit, allow reply
    if reply_count < SAME_USER_REPLIES_BEFORE_COOLDOWN:
        return False

    # Over limit - check if cooldown has expired
    hours_since = (datetime.now(timezone.utc).timestamp() - first_reply_time) / 3600
    return hours_since < SAME_USER_COOLDOWN_HOURS


def get_cached_moderators(state: dict, subreddit) -> set:
    """
    Get moderator set from cache, refreshing from Reddit if stale.
    Updates state in-place with cached data.
    """
    from config import MOD_CACHE_REFRESH_DAYS

    now = datetime.now(timezone.utc).timestamp()
    cache_max_age = MOD_CACHE_REFRESH_DAYS * 24 * 3600  # Convert days to seconds

    cached_mods = state.get("moderator_cache", {})
    last_refresh = cached_mods.get("last_refresh", 0)
    mod_list = cached_mods.get("moderators", [])

    # Check if cache is fresh enough
    if mod_list and (now - last_refresh) < cache_max_age:
        return set(m.lower() for m in mod_list)

    # Cache is stale or empty - refresh from Reddit
    try:
        fresh_mods = [mod.name for mod in subreddit.moderator()]
        state["moderator_cache"] = {
            "moderators": fresh_mods,
            "last_refresh": now
        }
        print(f"    🔄 Refreshed moderator cache ({len(fresh_mods)} mods)")
        return set(m.lower() for m in fresh_mods)
    except Exception as e:
        print(f"    ⚠️ Could not refresh mod cache: {e}")
        # Return stale cache if available, otherwise empty
        return set(m.lower() for m in mod_list)


def is_moderator(author_name: str | None, state: dict, subreddit) -> bool:
    """Check if a user is a moderator of the subreddit."""
    if not author_name:
        return False
    mods = get_cached_moderators(state, subreddit)
    return author_name.lower() in mods


def validate_reply_response(response, item_type="comment") -> bool:
    """
    Validate that a Reddit API reply response has expected attributes.

    Args:
        response: The PRAW response object from reply()
        item_type: Description for error messages (e.g. "comment", "post")

    Returns:
        True if valid, raises ValueError if not
    """
    if response is None:
        raise ValueError(f"Reddit API returned None response for {item_type}")
    if not hasattr(response, "id") or not response.id:
        raise ValueError(f"Reddit API returned response without valid ID for {item_type}")
    if not hasattr(response, "permalink"):
        raise ValueError(f"Reddit API returned response without permalink for {item_type}")
    return True


def is_content_approved(content_obj) -> bool:
    """Return True if Reddit content is moderator-approved."""
    try:
        return bool(getattr(content_obj, "approved", False))
    except Exception:
        return False


def claim_action(state: dict, key: str, *, max_keys: int = 5000) -> bool:
    """
    Record a one-time action key in bot state. Returns True if this is the first claim.

    Keys are namespaced, e.g. moderation:t3_abc, troll_alert:username.
    """
    action_keys = state.setdefault("action_keys", [])
    if key in action_keys:
        return False
    action_keys.append(key)
    if len(action_keys) > max_keys:
        state["action_keys"] = action_keys[-max_keys:]
    return True


def has_action_claim(state: dict, key: str) -> bool:
    """Return True if an action key was already claimed."""
    return key in state.get("action_keys", [])
