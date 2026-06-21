"""
Summon detection and response for the Optimist Prime bot.
Handles responding when users explicitly summon the bot anywhere in r/accelerate.
"""

import re
from datetime import datetime, timezone

import config
from config import (
    MAX_REPLIES_PER_RUN,
    MAX_AGE_HOURS,
    SUMMON_PATTERNS,
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
from persona import generate_conversational_response, generate_post_summon_response
from bot_comment_format import format_bot_comment
from acceleration_handler import (
    handle_acceleration_command,
    queue_background_scan,
)
from bot_utils import validate_reply_response


def is_summon(text: str) -> bool:
    """Check if text contains a summon phrase for the bot."""
    text_lower = text.lower()
    for pattern in SUMMON_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def check_for_summons(
    subreddit,
    gemini_model,
    state: dict,
    bot_username: str,
    reddit=None,
    dry_run: bool = False
) -> tuple[int, int, float, dict]:
    """
    Scan recent comments and posts for summon phrases and respond.
    
    Args:
        subreddit: PRAW Subreddit object
        gemini_model: Initialized Gemini model
        state: Current bot state dict
        bot_username: The bot's Reddit username
        reddit: PRAW Reddit instance (for acceleration feature)
        dry_run: If True, don't actually post replies
    
    Returns:
        Tuple of (summons_handled, tokens_used, cost, updated_state)
    """
    summons_handled = 0
    total_tokens = 0
    total_cost = 0.0
    
    # Get tracking sets from state
    summon_responses = set(state.get("summon_responses", []))
    recent_user_replies = state.get("recent_user_replies", {})
    
    print(f"  🔔 Scanning for bot summons in r/{subreddit.display_name}...")
    
    # Check comments
    try:
        comments = list(subreddit.comments(limit=100))
        
        # Batch fetch parent authors to avoid N+1 API calls
        parent_author_cache = {}
        # Use passed reddit instance or try to get it from subreddit object
        reddit_instance = reddit if reddit else getattr(subreddit, "_reddit", None)

        if reddit_instance:
            parent_ids_to_fetch = set()
            for comment in comments:
                # Pre-filter to reduce fetch count
                if comment.id in summon_responses: continue
                if is_too_old(comment.created_utc): continue
                if comment.author and comment.author.name == bot_username: continue

                # Check parents for replies
                if hasattr(comment, 'parent_id'):
                    parent_ids_to_fetch.add(comment.parent_id)

            if parent_ids_to_fetch:
                try:
                    # Fetch all parents in one go
                    parents = reddit_instance.info(fullnames=list(parent_ids_to_fetch))
                    for parent in parents:
                        if hasattr(parent, 'author') and parent.author:
                            parent_author_cache[parent.fullname] = parent.author.name
                except Exception as e:
                    print(f"    ⚠️ Could not batch fetch parents: {e}")

        for comment in comments:
            # Check limits
            if summons_handled >= MAX_REPLIES_PER_RUN:
                print(f"  ⏸️ Reached max summon responses per run ({MAX_REPLIES_PER_RUN})")
                break
            
            # Skip already processed
            if comment.id in summon_responses:
                continue
            
            # Skip too old
            if is_too_old(comment.created_utc):
                continue
            
            # Skip if it's our own comment
            if comment.author and comment.author.name == bot_username:
                continue
            
            # Skip if this is a reply to our comment (reply_handler will handle those)
            try:
                # Optimized check using cache or fast path
                parent_id = getattr(comment, 'parent_id', None)

                if parent_id and parent_id in parent_author_cache:
                    if parent_author_cache[parent_id] == bot_username:
                        continue
                # Fallback to slow N+1 method if not cached (e.g. reddit instance unavailable or fetch failed)
                elif not parent_author_cache:
                    parent = comment.parent()
                    if hasattr(parent, 'author') and parent.author and parent.author.name == bot_username:
                        continue
            except Exception:
                pass  # If we can't get parent, proceed normally
            
            # Skip deleted
            if not comment.body or comment.body == '[deleted]':
                continue
            
            author_name = comment.author.name if comment.author else None
            
            # Queue commenter for background scan (processed 1 per cycle)
            if config.ACCELERATION_ENABLED and author_name and not is_likely_bot(author_name):
                state = queue_background_scan(author_name, state)
            
            # Check if this is a summon
            if not is_summon(comment.body):
                continue
            
            # Skip bots
            if is_likely_bot(author_name):
                summon_responses.add(comment.id)
                continue
            
            # Skip hostile
            if is_hostile_comment(comment.body):
                print(f"    ⏭️ Skipping hostile summon from u/{author_name}")
                summon_responses.add(comment.id)
                continue
            
            # Check user cooldown (moderators bypass this)
            if not is_moderator(author_name, state, subreddit) and check_user_cooldown(author_name, recent_user_replies):
                print(f"    ⏭️ Skipping u/{author_name} (cooldown active)")
                continue
            
            print(f"    🔔 Summon detected from u/{author_name}: {comment.body[:60]}...")
            
            if dry_run:
                print(f"       [DRY RUN] Would respond to summon in comment {comment.id}")
                summon_responses.add(comment.id)
                continue
            
            try:
                # Get submission for context
                submission = comment.submission
                
                # Check if this is an acceleration command first
                if config.ACCELERATION_ENABLED and reddit:
                    accel_response, state = handle_acceleration_command(
                        comment, subreddit, reddit, gemini_model, state, dry_run
                    )
                    if accel_response:
                        # This was an acceleration command
                        if not dry_run:
                            accel_reply = comment.reply(format_bot_comment(accel_response))
                            validate_reply_response(accel_reply, "acceleration reply")
                            accel_reply.mod.distinguish(sticky=False)
                        print(f"       🚀 Handled acceleration command for u/{author_name}")
                        summon_responses.add(comment.id)
                        summons_handled += 1
                        continue
                
                # Generate regular conversational response
                response_text, token_info = generate_conversational_response(
                    comment,
                    submission,
                    gemini_model,
                    is_summon=True
                )
                
                # Post the reply
                reply = comment.reply(format_bot_comment(response_text))
                validate_reply_response(reply, "summon reply")
                reply.mod.distinguish(sticky=False)
                
                print(f"       ✅ Responded to summon ({len(response_text.split())} words, {token_info['total_tokens']} tokens)")
                
                from audit_log import log_audit_event
                log_audit_event("summon", comment.id, author_name or "[deleted]", comment.body, "replied", True)
                
                # Update tracking
                summon_responses.add(comment.id)
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
                summons_handled += 1
                total_tokens += token_info["total_tokens"]
                total_cost += token_info["cost"]
                
            except Exception as e:
                print(f"       ❌ Error responding to summon: {e}")
                summon_responses.add(comment.id)
    
    except Exception as e:
        print(f"  ❌ Error scanning comments for summons: {e}")
    
    # Check posts for summons (in title or body)
    if summons_handled < MAX_REPLIES_PER_RUN:
        try:
            # Rate limiting: wait before making another API call
            import time
            time.sleep(0.5)
            
            posts = list(subreddit.new(limit=25))
            
            for post in posts:
                if summons_handled >= MAX_REPLIES_PER_RUN:
                    break
                
                post_id = f"post_{post.id}"
                
                # Skip already processed
                if post_id in summon_responses:
                    continue
                
                # Skip too old
                if is_too_old(post.created_utc):
                    continue
                
                # Skip if it's our own post (unlikely but possible)
                if post.author and post.author.name == bot_username:
                    continue
                
                # Check for summon in title or body
                combined_text = f"{post.title} {post.selftext or ''}"
                if not is_summon(combined_text):
                    continue
                
                author_name = post.author.name if post.author else None
                
                # Skip bots
                if is_likely_bot(author_name):
                    summon_responses.add(post_id)
                    continue
                
                # Skip hostile
                if is_hostile_comment(combined_text):
                    print(f"    ⏭️ Skipping hostile post summon from u/{author_name}")
                    summon_responses.add(post_id)
                    continue
                
                # Check user cooldown (moderators bypass this)
                if not is_moderator(author_name, state, subreddit) and check_user_cooldown(author_name, recent_user_replies):
                    print(f"    ⏭️ Skipping u/{author_name} (cooldown active)")
                    continue
                
                print(f"    🔔 Summon in post by u/{author_name}: {post.title[:50]}...")
                
                if dry_run:
                    print(f"       [DRY RUN] Would respond to summon in post {post.id}")
                    summon_responses.add(post_id)
                    continue
                
                try:
                    # Generate response for post
                    response_text, token_info = generate_post_summon_response(
                        post,
                        gemini_model
                    )
                    
                    # Post the reply
                    reply = post.reply(format_bot_comment(response_text))
                    validate_reply_response(reply, "post summon reply")
                    reply.mod.distinguish(sticky=False)
                    
                    print(f"       ✅ Responded to post summon ({len(response_text.split())} words, {token_info['total_tokens']} tokens)")
                    
                    # Log audit event
                    from audit_log import log_audit_event
                    log_audit_event("post_summon", post_id, author_name, post.title[:100], "replied", True)
                    
                    # Update tracking
                    summon_responses.add(post_id)
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
                    summons_handled += 1
                    total_tokens += token_info["total_tokens"]
                    total_cost += token_info["cost"]
                    
                except Exception as e:
                    print(f"       ❌ Error responding to post summon: {e}")
                    summon_responses.add(post_id)
        
        except Exception as e:
            print(f"  ❌ Error scanning posts for summons: {e}")
    
# Clean up old user reply tracking (remove entries older than cooldown window)
    now = datetime.now(timezone.utc).timestamp()
    cutoff_seconds = SAME_USER_COOLDOWN_HOURS * 3600
    recent_user_replies = {
        user: data for user, data in recent_user_replies.items()
        if (now - data.get("first_reply_time", 0)) < cutoff_seconds
    }

    # Update state
    state["summon_responses"] = list(summon_responses)[-2000:]  # Keep last 2000
    state["recent_user_replies"] = recent_user_replies
    state["daily_replies"] = state.get("daily_replies", 0) + summons_handled
    
    return summons_handled, total_tokens, total_cost, state
