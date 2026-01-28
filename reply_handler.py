"""
Inbox reply monitoring for the Optimist Prime bot.
Handles responding to users who reply to the bot's comments.
"""

import re
from datetime import datetime

from config import (
    SUBREDDIT,
    MAX_REPLIES_PER_RUN,
    MAX_AGE_HOURS,
    HOSTILE_PATTERNS,
    BOT_INDICATORS,
    SAME_USER_COOLDOWN_HOURS,
    SAME_USER_REPLIES_BEFORE_COOLDOWN,
    MOD_CACHE_REFRESH_DAYS,
    ACCELERATION_ENABLED,
)
from persona import generate_conversational_response
from acceleration_handler import handle_acceleration_command


def get_cached_moderators(state: dict, subreddit) -> set:
    """
    Get moderator set from cache, refreshing from Reddit if stale.
    Updates state in-place with cached data.
    """
    now = datetime.utcnow().timestamp()
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


def is_hostile_comment(text: str) -> bool:
    """Check if a comment appears hostile/bad-faith."""
    text_lower = text.lower()
    for pattern in HOSTILE_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def is_likely_bot(author_name: str | None) -> bool:
    """Check if an author is likely a bot based on username patterns."""
    if not author_name:
        return True  # Treat deleted users as bots
    
    name_lower = author_name.lower()
    for pattern in BOT_INDICATORS:
        if re.search(pattern.lower(), name_lower):
            return True
    return False


def is_too_old(created_utc: float) -> bool:
    """Check if a comment is older than MAX_AGE_HOURS."""
    age_seconds = datetime.utcnow().timestamp() - created_utc
    age_hours = age_seconds / 3600
    return age_hours > MAX_AGE_HOURS


def check_user_cooldown(author_name: str | None, recent_replies: dict) -> bool:
    """
    Check if we've recently replied to this user too many times.
    
    Args:
        author_name: The username to check
        recent_replies: Dict of {username: {count: int, first_reply_time: float}}
    
    Returns:
        True if we should skip (user is on cooldown), False if OK to reply
    """
    if not author_name or author_name not in recent_replies:
        return False
    
    user_data = recent_replies[author_name]
    reply_count = user_data.get("count", 0)
    first_reply_time = user_data.get("first_reply_time", 0)
    
    # If under the limit, allow reply
    if reply_count < SAME_USER_REPLIES_BEFORE_COOLDOWN:
        return False
    
    # Over limit - check if cooldown has expired
    hours_since = (datetime.utcnow().timestamp() - first_reply_time) / 3600
    return hours_since < SAME_USER_COOLDOWN_HOURS


