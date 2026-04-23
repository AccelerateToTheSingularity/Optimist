"""
Crosspost Handler for the Optimist Prime bot.
Automatically crossposts top AI-related posts from r/accelerate to r/ProAI.

Features:
- Fetches yesterday's top posts from source subreddit
- AI classification to filter only strictly AI-related content
- Duplicate detection (checks target sub + internal history)
- Title enhancement with optional excitement
- Enthusiastic comment in Optimist Prime voice
- Rate limiting with random time variation
- 5% random skip chance for human-like behavior
"""

import random
from datetime import datetime, date, timedelta

from config import (
    CROSSPOST_ENABLED,
    CROSSPOST_SOURCE_SUB,
    CROSSPOST_TARGET_SUB,
    CROSSPOST_MAX_PER_DAY,
    CROSSPOST_MIN_SCORE,
    CROSSPOST_MIN_HOURS_OLD,
    CROSSPOST_MAX_HOURS_OLD,
    CROSSPOST_SKIP_CHANCE,
    CROSSPOST_TIME_VARIATION_HOURS,
    CROSSPOST_LOOKBACK_DAYS,
)
from persona import ACCELERATE_PERSONA_PROMPT


def get_ai_classification_prompt(title: str, selftext: str) -> str:
    """Build prompt for classifying a post as AI-related or not."""
    content_snippet = selftext[:500] if selftext else "[Link post - no body text]"
    
    return f"""You are classifying Reddit posts for an AI-focused subreddit.

Classify as "YES" ONLY if the post is DIRECTLY about:
- Artificial Intelligence, Machine Learning, Deep Learning
- LLMs, GPT, Claude, Gemini, or other AI models
- AGI, ASI, or the Technological Singularity
- AI research, AI labs (OpenAI, Anthropic, DeepMind, Google AI, Meta AI, etc.)
- AI capabilities, benchmarks, or breakthroughs
- AI policy, regulation, or safety (if AI is the main focus)

Classify as "NO" if:
- AI is mentioned tangentially but isn't the main topic
- It's about robotics, automation, biotech, space, crypto WITHOUT AI being central
- It's a general tech/science post that doesn't center on AI
- It's a meme or shitpost (unless specifically about AI)
- It's about acceleration philosophy without specific AI focus

POST TITLE: {title}
POST CONTENT: {content_snippet}

Reply with ONLY "YES" or "NO"."""


def get_title_enhancement_prompt(title: str) -> str:
    """Build prompt for potentially improving a post title."""
    return f"""You are helping crosspost an AI-related post to r/ProAI, a community excited about AI progress and the Singularity.

ORIGINAL TITLE: "{title}"

Your task:
1. If the title is already great, return it EXACTLY unchanged
2. If it could be clearer or more engaging, improve it slightly (keep the same meaning)
3. If there's room (under 280 chars total), you MAY add brief excited commentary like:
   - "🔥 [title]"
   - "[title] - this is huge"
   - "[title] 👀"
   - "[title] - the future is here"
   
Guidelines:
- Keep the core meaning intact
- Don't sensationalize or mislead
- Don't exceed 290 characters total
- If the original is already perfect, return it exactly as-is
- Most titles should stay unchanged or have minimal tweaks

Return ONLY the final title, nothing else."""


def get_crosspost_comment_prompt(title: str, content_summary: str) -> str:
    """Build prompt for generating an enthusiastic comment on the crosspost."""
    return f"""{ACCELERATE_PERSONA_PROMPT}

You just crossposted an AI-related post to r/ProAI from r/accelerate.

POST TITLE: {title}
POST CONTENT SUMMARY: {content_summary}

Write a brief comment (1-3 sentences) reacting to this post like a regular excited community member would.

**CRITICAL - SOUND LIKE A REAL REDDITOR:**
Here are examples of how real r/accelerate users comment:
- "Welp. I guess the Singularity is on then. I mean holy shit."
- "This is massive, the cost/compute is scaling insanely. 2026 will be a crazy year."
- "God damn how do we speed this up even more?"
- "I'll wait for actual benchmarks, but for now, it's impressive, we're moving so fast it's unreal!!!"
- "10x reduction is insane."
- "Another nail in the coffin of the assumption that these models will get progressively more demanding."

**DO NOT:**
- Start with "Hey r/ProAI!" or any subreddit greeting - that's corporate/bot-like
- Use phrases like "Sharing this cool article" or "Exciting times" - too formal
- Sound like a press release or marketing copy
- Mention that you're crossposting or "sharing" anything

**DO:**
- React genuinely like you just saw something cool
- Use casual language, maybe some mild profanity if it fits
- Keep it short - sometimes just one punchy sentence is perfect
- Sound like a real person who's excited, not a community manager

Your comment:"""


