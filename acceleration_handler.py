"""
Acceleration Factor handler for the Optimist Prime bot.
Manages opt-in flair showing user's karma from pro-AI subreddits.
"""

import re
from datetime import datetime

from config import (
    ACCELERATION_ENABLED,
    ACCELERATION_PRO_AI_SUBS,
    ACCELERATION_SCAN_LIMIT,
    ACCELERATION_REFRESH_DAYS,
    ACCELERATION_BACKGROUND_REFRESH_DAYS,
    ACCELERATION_TIERS,
    ACCELERATION_ZERO_TIER,
    ACCELERATION_MODMAIL_THRESHOLD,
    ACCELERATION_AUTOBAN_ENABLED,
    ACCELERATION_AUTOBAN_THRESHOLD,
)


def calculate_pro_ai_karma(redditor, reddit) -> int:
    """
    Calculate total karma from pro-AI subreddits.
    
    Args:
        redditor: PRAW Redditor object
        reddit: PRAW Reddit instance (for accessing subreddits)
    
    Returns:
        Net karma score from pro-AI subreddits
    """
    total_karma = 0
    items_scanned = 0
    pro_ai_subs_lower = {sub.lower() for sub in ACCELERATION_PRO_AI_SUBS}
    
    try:
        # Scan comments
        for comment in redditor.comments.new(limit=ACCELERATION_SCAN_LIMIT):
            if items_scanned >= ACCELERATION_SCAN_LIMIT:
                break
            
            sub_name = comment.subreddit.display_name.lower()
            if sub_name in pro_ai_subs_lower:
                total_karma += comment.score
            items_scanned += 1
        
        # Scan submissions (posts)
        items_scanned = 0
        for submission in redditor.submissions.new(limit=ACCELERATION_SCAN_LIMIT):
            if items_scanned >= ACCELERATION_SCAN_LIMIT:
                break
            
            sub_name = submission.subreddit.display_name.lower()
            if sub_name in pro_ai_subs_lower:
                total_karma += submission.score
            items_scanned += 1
    
    except Exception as e:
        print(f"    ⚠️ Error scanning karma for u/{redditor.name}: {e}")
        return 0
    
    return total_karma


def get_acceleration_tier(score: int, high_score: int) -> str:
    """
    Get tier name based on score relative to high score.
    
    Args:
        score: User's pro-AI karma score
        high_score: Current highest score in the system
    
    Returns:
        Tier name string
    """
    if score <= 0:
        return ACCELERATION_ZERO_TIER
    
    if high_score <= 0:
        # No valid high score yet, default to lowest positive tier
        return ACCELERATION_TIERS[-1][1]  # "Crawling"
    
    percentage = score / high_score
    
    for threshold, tier_name in ACCELERATION_TIERS:
        if percentage >= threshold:
            return tier_name
    
    # Fallback (shouldn't happen but safety)
    return ACCELERATION_TIERS[-1][1]


def update_user_flair(subreddit, username: str, tier: str | None, remove: bool = False) -> bool:
    """
    Update user's flair to include/update/remove Acceleration tier.
    
    Args:
        subreddit: PRAW Subreddit object
        username: Reddit username
        tier: Tier name to set, or None if removing
        remove: If True, remove acceleration flair entirely
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current flair
        current_flair = None
        for flair in subreddit.flair(redditor=username):
            current_flair = flair.get("flair_text", "") or ""
            break
        
        if current_flair is None:
            current_flair = ""
        
        # Pattern to match existing acceleration flair
        accel_pattern = r"\s*\|\s*Acceleration:\s*\S+|\s*Acceleration:\s*\S+"
        
        if remove:
            # Remove acceleration portion
            new_flair = re.sub(accel_pattern, "", current_flair).strip()
            # Clean up any leading/trailing pipes
            new_flair = re.sub(r"^\s*\|\s*", "", new_flair)
            new_flair = re.sub(r"\s*\|\s*$", "", new_flair)
        else:
            accel_text = f"Acceleration: {tier}"
            
            if re.search(r"Acceleration:\s*\S+", current_flair):
                # Update existing acceleration flair
                new_flair = re.sub(r"Acceleration:\s*\S+", accel_text, current_flair)
            elif current_flair.strip():
                # Append to existing flair
                new_flair = f"{current_flair.strip()} | {accel_text}"
            else:
                # No existing flair
                new_flair = accel_text
        
        # Set the new flair
        subreddit.flair.set(username, text=new_flair if new_flair else None)
        return True
    
    except Exception as e:
        print(f"    ❌ Error updating flair for u/{username}: {e}")
        return False


def alert_mods_negative_karma(subreddit, username: str, score: int) -> bool:
    """
    Send modmail alerting mods about a user with negative pro-AI karma.
    
    Args:
        subreddit: PRAW Subreddit object
        username: Reddit username
        score: Their negative karma score
    
    Returns:
        True if successful, False otherwise
    """
    try:
        subject = f"⚠️ Negative Acceleration Alert: u/{username}"
        message = (
            f"User **u/{username}** has **{score}** net karma across pro-AI subreddits.\n\n"
            f"**Subreddits scanned:** {', '.join(ACCELERATION_PRO_AI_SUBS)}\n\n"
            f"This user may be a bad actor. Consider reviewing their activity.\n\n"
            f"---\n*Automated alert from Optimist Prime*"
        )
        
        subreddit.message(subject, message)
        print(f"    📧 Sent modmail alert for u/{username} (score: {score})")
        return True
    
    except Exception as e:
        print(f"    ❌ Error sending modmail for u/{username}: {e}")
        return False


def classify_acceleration_intent(comment_body: str, gemini_model) -> dict | None:
    """
    Use Gemini to classify if a comment is requesting acceleration flair action.
    
    Args:
        comment_body: The comment text
        gemini_model: Initialized Gemini model
    
    Returns:
        Dict with 'action' ('on', 'off', 'check', None) or None if not acceleration-related
    """
    prompt = f"""Analyze this Reddit comment and determine if the user is asking about the "Acceleration" flair feature.

