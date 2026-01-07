"""
Summon detection and response for the Optimist Prime bot.
Handles responding when users explicitly summon the bot anywhere in r/accelerate.
"""

import re
from datetime import datetime

from config import (
    SUBREDDIT,
    MAX_REPLIES_PER_RUN,
    MAX_AGE_HOURS,
    SUMMON_PATTERNS,
    HOSTILE_PATTERNS,
    BOT_INDICATORS,
    SAME_USER_COOLDOWN_HOURS,
    SAME_USER_REPLIES_BEFORE_COOLDOWN,
    MOD_CACHE_REFRESH_DAYS,
)
from persona import generate_conversational_response, generate_post_summon_response


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


def is_summon(text: str) -> bool:
    """Check if text contains a summon phrase for the bot."""
    text_lower = text.lower()
    for pattern in SUMMON_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


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
        return True
    
    name_lower = author_name.lower()
    for pattern in BOT_INDICATORS:
        if re.search(pattern.lower(), name_lower):
            return True
    return False


def is_too_old(created_utc: float) -> bool:
    """Check if a comment/post is older than MAX_AGE_HOURS."""
    age_seconds = datetime.utcnow().timestamp() - created_utc
    age_hours = age_seconds / 3600
    return age_hours > MAX_AGE_HOURS


def check_user_cooldown(author_name: str | None, recent_replies: dict) -> bool:
    """Check if we've recently replied to this user too many times."""
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


def check_for_summons(
    subreddit,
    gemini_model,
    state: dict,
    bot_username: str,
    dry_run: bool = False
) -> tuple[int, int, float, dict]:
    """
    Scan recent comments and posts for summon phrases and respond.
    
    Args:
        subreddit: PRAW Subreddit object
        gemini_model: Initialized Gemini model
        state: Current bot state dict
        bot_username: The bot's Reddit username
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
    
    print(f"  🔔 Scanning for bot summons in r/{SUBREDDIT}...")
    
    # Check comments
    try:
        comments = list(subreddit.comments(limit=100))
        
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
            
            # Skip deleted
            if not comment.body or comment.body == '[deleted]':
                continue
            
            # Check if this is a summon
            if not is_summon(comment.body):
                continue
            
            author_name = comment.author.name if comment.author else None
            
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
                
                # Generate response
                response_text, token_info = generate_conversational_response(
                    comment,
                    submission,
                    gemini_model,
                    is_summon=True
                )
                
                # Post the reply
                comment.reply(response_text)
                
                print(f"       ✅ Responded to summon ({len(response_text.split())} words, {token_info['total_tokens']} tokens)")
                
                # Update tracking
                summon_responses.add(comment.id)
                # Track reply count per user
                if author_name not in recent_user_replies:
                    recent_user_replies[author_name] = {"count": 1, "first_reply_time": datetime.utcnow().timestamp()}
                else:
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
                    post.reply(response_text)
                    
                    print(f"       ✅ Responded to post summon ({len(response_text.split())} words, {token_info['total_tokens']} tokens)")
                    
                    # Update tracking
                    summon_responses.add(post_id)
                    # Track reply count per user
                    if author_name not in recent_user_replies:
                        recent_user_replies[author_name] = {"count": 1, "first_reply_time": datetime.utcnow().timestamp()}
                    else:
                        recent_user_replies[author_name]["count"] = recent_user_replies[author_name].get("count", 0) + 1
                    summons_handled += 1
                    total_tokens += token_info["total_tokens"]
                    total_cost += token_info["cost"]
                    
                except Exception as e:
                    print(f"       ❌ Error responding to post summon: {e}")
                    summon_responses.add(post_id)
        
        except Exception as e:
            print(f"  ❌ Error scanning posts for summons: {e}")
    
    # Update state
    state["summon_responses"] = list(summon_responses)[-2000:]  # Keep last 2000
    state["recent_user_replies"] = recent_user_replies
    state["daily_replies"] = state.get("daily_replies", 0) + summons_handled
    
    return summons_handled, total_tokens, total_cost, state