def initialize_crosspost_state(state: dict) -> dict:
    """Ensure crosspost state structure exists."""
    if "crosspost" not in state:
        state["crosspost"] = {
            "history": [],
            "last_crosspost_date": None,
            "daily_crossposts": 0,
            "scheduled_date": None,
            "scheduled_hour": None,
            "skip_today": False,
        }
    return state


def get_todays_schedule(state: dict) -> tuple[int | None, bool]:
    """
    Determine today's crosspost schedule.
    
    Returns:
        Tuple of (scheduled_hour, should_skip)
        If should_skip is True, scheduled_hour will be None
    """
    state = initialize_crosspost_state(state)
    today = date.today().isoformat()
    crosspost_state = state["crosspost"]
    
    # If we already scheduled for today, return cached values
    if crosspost_state.get("scheduled_date") == today:
        if crosspost_state.get("skip_today"):
            return None, True
        return crosspost_state.get("scheduled_hour"), False
    
    # New day - reset daily counter and roll new schedule
    crosspost_state["daily_crossposts"] = 0
    crosspost_state["scheduled_date"] = today
    
    # 5% chance to skip today entirely
    if random.random() < CROSSPOST_SKIP_CHANCE:
        crosspost_state["skip_today"] = True
        crosspost_state["scheduled_hour"] = None
        print(f"  🎲 Random skip triggered (5% chance) - skipping crosspost today")
        return None, True
    
    # Pick random hour within configured range
    min_hour, max_hour = CROSSPOST_TIME_VARIATION_HOURS
    scheduled_hour = random.randint(min_hour, max_hour)
    crosspost_state["scheduled_hour"] = scheduled_hour
    crosspost_state["skip_today"] = False
    
    print(f"  ⏰ Today's crosspost scheduled for hour {scheduled_hour} UTC")
    return scheduled_hour, False


def is_time_to_crosspost(state: dict) -> bool:
    """Check if it's time to crosspost based on today's schedule."""
    state = initialize_crosspost_state(state)
    crosspost_state = state["crosspost"]
    
    # Check if we've already posted today
    today = date.today().isoformat()
    if crosspost_state.get("last_crosspost_date") == today:
        if crosspost_state.get("daily_crossposts", 0) >= CROSSPOST_MAX_PER_DAY:
            return False
    
    # Get today's schedule
    scheduled_hour, should_skip = get_todays_schedule(state)
    
    if should_skip:
        return False
    
    if scheduled_hour is None:
        return False
    
    # Check if current hour >= scheduled hour
    current_hour = datetime.utcnow().hour
    return current_hour >= scheduled_hour


def fetch_candidate_posts(source_subreddit) -> list:
    """
    Fetch yesterday's top posts from the source subreddit.
    
    Returns posts that are:
    - Between MIN_HOURS_OLD and MAX_HOURS_OLD
    - Have score >= MIN_SCORE
    - Sorted by score descending
    """
    candidates = []
    now = datetime.utcnow()
    
    # Fetch top posts from the last day or two
    for submission in source_subreddit.top(time_filter="day", limit=50):
        post_age_hours = (now - datetime.utcfromtimestamp(submission.created_utc)).total_seconds() / 3600
        
        # Check age constraints
        if post_age_hours < CROSSPOST_MIN_HOURS_OLD:
            continue
        if post_age_hours > CROSSPOST_MAX_HOURS_OLD:
            continue
        
        # Check score threshold
        if submission.score < CROSSPOST_MIN_SCORE:
            continue
        
        candidates.append(submission)
    
    # Sort by score descending (best first)
    candidates.sort(key=lambda x: x.score, reverse=True)
    
    return candidates


