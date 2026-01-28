"""
Reddit Bot Runner for GitHub Actions.
Runs a single check cycle for r/accelerate:
- Generates TLDRs for long posts and comments
- Monitors and responds to replies
- Detects and responds to summons
- Auto-bans users with excessive negative karma
- Crossposts top AI posts to r/ProAI
"""

import os
import sys
import json
import argparse
from datetime import datetime, date

import praw
import google.generativeai as genai

# Import configuration from centralized config
from config import (
    SUBREDDIT,
    POST_WORD_THRESHOLD,
    COMMENT_WORD_THRESHOLD,
    MAX_TLDR_PER_RUN,
    MAX_TLDR_PER_DAY,
    MAX_AGE_HOURS,
    COMMENT_MILESTONES,
    MAX_REPLIES_PER_DAY,
    CROSSPOST_ENABLED,
    ACCELERATION_ENABLED,
)

# Import handlers for reply, summon, ban, crosspost, and acceleration features
from reply_handler import check_inbox_replies
from summon_handler import check_for_summons
from ban_handler import check_and_ban_negative_karma_users
from crosspost_handler import check_and_crosspost
from acceleration_handler import refresh_opted_in_users, process_scan_queue


def load_state(state_file: str = "data/bot_state.json") -> dict:
    """Load bot state from file."""
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    return {
        "last_check": None,
        "processed_posts": [],
        "processed_comments": [],  # Comment IDs already TLDRed
        "comment_summaries": {},  # {post_id: last_milestone}
        "daily_tldrs": 0,
        "daily_reset_date": None,
        # New fields for reply/summon features
        "replied_to_comments": [],  # IDs of comments we've replied to conversationally
        "summon_responses": [],  # IDs of summon comments/posts we've responded to
        "recent_user_replies": {},  # {username: last_reply_timestamp} for cooldowns
        "daily_replies": 0,  # Daily count for conversational replies
        "stats": {
            "total_posts_processed": 0,
            "total_tldrs_generated": 0,
            "total_tokens_used": 0,
            "total_cost": 0.0,
            "total_replies_sent": 0,
            "total_summons_handled": 0,
            "total_users_banned": 0
        },
        "banned_users": []  # Track users we've auto-banned
    }


def save_state(state: dict, state_file: str = "data/bot_state.json"):
    """Save state to file."""
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def update_stats(stats_file: str = "data/stats.json", tldrs_generated: int = 0, tokens: int = 0, cost: float = 0.0):
    """Update cumulative stats file."""
    stats = {"total_tldrs": 0, "total_tokens": 0, "total_cost": 0.0, "runs": 0, "last_run": None}
    
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r') as f:
                stats = json.load(f)
        except:
            pass
    
    stats["total_tldrs"] = stats.get("total_tldrs", 0) + tldrs_generated
    stats["total_tokens"] = stats.get("total_tokens", 0) + tokens
    stats["total_cost"] = stats.get("total_cost", 0.0) + cost
    stats["runs"] = stats.get("runs", 0) + 1
    stats["last_run"] = datetime.utcnow().isoformat()
    
    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)


def count_words(text: str) -> int:
    """Count words in text, handling markdown."""
    import re
    if not text:
        return 0
    # Remove markdown
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
    text = re.sub(r'`([^`]+)`', r'\1', text)        # Code
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Links
    return len(text.split())


def calculate_max_tldr_words(content_word_count: int) -> int:
    """Calculate target TLDR length (17% of content, clamped 40-400)."""
    scaled = int(content_word_count * 0.17)
    return max(40, min(400, scaled))


def get_tldr_prompt(max_words: int = 75) -> str:
    """Get the TLDR generation prompt for r/accelerate posts."""
    return f"""You are a summarization assistant for r/accelerate, a community focused on technological acceleration, the Technological Singularity, and AI progress.

Your task is to create a concise, accurate TLDR (Too Long; Didn't Read) summary.

**CRITICAL REQUIREMENTS:**
- Target approximately {max_words} words, BUT THIS IS A SOFT GUIDELINE - NOT A HARD LIMIT
- **COMPLETENESS IS MORE IMPORTANT THAN WORD COUNT** - it's better to exceed the word target than to cut off mid-sentence or omit key points
- NEVER cut off mid-sentence or mid-thought under any circumstances
- If you need 20-50 extra words to finish properly, USE THEM
- Cover all major points from the content proportionally to its length
- For long posts (1000+ words), provide a comprehensive multi-sentence summary

**SUMMARIZATION GUIDELINES:**
1. **Complete Thoughts First**: Finish every sentence and thought completely - this overrides word limits
2. **Cover All Key Points**: For long posts, include all major arguments, not just the first one
3. **Natural Ending**: End on a complete thought with proper punctuation, never mid-word or mid-sentence
4. **Maintain Perspective**: Preserve the author's viewpoint and accelerationist context
5. **Technical Accuracy**: Preserve important technical details and terminology

**FORMAT:**
Provide only the summary content - no headers, labels, or metadata. Just the summary text, ready to post directly. Your summary MUST end with a complete sentence and proper punctuation."""