The Acceleration feature shows a user's karma from pro-AI subreddits as a flair.

Comment: "{comment_body}"

Respond with ONLY one of these exact words:
- ON - if user wants to enable/turn on the acceleration flair
- OFF - if user wants to disable/turn off the acceleration flair  
- CHECK - if user wants to see their score but not change anything
- NONE - if the comment is NOT about the acceleration flair feature

Response:"""

    try:
        response = gemini_model.generate_content(prompt)
        result = response.text.strip().upper()
        
        if result == "ON":
            return {"action": "on"}
        elif result == "OFF":
            return {"action": "off"}
        elif result == "CHECK":
            return {"action": "check"}
        else:
            return None
    
    except Exception as e:
        print(f"    ⚠️ Error classifying acceleration intent: {e}")
        return None


def handle_acceleration_command(
    comment,
    subreddit,
    reddit,
    gemini_model,
    state: dict,
    dry_run: bool = False
) -> tuple[str | None, dict]:
    """
    Handle an acceleration flair command from a user.
    
    Args:
        comment: PRAW Comment object
        subreddit: PRAW Subreddit object
        reddit: PRAW Reddit instance
        gemini_model: Initialized Gemini model
        state: Current bot state dict
        dry_run: If True, don't actually modify flairs
    
    Returns:
        Tuple of (response_text or None, updated_state)
    """
    if not ACCELERATION_ENABLED:
        return None, state
    
    author_name = comment.author.name if comment.author else None
    if not author_name:
        return None, state
    
    # Classify intent using Gemini
    intent = classify_acceleration_intent(comment.body, gemini_model)
    if not intent:
        return None, state
    
    action = intent["action"]
    
    # Initialize acceleration state if needed
    if "acceleration" not in state:
        state["acceleration"] = {
            "high_score": 100,  # Start with reasonable default
            "opted_in_users": {},
            "alerted_users": [],
            "scanned_users": {}  # For background scanning non-opted-in
        }
    
    accel_state = state["acceleration"]
    user_data = accel_state["opted_in_users"].get(author_name, {})
    
    if action == "off":
        # Disable acceleration flair
        if author_name in accel_state["opted_in_users"]:
            del accel_state["opted_in_users"][author_name]
        
        if not dry_run:
            update_user_flair(subreddit, author_name, None, remove=True)
        
        response = (
            f"Done! I've removed your Acceleration flair. "
            f"You can turn it back on anytime by asking me. 🚀"
        )
        return response, state
    
    elif action in ("on", "check"):
        # Calculate their karma
        try:
            redditor = reddit.redditor(author_name)
            score = calculate_pro_ai_karma(redditor, reddit)
        except Exception as e:
            print(f"    ❌ Error getting redditor u/{author_name}: {e}")
            return "Sorry, I couldn't calculate your score right now. Please try again later!", state
        
        # Update high score if needed
        if score > accel_state.get("high_score", 0):
            accel_state["high_score"] = score
        
        tier = get_acceleration_tier(score, accel_state["high_score"])
        
        if action == "on":
            # Enable and set flair
            now = datetime.utcnow().timestamp()
            accel_state["opted_in_users"][author_name] = {
                "enabled": True,
                "last_calculated": now,
                "score": score,
                "tier": tier
            }
            
            if not dry_run:
                update_user_flair(subreddit, author_name, tier)
            
            response = (
                f"Your Acceleration flair is now active! 🚀\n\n"
                f"**Score:** {score} karma from pro-AI subs\n"
                f"**Tier:** {tier}\n\n"
                f"Your flair will update weekly. To turn it off, just ask me!"
            )
        else:
            # Just checking, don't modify flair
            response = (
                f"Here's your Acceleration status:\n\n"
                f"**Score:** {score} karma from pro-AI subs\n"
                f"**Tier:** {tier}\n\n"
                f"{'Your flair is active!' if author_name in accel_state['opted_in_users'] else 'Your flair is not active. Ask me to turn it on!'}"
            )
        
        # Check for negative karma alert
        if score < ACCELERATION_MODMAIL_THRESHOLD:
            if author_name not in accel_state.get("alerted_users", []):
                if not dry_run:
                    alert_mods_negative_karma(subreddit, author_name, score)
                accel_state.setdefault("alerted_users", []).append(author_name)
        
        return response, state
    
    return None, state


def refresh_opted_in_users(
    subreddit,
    reddit,
    state: dict,
    dry_run: bool = False
) -> tuple[int, dict]:
    """
    Refresh acceleration scores for opted-in users (weekly job).
    
    Args:
        subreddit: PRAW Subreddit object
        reddit: PRAW Reddit instance
        state: Current bot state dict
        dry_run: If True, don't actually modify flairs
    
    Returns:
        Tuple of (users_updated, updated_state)
    """
    if not ACCELERATION_ENABLED:
        return 0, state
    
    accel_state = state.get("acceleration", {})
    opted_in = accel_state.get("opted_in_users", {})
    
    if not opted_in:
        return 0, state
    
    now = datetime.utcnow().timestamp()
    refresh_threshold = ACCELERATION_REFRESH_DAYS * 24 * 3600
    users_updated = 0
    
    print(f"  🔄 Refreshing acceleration scores for {len(opted_in)} opted-in users...")
    
    for username, user_data in list(opted_in.items()):
        last_calc = user_data.get("last_calculated", 0)
        
        if (now - last_calc) < refresh_threshold:
            continue  # Not due for refresh yet
        
        try:
            redditor = reddit.redditor(username)
            score = calculate_pro_ai_karma(redditor, reddit)
            
            # Update high score if needed
            if score > accel_state.get("high_score", 0):
                accel_state["high_score"] = score
            
            tier = get_acceleration_tier(score, accel_state["high_score"])
            
            # Update user data
            opted_in[username] = {
                "enabled": True,
                "last_calculated": now,
                "score": score,
                "tier": tier
            }
            
            if not dry_run:
                update_user_flair(subreddit, username, tier)
            
            print(f"    ✅ Refreshed u/{username}: {score} → {tier}")
            users_updated += 1
            
        except Exception as e:
            print(f"    ⚠️ Error refreshing u/{username}: {e}")
    
    state["acceleration"] = accel_state
    return users_updated, state


def background_scan_commenter(
    username: str,
    subreddit,
    reddit,
    state: dict,
    dry_run: bool = False
) -> dict:
    """
    Background scan a commenter for negative karma (doesn't update their flair).
    
    Args:
        username: Reddit username to scan
        subreddit: PRAW Subreddit object
        reddit: PRAW Reddit instance
        state: Current bot state dict
        dry_run: If True, don't send modmail
    
    Returns:
        Updated state
    """
    if not ACCELERATION_ENABLED:
        return state
    
    # Initialize acceleration state if needed
    if "acceleration" not in state:
        state["acceleration"] = {
            "high_score": 100,
            "opted_in_users": {},
            "alerted_users": [],
            "scanned_users": {}
        }
    
    accel_state = state["acceleration"]
    
    # Skip if already opted-in (they get weekly refreshes)
    if username in accel_state.get("opted_in_users", {}):
        return state
    
    # Check if due for background scan
    scanned = accel_state.setdefault("scanned_users", {})
    now = datetime.utcnow().timestamp()
    refresh_threshold = ACCELERATION_BACKGROUND_REFRESH_DAYS * 24 * 3600
    
    last_scan = scanned.get(username, {}).get("last_scanned", 0)
    if (now - last_scan) < refresh_threshold:
        return state  # Not due for scan yet
    
    try:
        redditor = reddit.redditor(username)
        score = calculate_pro_ai_karma(redditor, reddit)
        
        # Record the scan
        scanned[username] = {
            "last_scanned": now,
            "score": score
        }
        
        # Check for negative karma alert
        if score < ACCELERATION_MODMAIL_THRESHOLD:
            if username not in accel_state.get("alerted_users", []):
                if not dry_run:
                    alert_mods_negative_karma(subreddit, username, score)
                accel_state.setdefault("alerted_users", []).append(username)
                print(f"    ⚠️ Background scan: u/{username} has {score} pro-AI karma")
        
        # Update high score if positive
        if score > accel_state.get("high_score", 0):
            accel_state["high_score"] = score
        
    except Exception as e:
        print(f"    ⚠️ Error background scanning u/{username}: {e}")
    
    # Keep alerted_users list manageable
    accel_state["alerted_users"] = accel_state.get("alerted_users", [])[-500:]
    # Keep scanned_users manageable (last 2000)
    if len(scanned) > 2000:
        sorted_users = sorted(scanned.items(), key=lambda x: x[1].get("last_scanned", 0))
        scanned = dict(sorted_users[-2000:])
        accel_state["scanned_users"] = scanned
    
    state["acceleration"] = accel_state
    return state