def check_inbox_replies(
    reddit,
    gemini_model,
    state: dict,
    bot_username: str,
    dry_run: bool = False
) -> tuple[int, int, float, dict]:
    """
    Check bot's inbox for replies to our comments and respond.
    
    Args:
        reddit: Authenticated PRAW Reddit instance
        gemini_model: Initialized Gemini model
        state: Current bot state dict
        bot_username: The bot's Reddit username
        dry_run: If True, don't actually post replies
    
    Returns:
        Tuple of (replies_sent, tokens_used, cost, updated_state)
    """
    replies_sent = 0
    total_tokens = 0
    total_cost = 0.0
    
    # Get tracking sets from state
    replied_to = set(state.get("replied_to_comments", []))
    recent_user_replies = state.get("recent_user_replies", {})
    
    print(f"  📬 Checking inbox for replies to bot comments...")
    
    try:
        # Get comment replies from inbox
        # This returns comments that are direct replies to our comments
        inbox_items = list(reddit.inbox.comment_replies(limit=50))
        
        for item in inbox_items:
            # Check if we've hit the per-run limit
            if replies_sent >= MAX_REPLIES_PER_RUN:
                print(f"  ⏸️ Reached max replies per run ({MAX_REPLIES_PER_RUN})")
                break
            
            # Skip if already replied to
            if item.id in replied_to:
                continue
            
            # Skip if too old
            if is_too_old(item.created_utc):
                continue
            
            # Skip if not from our subreddit
            if item.subreddit.display_name.lower() != SUBREDDIT.lower():
                continue
            
            # Skip deleted comments
            if not item.body or item.body == '[deleted]':
                replied_to.add(item.id)  # Mark as processed
                continue
            
            # Skip if author is a bot
            author_name = item.author.name if item.author else None
            if is_likely_bot(author_name):
                replied_to.add(item.id)
                continue
            
            # Skip if hostile
            if is_hostile_comment(item.body):
                print(f"    ⏭️ Skipping hostile comment from u/{author_name}")
                replied_to.add(item.id)
                continue
            
            # Check user cooldown (moderators bypass this)
            if not is_moderator(author_name, state, item.subreddit) and check_user_cooldown(author_name, recent_user_replies):
                print(f"    ⏭️ Skipping u/{author_name} (cooldown active)")
                continue
            
            print(f"    💬 Reply from u/{author_name}: {item.body[:50]}...")
            
            if dry_run:
                print(f"       [DRY RUN] Would respond to comment {item.id}")
                replied_to.add(item.id)
                continue
            
            try:
                # Get the submission for context
                submission = item.submission
                subreddit = item.subreddit
                
                # Check if this is an acceleration command first
                if ACCELERATION_ENABLED:
                    accel_response, state = handle_acceleration_command(
                        item, subreddit, reddit, gemini_model, state, dry_run
                    )
                    if accel_response:
                        # This was an acceleration command
                        item.reply(accel_response)
                        print(f"       🚀 Handled acceleration command for u/{author_name}")
                        replied_to.add(item.id)
                        replies_sent += 1
                        continue
                
                # Generate regular conversational response
                response_text, token_info = generate_conversational_response(
                    item,
                    submission,
                    gemini_model,
                    is_summon=False
                )
                
                # Post the reply
                item.reply(response_text)
                
                print(f"       ✅ Replied ({len(response_text.split())} words, {token_info['total_tokens']} tokens)")
                
                # Update tracking
                replied_to.add(item.id)
                # Track reply count per user (reset if cooldown window has passed)
                now = datetime.utcnow().timestamp()
                if author_name not in recent_user_replies:
                    recent_user_replies[author_name] = {"count": 1, "first_reply_time": now}
                else:
                    # Check if the cooldown window has passed - if so, reset the tracking
                    hours_since = (now - recent_user_replies[author_name].get("first_reply_time", 0)) / 3600
                    if hours_since >= SAME_USER_COOLDOWN_HOURS:
                        # Cooldown expired, start fresh window
                        recent_user_replies[author_name] = {"count": 1, "first_reply_time": now}
                    else:
                        # Still within window, increment count
                        recent_user_replies[author_name]["count"] = recent_user_replies[author_name].get("count", 0) + 1
                replies_sent += 1
                total_tokens += token_info["total_tokens"]
                total_cost += token_info["cost"]
                
            except Exception as e:
                print(f"       ❌ Error replying: {e}")
                replied_to.add(item.id)  # Mark as processed to avoid retry loop
    
    except Exception as e:
        print(f"  ❌ Error checking inbox: {e}")
    
# Clean up old user reply tracking (remove entries older than cooldown window)
    now = datetime.utcnow().timestamp()
    cutoff_seconds = SAME_USER_COOLDOWN_HOURS * 3600
    recent_user_replies = {
        user: data for user, data in recent_user_replies.items()
        if (now - data.get("first_reply_time", 0)) < cutoff_seconds
    }

    # Update state
    state["replied_to_comments"] = list(replied_to)[-2000:]  # Keep last 2000
    state["recent_user_replies"] = recent_user_replies
    state["daily_replies"] = state.get("daily_replies", 0) + replies_sent
    
    return replies_sent, total_tokens, total_cost, state