def get_comment_summary_prompt(max_words: int = 100) -> str:
    """Get the comment summarization prompt."""
    return f"""You are summarizing community discussion from r/accelerate, a subreddit about technological acceleration and AI progress.

Your task is to synthesize the main viewpoints, key insights, and any notable debates from the comments.

**CRITICAL REQUIREMENTS:**
- Target approximately {max_words} words, BUT COMPLETENESS IS MORE IMPORTANT
- Focus on substance, not meta-commentary about the discussion itself
- Capture diverse perspectives if they exist
- Highlight any consensus or interesting disagreements

**FORMAT:**
Provide only the summary content - no headers, labels, or metadata. Just the summary text.
Your summary MUST end with a complete sentence and proper punctuation."""


def generate_tldr(content: str, title: str, gemini_model) -> tuple[str, dict]:
    """Generate TLDR using Gemini API."""
    word_count = count_words(content)
    max_words = calculate_max_tldr_words(word_count)
    
    prompt = get_tldr_prompt(max_words)
    full_content = f"Title: {title}\n\nContent: {content}"
    
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt + "\n\n" + full_content]}],
        generation_config={"temperature": 0.3, "max_output_tokens": 1024}
    )
    
    # Extract token counts
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    
    # Estimate cost (Gemini 2.0 Flash pricing)
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    return response.text.strip(), token_info


def get_parent_chain(comment, comment_lookup=None, max_parents: int = 6) -> list:
    """Get parent comments up to max_parents levels."""
    parents = []
    current = comment
    while len(parents) < max_parents:
        try:
            # Use lookup if available to avoid API call
            parent = None
            if comment_lookup and hasattr(current, 'parent_id'):
                parent_id = current.parent_id
                if parent_id.startswith('t3_'):
                    break  # Parent is submission

                # Extract ID part (t1_xyz -> xyz)
                pid = parent_id.split('_')[1] if '_' in parent_id else parent_id

                if pid in comment_lookup:
                    parent = comment_lookup[pid]

            # Fallback to API if not found in lookup
            if parent is None:
                parent = current.parent()

            # Check if parent is a comment (not the submission)
            if hasattr(parent, 'body') and parent.body and parent.body != '[deleted]':
                parents.append(parent)
                current = parent
            else:
                break
        except:
            break
    return list(reversed(parents))  # Oldest first


def generate_comment_tldr(comment, submission, gemini_model, comment_lookup=None) -> tuple[str, dict]:
    """Generate TLDR for a comment with context from parents and submission."""
    word_count = count_words(comment.body)
    max_words = calculate_max_tldr_words(word_count)
    
    # Build context
    context_parts = []
    
    # Add submission context (title + first 600 chars of body if exists)
    context_parts.append(f"**Original Post Title:** {submission.title}")
    if submission.selftext:
        snippet = submission.selftext[:600] + "..." if len(submission.selftext) > 600 else submission.selftext
        context_parts.append(f"**Original Post (snippet):** {snippet}")
    
    # Add parent comments
    parents = get_parent_chain(comment, comment_lookup)
    if parents:
        context_parts.append("**Parent Comments (for context):**")
        for i, parent in enumerate(parents, 1):
            parent_snippet = parent.body[:400] + "..." if len(parent.body) > 400 else parent.body
            context_parts.append(f"  [{i}] {parent_snippet}")
    
    context = "\n".join(context_parts)
    
    prompt = f"""You are a summarization assistant for r/accelerate, a community focused on technological acceleration and AI progress.

Your task is to create a concise TLDR of the TARGET COMMENT below. The context (original post and parent comments) is provided ONLY to help you understand what the comment is replying to - do NOT summarize the context, only use it for awareness.

**CRITICAL REQUIREMENTS:**
- Target approximately {max_words} words
- Summarize ONLY the target comment - the context is just for your awareness
- Use the context to understand references, pronouns, and what the commenter is responding to
- Complete all sentences properly

**FORMAT:**
Provide only the summary text - no headers or labels.

---
CONTEXT:
{context}

---
TARGET COMMENT TO SUMMARIZE:
{comment.body}"""

    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={"temperature": 0.3, "max_output_tokens": 1024}
    )
    
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    return response.text.strip(), token_info