def get_existing_target_urls(target_subreddit, lookback_days: int = 2) -> set:
    """
    Get URLs of posts already in the target subreddit.
    Used to avoid duplicate crossposts.
    """
    existing_urls = set()
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    
    try:
        for submission in target_subreddit.new(limit=100):
            # Stop if we've gone past the lookback period
            if datetime.utcfromtimestamp(submission.created_utc) < cutoff:
                break
            
            # Track the URL (for crossposts, this is the original post URL)
            existing_urls.add(submission.url)
            
            # Also track permalink in case of direct reposts
            if hasattr(submission, 'crosspost_parent_list') and submission.crosspost_parent_list:
                for parent in submission.crosspost_parent_list:
                    existing_urls.add(f"https://reddit.com{parent.get('permalink', '')}")
    except Exception as e:
        print(f"  ⚠️ Error fetching existing posts from r/{target_subreddit.display_name}: {e}")
    
    return existing_urls


def is_already_crossposted(submission, existing_urls: set, history_ids: set) -> bool:
    """Check if a post has already been crossposted."""
    # Check against existing URLs in target subreddit
    post_url = f"https://reddit.com{submission.permalink}"
    if post_url in existing_urls or submission.url in existing_urls:
        return True
    
    # Check against our internal history
    if submission.id in history_ids:
        return True
    
    return False


def classify_post_as_ai_related(submission, gemini_model) -> tuple[bool, dict]:
    """
    Use AI to classify if a post is strictly AI-related.
    
    Returns:
        Tuple of (is_ai_related, token_info)
    """
    prompt = get_ai_classification_prompt(submission.title, submission.selftext or "")
    
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={"temperature": 0.1, "max_output_tokens": 10}
    )
    
    # Extract token info
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    result = response.text.strip().upper()
    is_ai_related = result == "YES"
    
    return is_ai_related, token_info


def enhance_title(original_title: str, gemini_model) -> tuple[str, dict]:
    """
    Potentially improve the title with slight enhancements.
    
    Returns:
        Tuple of (enhanced_title, token_info)
    """
    prompt = get_title_enhancement_prompt(original_title)
    
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={"temperature": 0.7, "max_output_tokens": 100}
    )
    
    # Extract token info
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    enhanced = response.text.strip()
    
    # Sanity check - if the AI returned something weird, use original
    if len(enhanced) < 5 or len(enhanced) > 300:
        enhanced = original_title
    
    return enhanced, token_info


def generate_crosspost_comment(title: str, content: str, gemini_model) -> tuple[str, dict]:
    """
    Generate an enthusiastic comment for the crosspost.
    
    Returns:
        Tuple of (comment_text, token_info)
    """
    # Create a brief content summary
    content_summary = content[:400] if content else "[Link post]"
    
    prompt = get_crosspost_comment_prompt(title, content_summary)
    
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={"temperature": 0.8, "max_output_tokens": 200}
    )
    
    # Extract token info
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    return response.text.strip(), token_info


def perform_crosspost(
    submission,
    target_subreddit,
    new_title: str,
    comment_text: str,
    dry_run: bool = False
) -> tuple[bool, str | None]:
    """
    Execute the crosspost and leave a comment.
    
    Returns:
        Tuple of (success, crosspost_url or error_message)
    """
    if dry_run:
        print(f"     [DRY RUN] Would crosspost: {new_title[:60]}...")
        print(f"     [DRY RUN] Would comment: {comment_text[:80]}...")
        return True, "[DRY RUN]"
    
    try:
        # Perform the crosspost
        crosspost = submission.crosspost(
            subreddit=target_subreddit,
            title=new_title,
            send_replies=True
        )
        
        # Leave an enthusiastic comment
        crosspost.reply(comment_text)
        
        return True, f"https://reddit.com{crosspost.permalink}"
    
    except Exception as e:
        error_msg = str(e)
        print(f"     ❌ Crosspost failed: {error_msg}")
        return False, error_msg


