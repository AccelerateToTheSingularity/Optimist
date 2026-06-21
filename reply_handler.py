"""
Inbox reply monitoring for the Optimist Prime bot.
Handles responding to users who reply to the bot's comments.
"""

import re
from datetime import datetime, timezone

import config
from config import (
    MAX_REPLIES_PER_RUN,
    MAX_AGE_HOURS,
    HOSTILE_PATTERNS,
    SAME_USER_COOLDOWN_HOURS,
    SAME_USER_REPLIES_BEFORE_COOLDOWN,
    MOD_CACHE_REFRESH_DAYS,
)
from bot_utils import (
    is_likely_bot,
    is_too_old,
    is_hostile_comment,
    check_user_cooldown,
    get_cached_moderators,
    is_moderator,
)
from persona import generate_conversational_response
from bot_comment_format import format_bot_comment
from acceleration_handler import handle_acceleration_command
from bot_utils import validate_reply_response


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
            if item.subreddit.display_name.lower() != config.SUBREDDIT.lower():
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
            # NOTE: Cooldown-skipped comments are NOT added to replied_to — they will be
            # re-fetched and re-evaluated on every subsequent run until they age out (24h).
            # This is intentional: delay-not-prevent. The overhead is acceptable given the
            # low volume and the benefit of retrying after cooldown expires.
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
                if config.ACCELERATION_ENABLED:
                    accel_response, state = handle_acceleration_command(
                        item, subreddit, reddit, gemini_model, state, dry_run
                    )
                    if accel_response:
                        # This was an acceleration command
                        accel_reply = item.reply(format_bot_comment(accel_response))
                        validate_reply_response(accel_reply, "acceleration reply")
                        accel_reply.mod.distinguish(sticky=False)
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
                reply = item.reply(format_bot_comment(response_text))
                validate_reply_response(reply, "conversational reply")
                reply.mod.distinguish(sticky=False)
                
                print(f"       ✅ Replied ({len(response_text.split())} words, {token_info['total_tokens']} tokens)")
                
                from audit_log import log_audit_event
                log_audit_event("reply", item.id, author_name or "[deleted]", item.body, "replied", True)
                
                # Update tracking
                replied_to.add(item.id)
                # Track reply count per user (reset if cooldown window has passed)
                now = datetime.now(timezone.utc).timestamp()
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
    now = datetime.now(timezone.utc).timestamp()
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