def generate_comment_summary(comments: list, gemini_model) -> tuple[str, dict]:
    """Generate summary of comments using Gemini API."""
    # Build comment text
    comment_texts = []
    for i, comment in enumerate(comments[:30], 1):  # Limit to 30 comments for token efficiency
        if hasattr(comment, 'body') and comment.body and comment.body != '[deleted]':
            comment_texts.append(f"Comment {i}: {comment.body[:500]}")  # Truncate long comments
    
    if not comment_texts:
        return None, {"total_tokens": 0, "cost": 0.0}
    
    combined_content = "\n\n".join(comment_texts)
    word_count = count_words(combined_content)
    max_words = calculate_max_tldr_words(word_count)
    
    prompt = get_comment_summary_prompt(max_words)
    
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt + "\n\nComments to summarize:\n\n" + combined_content]}],
        generation_config={"temperature": 0.3, "max_output_tokens": 1024}
    )
    
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    return response.text.strip(), token_info


def find_bot_comment(submission, username: str):
    """Find our existing distinguished comment on a post, if any."""
    submission.comments.replace_more(limit=0)
    for comment in submission.comments:
        if hasattr(comment, 'author') and comment.author:
            if comment.author.name == username and comment.distinguished:
                return comment
    return None


def get_next_milestone(comment_count: int, last_milestone: int = 0) -> int:
    """Get the next milestone threshold that should be processed."""
    for milestone in COMMENT_MILESTONES:
        if comment_count >= milestone and milestone > last_milestone:
            # Find the highest milestone we've crossed
            pass
    
    # Find highest milestone we've crossed
    current_milestone = 0
    for milestone in COMMENT_MILESTONES:
        if comment_count >= milestone:
            current_milestone = milestone
    
    # Return it only if it's higher than what we've processed
    if current_milestone > last_milestone:
        return current_milestone
    return 0


def check_daily_limit(state: dict) -> tuple[bool, dict]:
    """Check and reset daily limit if needed. Returns (can_proceed, updated_state)."""
    today = date.today().isoformat()
    
    # Reset counter if new day
    if state.get("daily_reset_date") != today:
        state["daily_tldrs"] = 0
        state["daily_replies"] = 0  # Also reset reply counter
        state["recent_user_replies"] = {}  # Clear user cooldowns on new day
        state["daily_reset_date"] = today
        print(f"📅 New day detected, reset daily counters")
    
    # Check if under limit
    if state["daily_tldrs"] >= MAX_TLDR_PER_DAY:
        print(f"⏸️ Daily TLDR limit reached ({MAX_TLDR_PER_DAY} TLDRs)")
        return False, state
    
    return True, state


def check_daily_reply_limit(state: dict) -> tuple[bool, dict]:
    """Check daily limit for conversational replies. Returns (can_proceed, updated_state)."""
    today = date.today().isoformat()
    
    # Reset counter if new day (redundant check but safe)
    if state.get("daily_reset_date") != today:
        state["daily_replies"] = 0
        state["daily_reset_date"] = today
    
    # Check if under limit
    if state.get("daily_replies", 0) >= MAX_REPLIES_PER_DAY:
        print(f"⏸️ Daily reply limit reached ({MAX_REPLIES_PER_DAY} replies)")
        return False, state
    
    return True, state


def is_too_old(created_utc: float) -> bool:
    """Check if a post/comment is older than MAX_AGE_HOURS."""
    age_seconds = datetime.utcnow().timestamp() - created_utc
    age_hours = age_seconds / 3600
    return age_hours > MAX_AGE_HOURS