def check_and_crosspost(reddit, gemini_model, state: dict, dry_run: bool = False) -> tuple[int, int, float, dict]:
    """
    Main entry point: check if we should crosspost and do it.
    
    Returns:
        Tuple of (crossposts_made, total_tokens, total_cost, updated_state)
    """
    state = initialize_crosspost_state(state)
    total_tokens = 0
    total_cost = 0.0
    
    if not CROSSPOST_ENABLED:
        return 0, 0, 0.0, state
    
    print(f"\n🔄 Phase 7: Checking crosspost to r/{CROSSPOST_TARGET_SUB}...")
    
    # Check if it's time to crosspost
    if not is_time_to_crosspost(state):
        scheduled = state["crosspost"].get("scheduled_hour")
        if state["crosspost"].get("skip_today"):
            print(f"  ⏭️ Skipping today (random skip)")
        elif state["crosspost"].get("last_crosspost_date") == date.today().isoformat():
            print(f"  ✅ Already crossposted today")
        else:
            print(f"  ⏳ Not yet time (scheduled for hour {scheduled} UTC, current: {datetime.utcnow().hour})")
        return 0, 0, 0.0, state
    
    # Get subreddits
    source_sub = reddit.subreddit(CROSSPOST_SOURCE_SUB)
    target_sub = reddit.subreddit(CROSSPOST_TARGET_SUB)
    
    # Fetch candidate posts
    print(f"  📥 Fetching top posts from r/{CROSSPOST_SOURCE_SUB}...")
    candidates = fetch_candidate_posts(source_sub)
    print(f"     Found {len(candidates)} candidates (score >= {CROSSPOST_MIN_SCORE})")
    
    if not candidates:
        print(f"  ⚠️ No qualifying posts found")
        return 0, 0, 0.0, state
    
    # Get existing posts in target to avoid duplicates
    print(f"  🔍 Checking for existing posts in r/{CROSSPOST_TARGET_SUB}...")
    existing_urls = get_existing_target_urls(target_sub, CROSSPOST_LOOKBACK_DAYS)
    history = state["crosspost"].get("history", [])
    history_ids = {entry.get("source_post_id") for entry in history}
    
    # Find the best AI-related post
    selected_post = None
    
    for submission in candidates:
        # Skip if already crossposted
        if is_already_crossposted(submission, existing_urls, history_ids):
            print(f"     ⏭️ Skipping {submission.id} (already crossposted)")
            continue
        
        # Classify as AI-related
        print(f"     🤖 Classifying: {submission.title[:50]}...")
        is_ai, token_info = classify_post_as_ai_related(submission, gemini_model)
        total_tokens += token_info["total_tokens"]
        total_cost += token_info["cost"]
        
        if is_ai:
            print(f"     ✅ AI-related! Score: {submission.score}")
            selected_post = submission
            break
        else:
            print(f"     ❌ Not AI-related, skipping")
    
    if not selected_post:
        print(f"  ⚠️ No AI-related posts found to crosspost")
        return 0, total_tokens, total_cost, state
    
    # Enhance the title
    print(f"  ✏️ Enhancing title...")
    enhanced_title, token_info = enhance_title(selected_post.title, gemini_model)
    total_tokens += token_info["total_tokens"]
    total_cost += token_info["cost"]
    
    if enhanced_title != selected_post.title:
        print(f"     Original: {selected_post.title[:60]}...")
        print(f"     Enhanced: {enhanced_title[:60]}...")
    else:
        print(f"     Title unchanged: {enhanced_title[:60]}...")
    
    # Generate enthusiastic comment
    print(f"  💬 Generating comment...")
    comment_text, token_info = generate_crosspost_comment(
        selected_post.title,
        selected_post.selftext or "",
        gemini_model
    )
    total_tokens += token_info["total_tokens"]
    total_cost += token_info["cost"]
    print(f"     Comment: {comment_text[:80]}...")
    
    # Perform the crosspost
    print(f"  📤 Crossposting to r/{CROSSPOST_TARGET_SUB}...")
    success, result = perform_crosspost(
        selected_post,
        target_sub,
        enhanced_title,
        comment_text,
        dry_run
    )
    
    if success:
        # Update state
        today = date.today().isoformat()
        state["crosspost"]["last_crosspost_date"] = today
        state["crosspost"]["daily_crossposts"] = state["crosspost"].get("daily_crossposts", 0) + 1
        
        # Add to history
        state["crosspost"]["history"].append({
            "source_post_id": selected_post.id,
            "source_url": f"https://reddit.com{selected_post.permalink}",
            "target_url": result,
            "original_title": selected_post.title,
            "enhanced_title": enhanced_title,
            "timestamp": datetime.utcnow().isoformat(),
            "score_at_crosspost": selected_post.score,
        })
        
        # Keep history manageable (last 100 crossposts)
        state["crosspost"]["history"] = state["crosspost"]["history"][-100:]
        
        # Update stats
        if "total_crossposts" not in state["stats"]:
            state["stats"]["total_crossposts"] = 0
        state["stats"]["total_crossposts"] += 1
        
        print(f"  ✅ Successfully crossposted!")
        if not dry_run:
            print(f"     URL: {result}")
        
        return 1, total_tokens, total_cost, state
    else:
        print(f"  ❌ Crosspost failed: {result}")
        return 0, total_tokens, total_cost, state
