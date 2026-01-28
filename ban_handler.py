"""
Auto-ban handler for users with excessive negative karma.
Monitors automod removals and bans repeat offenders.
"""

from datetime import datetime, timedelta


def check_and_ban_negative_karma_users(
    subreddit,
    state: dict,
    dry_run: bool = False,
    lookback_hours: int = 1
) -> tuple[int, dict]:
    """
    Check mod log for automod removals due to negative karma and ban those users.
    
    Args:
        subreddit: PRAW Subreddit object
        state: Current bot state dict
        dry_run: If True, don't actually ban users
        lookback_hours: How far back to check the mod log
    
    Returns:
        Tuple of (users_banned, updated_state)
    """
    users_banned = 0
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    
    # Track who we've already processed to avoid duplicate attempts
    already_banned = set(state.get("banned_users", []))
    users_to_ban = set()
    
    print(f"  🔍 Scanning mod log for negative karma removals...")
    
    try:
        # Check BOTH post and comment removals
        for action in ["removelink", "removecomment"]:
            for log in subreddit.mod.log(action=action, limit=100):
                # Skip old entries
                log_time = datetime.utcfromtimestamp(log.created_utc)
                if log_time < cutoff:
                    break
                
                # Match automod rule #5's action_reason EXACTLY
                if log.details == "User has negative local reputation":
                    target = log.target_author
                    if target and target != "[deleted]" and target not in already_banned:
                        users_to_ban.add(target)
    
    except Exception as e:
        print(f"  ❌ Error reading mod log: {e}")
        return 0, state
    
    if not users_to_ban:
        print(f"  ✅ No users to ban")
        return 0, state
    
    print(f"  📋 Found {len(users_to_ban)} user(s) to ban: {', '.join(users_to_ban)}")
    
    # Fetch ban list once to avoid N+1 API calls
    current_banned_users = set()
    if not dry_run:
        try:
            print("  🔍 Fetching current ban list...")
            for banned_user in subreddit.banned(limit=None):
                if hasattr(banned_user, 'name') and banned_user.name:
                    current_banned_users.add(banned_user.name.lower())
        except Exception as e:
            print(f"  ⚠️ Could not fetch ban list: {e}")

    # Ban collected users
    for username in users_to_ban:
        if dry_run:
            print(f"     [DRY RUN] Would ban u/{username}")
            already_banned.add(username)
            users_banned += 1
            continue
        
        try:
            # Check if already banned (avoid errors)
            if username.lower() in current_banned_users:
                print(f"     ⏭️ u/{username} already banned, skipping")
                already_banned.add(username)
                continue
            
            # Perform the ban
            subreddit.banned.add(
                username,
                ban_reason="Auto-ban: Excessive negative karma (< -80)",
                ban_message="You have been banned from r/accelerate due to excessive negative reputation. This action was taken automatically."
            )
            print(f"     ✅ Banned u/{username}")
            already_banned.add(username)
            users_banned += 1
            
        except Exception as e:
            print(f"     ❌ Failed to ban u/{username}: {e}")
    
    # Update state - keep last 500 banned users to avoid reprocessing
    state["banned_users"] = list(already_banned)[-500:]
    state["stats"]["total_users_banned"] = state["stats"].get("total_users_banned", 0) + users_banned
    
    return users_banned, state