def main():
    parser = argparse.ArgumentParser(description="Reddit Mod Bot for GitHub Actions")
    parser.add_argument("--dry-run", action="store_true", help="Don't post, just log what would happen")
    args = parser.parse_args()
    
    print(f"🚀 Reddit Mod Bot starting at {datetime.utcnow().isoformat()}")
    
    # Check required environment variables
    required_vars = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD", "GEMINI_API_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Initialize Reddit
    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="Reddit Mod Bot v1.0 (GitHub Actions)"
    )
    bot_username = reddit.user.me().name
    print(f"✅ Connected to Reddit as u/{bot_username}")
    
    # Initialize Gemini
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.0-flash")
    print("✅ Gemini API initialized")
    
    # Load state
    state = load_state()
    last_check = state.get("last_check")
    processed_posts = set(state.get("processed_posts", []))
    processed_comments = set(state.get("processed_comments", []))
    comment_summaries = state.get("comment_summaries", {})
    
    # Check daily limit
    can_proceed, state = check_daily_limit(state)
    
    # Get subreddit
    subreddit = reddit.subreddit(SUBREDDIT)
    
    # Check posts for TLDRs
    tldrs_generated = 0
    total_tokens = 0
    total_cost = 0.0
    
    limit = 10 if last_check is None else 50
    print(f"🔍 Checking last {limit} posts on r/{SUBREDDIT}...")
    
    posts_to_check = list(subreddit.new(limit=limit))
    
    # Phase 1: Generate TLDRs for long posts
    if can_proceed:
        for submission in posts_to_check:
            # Skip if too old (older than MAX_AGE_HOURS)
            if is_too_old(submission.created_utc):
                continue
            
            # Skip if already processed
            if submission.id in processed_posts:
                continue
            
            # Skip if no text content
            if not submission.selftext:
                continue
            
            # Check word count
            word_count = count_words(submission.selftext)
            if word_count < POST_WORD_THRESHOLD:
                print(f"  📝 Post {submission.id}: {word_count} words (below {POST_WORD_THRESHOLD} threshold)")
                continue
            
            print(f"  ✨ Post {submission.id}: {word_count} words - Generating TLDR...")
            
            if args.dry_run:
                print(f"     [DRY RUN] Would generate TLDR for: {submission.title[:50]}...")
                processed_posts.add(submission.id)
                continue
            
            try:
                # Generate TLDR
                tldr_text, token_info = generate_tldr(submission.selftext, submission.title, model)
                
                # Post comment
                comment_text = f"**Post TLDR:** {tldr_text}"
                comment = submission.reply(comment_text)
                comment.mod.distinguish(sticky=False)
                
                print(f"     ✅ Posted TLDR ({len(tldr_text.split())} words, {token_info['total_tokens']} tokens)")
                
                processed_posts.add(submission.id)
                tldrs_generated += 1
                state["daily_tldrs"] = state.get("daily_tldrs", 0) + 1
                total_tokens += token_info["total_tokens"]
                total_cost += token_info["cost"]
                
                # Only 1 TLDR per run
                if tldrs_generated >= MAX_TLDR_PER_RUN:
                    print(f"  ⏸️ Reached max TLDRs per run ({MAX_TLDR_PER_RUN})")
                    break
                    
            except Exception as e:
                print(f"     ❌ Error: {e}")
    
    # Phase 2: Check for comment summaries (if we haven't hit daily limit)
    can_proceed, state = check_daily_limit(state)
    
    if can_proceed:
        print(f"\n💬 Checking posts for comment summaries...")
        
        for submission in posts_to_check:
            # Skip if too old (older than MAX_AGE_HOURS)
            if is_too_old(submission.created_utc):
                continue
            
            comment_count = submission.num_comments
            post_id = submission.id
            last_milestone = comment_summaries.get(post_id, 0)
            
            next_milestone = get_next_milestone(comment_count, last_milestone)
            
            if next_milestone == 0:
                continue  # No new milestone
            
            print(f"  📊 Post {post_id}: {comment_count} comments - New milestone {next_milestone}!")
            
            if args.dry_run:
                print(f"     [DRY RUN] Would generate comment summary for: {submission.title[:50]}...")
                comment_summaries[post_id] = next_milestone
                continue
            
            try:
                # Fetch comments
                submission.comments.replace_more(limit=0)
                top_comments = list(submission.comments)[:30]
                
                if len(top_comments) < 5:
                    print(f"     ⏭️ Not enough substantive comments to summarize")
                    continue
                
                # Generate comment summary
                summary_text, token_info = generate_comment_summary(top_comments, model)
                
                if not summary_text:
                    print(f"     ⏭️ Could not generate summary")
                    continue
                
                # Find existing bot comment or create new one
                existing_comment = find_bot_comment(submission, bot_username)
                
                if existing_comment:
                    # Edit existing comment to update/replace comment summary
                    new_body = existing_comment.body
                    
                    # Remove old comment summary if present
                    # Handle two cases:
                    # 1. Summary appended to TLDR with --- separator
                    # 2. Standalone summary-only comment (starts with **💬)
                    import re
                    
                    # First try: split on --- before discussion summary
                    if re.search(r'\n*---\s*\n+\*\*💬', new_body):
                        new_body = re.split(r'\n*---\s*\n+\*\*💬', new_body)[0].rstrip()
                        new_body += f"\n\n---\n\n**💬 Discussion Summary ({next_milestone}+ comments):** {summary_text}"
                    # Second case: comment is ONLY a discussion summary (starts with it)
                    elif new_body.strip().startswith('**💬'):
                        new_body = f"**💬 Discussion Summary ({next_milestone}+ comments):** {summary_text}"
                    # Fallback: just append
                    else:
                        new_body += f"\n\n---\n\n**💬 Discussion Summary ({next_milestone}+ comments):** {summary_text}"
                    
                    existing_comment.edit(new_body)
                    print(f"     ✅ Updated existing comment with summary ({token_info['total_tokens']} tokens)")
                else:
                    # Create new pinned comment
                    comment_text = f"**💬 Discussion Summary ({next_milestone}+ comments):** {summary_text}"
                    comment = submission.reply(comment_text)
                    comment.mod.distinguish(sticky=False)
                    print(f"     ✅ Created new summary comment ({token_info['total_tokens']} tokens)")
                
                comment_summaries[post_id] = next_milestone
                state["daily_tldrs"] = state.get("daily_tldrs", 0) + 1
                total_tokens += token_info["total_tokens"]
                total_cost += token_info["cost"]
                
                # Only process one comment summary per run as well
                break
                    
            except Exception as e:
                print(f"     ❌ Error: {e}")
    
    # Phase 3: Generate TLDRs for long individual comments
    can_proceed, state = check_daily_limit(state)
    
    if can_proceed:
        print(f"\n📝 Checking for long comments to TLDR...")
        
        for submission in posts_to_check:
            # Skip if too old (older than MAX_AGE_HOURS)
            if is_too_old(submission.created_utc):
                continue
            
            # Already hit limit for this run?
            if tldrs_generated >= MAX_TLDR_PER_RUN:
                break
            
            # Fetch comments
            submission.comments.replace_more(limit=0)
            all_comments = submission.comments.list()
            comment_lookup = {c.id: c for c in all_comments}
            
            for comment in all_comments:
                # Skip if already processed
                if comment.id in processed_comments:
                    continue
                
                # Skip if comment is too old
                if is_too_old(comment.created_utc):
                    continue
                
                # Skip deleted/removed comments
                if not hasattr(comment, 'body') or not comment.body or comment.body == '[deleted]':
                    continue
                
                # Skip bot's own comments
                if hasattr(comment, 'author') and comment.author and comment.author.name == bot_username:
                    continue
                
                # Check word count
                word_count = count_words(comment.body)
                if word_count < COMMENT_WORD_THRESHOLD:
                    continue
                
                print(f"  ✨ Comment {comment.id}: {word_count} words - Generating TLDR...")
                
                if args.dry_run:
                    print(f"     [DRY RUN] Would generate Comment TLDR")
                    processed_comments.add(comment.id)
                    continue
                
                try:
                    # Generate TLDR for the comment with context
                    tldr_text, token_info = generate_comment_tldr(comment, submission, model, comment_lookup)
                    
                    # Post reply to the comment
                    reply_text = f"**Comment TLDR:** {tldr_text}"
                    reply = comment.reply(reply_text)
                    
                    print(f"     ✅ Posted Comment TLDR ({len(tldr_text.split())} words, {token_info['total_tokens']} tokens)")
                    
                    processed_comments.add(comment.id)
                    tldrs_generated += 1
                    state["daily_tldrs"] = state.get("daily_tldrs", 0) + 1
                    total_tokens += token_info["total_tokens"]
                    total_cost += token_info["cost"]
                    
                    # Only 1 TLDR per run
                    if tldrs_generated >= MAX_TLDR_PER_RUN:
                        print(f"  ⏸️ Reached max TLDRs per run ({MAX_TLDR_PER_RUN})")
                        break
                        
                except Exception as e:
                    print(f"     ❌ Error: {e}")
            
            # Break outer loop if we hit limit
            if tldrs_generated >= MAX_TLDR_PER_RUN:
                break
    
    # Phase 4: Check inbox for replies to bot's comments
    replies_sent = 0
    can_reply, state = check_daily_reply_limit(state)
    
    if can_reply:
        print(f"\n📬 Phase 4: Checking inbox for replies to bot comments...")
        try:
            replies_sent, reply_tokens, reply_cost, state = check_inbox_replies(
                reddit, model, state, bot_username, args.dry_run
            )
            total_tokens += reply_tokens
            total_cost += reply_cost
            if replies_sent > 0:
                print(f"  💬 Sent {replies_sent} conversational replies")
        except Exception as e:
            print(f"  ❌ Error in reply handling: {e}")
    
    # Phase 5: Check for bot summons in the subreddit
    summons_handled = 0
    can_reply, state = check_daily_reply_limit(state)
    
    if can_reply:
        print(f"\n🔔 Phase 5: Checking for bot summons...")
        try:
            summons_handled, summon_tokens, summon_cost, state = check_for_summons(
                subreddit, model, state, bot_username, reddit=reddit, dry_run=args.dry_run
            )
            total_tokens += summon_tokens
            total_cost += summon_cost
            if summons_handled > 0:
                print(f"  🎯 Responded to {summons_handled} summons")
        except Exception as e:
            print(f"  ❌ Error in summon handling: {e}")
    
    # Phase 6: Auto-ban users with excessive negative karma
    users_banned = 0
    print(f"\n🔨 Phase 6: Checking for negative karma users to ban...")
    try:
        users_banned, state = check_and_ban_negative_karma_users(
            subreddit, state, args.dry_run
        )
        if users_banned > 0:
            print(f"  ⛔ Banned {users_banned} user(s)")
    except Exception as e:
        print(f"  ❌ Error in ban handling: {e}")
    
    # Phase 7: Crosspost top AI posts to r/ProAI
    crossposts_made = 0
    crosspost_tokens = 0
    crosspost_cost = 0.0
    if CROSSPOST_ENABLED:
        try:
            crossposts_made, crosspost_tokens, crosspost_cost, state = check_and_crosspost(
                reddit, model, state, args.dry_run
            )
            total_tokens += crosspost_tokens
            total_cost += crosspost_cost
        except Exception as e:
            print(f"  ❌ Error in crosspost handling: {e}")
    
    # Phase 8: Refresh acceleration flairs for opted-in users (weekly)
    accel_refreshed = 0
    if ACCELERATION_ENABLED:
        print(f"\n🚀 Phase 8: Checking acceleration flair refreshes...")
        try:
            accel_refreshed, state = refresh_opted_in_users(
                subreddit, reddit, state, args.dry_run
            )
            if accel_refreshed > 0:
                print(f"  🔄 Refreshed {accel_refreshed} acceleration flair(s)")
        except Exception as e:
            print(f"  ❌ Error in acceleration refresh: {e}")
    
    # Phase 9: Process background scan queue (1 user per cycle to avoid API limits)
    queue_scanned = 0
    if ACCELERATION_ENABLED:
        try:
            queue_scanned, state = process_scan_queue(
                subreddit, reddit, state, args.dry_run
            )
        except Exception as e:
            print(f"  ❌ Error in queue processing: {e}")
    
    # Update state
    state["last_check"] = datetime.utcnow().timestamp()
    state["processed_posts"] = list(processed_posts)[-1000:]  # Keep last 1000
    state["processed_comments"] = list(processed_comments)[-2000:]  # Keep last 2000
    state["comment_summaries"] = comment_summaries
    state["stats"]["total_posts_processed"] += 1
    state["stats"]["total_tldrs_generated"] += tldrs_generated
    state["stats"]["total_tokens_used"] += total_tokens
    state["stats"]["total_cost"] += total_cost
    state["stats"]["total_replies_sent"] = state["stats"].get("total_replies_sent", 0) + replies_sent
    state["stats"]["total_summons_handled"] = state["stats"].get("total_summons_handled", 0) + summons_handled
    
    save_state(state)
    update_stats(tldrs_generated=tldrs_generated, tokens=total_tokens, cost=total_cost)
    
    print(f"\n📊 Summary:")
    print(f"   TLDRs: {tldrs_generated} | Replies: {replies_sent} | Summons: {summons_handled} | Bans: {users_banned} | Crossposts: {crossposts_made}")
    print(f"   Tokens: {total_tokens} | Cost: ${total_cost:.6f}")
    print(f"   Daily TLDRs: {state['daily_tldrs']}/{MAX_TLDR_PER_DAY} | Daily Replies: {state.get('daily_replies', 0)}/{MAX_REPLIES_PER_DAY}")
    print(f"✅ Reddit Bot completed at {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    main()
