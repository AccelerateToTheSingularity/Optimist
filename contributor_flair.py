"""
Contributor recognition flairs: milestone tiers and specialist roles for r/accelerate.

Combines with acceleration tier (D1) via USER_FLAIR_TEMPLATE.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import config
from acceleration_handler import get_first_flair_template


def truncate_flair_text(text: str, max_len: int | None = None) -> str:
    limit = max_len or config.USER_FLAIR_MAX_LEN
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def build_user_flair_text(
    acceleration: str | None = None,
    milestone: str | None = None,
    specialist: str | None = None,
) -> str:
    """Build combined flair string from template, omitting empty segments."""
    template = config.USER_FLAIR_TEMPLATE
    parts = {
        "acceleration": (acceleration or "").strip(),
        "milestone": (milestone or "").strip(),
        "specialist": (specialist or "").strip(),
    }
    text = template.format(**parts)
    # Collapse empty segments and stray pipes
    segments = [s.strip() for s in text.split("|") if s.strip()]
    return truncate_flair_text(" | ".join(segments))


def parse_milestone_tiers(json_str: str) -> list[tuple[int, str]]:
    """Parse [[count, label], ...] descending by count."""
    raw = json.loads(json_str)
    tiers: list[tuple[int, str]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            tiers.append((int(item[0]), str(item[1])))
    tiers.sort(key=lambda x: x[0], reverse=True)
    return tiers


def calculate_milestone_tier(activity_count: int, json_str: str | None = None) -> str | None:
    if activity_count <= 0:
        return None
    tiers = parse_milestone_tiers(json_str or config.MILESTONE_TIERS_JSON)
    for min_count, label in tiers:
        if activity_count >= min_count:
            return label
    return None


def fetch_user_local_history(reddit, username: str, subreddit_name: str, limit: int = 100) -> dict:
    """Fetch recent posts/comments by user in the target subreddit."""
    sub_lower = subreddit_name.lower()
    comments: list[dict] = []
    posts_count = 0

    try:
        redditor = reddit.redditor(username)
        for comment in redditor.comments.new(limit=limit * 2):
            if str(comment.subreddit).lower() != sub_lower:
                continue
            if not comment.body or comment.body == "[deleted]":
                continue
            comments.append({"body": comment.body, "score": comment.score})
            if len(comments) >= limit:
                break

        for submission in redditor.submissions.new(limit=limit):
            if str(submission.subreddit).lower() != sub_lower:
                continue
            posts_count += 1
            if posts_count >= limit:
                break
    except Exception as e:
        print(f"    ⚠️ Could not fetch local history for u/{username}: {e}")

    return {"comments": comments, "posts_count": posts_count}


def classify_specialist_role(comments_text: str, llm_model, roles: str | None = None) -> str | None:
    """LLM picks one specialist role from permitted list."""
    from prompts import get_specialist_classification_prompt

    allowed = [r.strip() for r in (roles or config.SPECIALIST_ROLES).split(",") if r.strip()]
    if not allowed or not comments_text.strip():
        return None

    prompt = get_specialist_classification_prompt(comments_text, allowed)
    try:
        response = llm_model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 32},
        )
        picked = response.text.strip().strip('"').strip("'")
        for role in allowed:
            if role.lower() == picked.lower():
                return role
        # Partial match fallback
        for role in allowed:
            if role.lower() in picked.lower() or picked.lower() in role.lower():
                return role
    except Exception as e:
        print(f"    ⚠️ Specialist classification failed for comment sample: {e}")
    return None


def _specialist_due(state: dict, username: str) -> bool:
    contrib = state.setdefault("contributor_flair", {})
    users = contrib.setdefault("specialist_refresh", {})
    last = users.get(username, 0)
    refresh_sec = config.SPECIALIST_REFRESH_DAYS * 24 * 3600
    return (datetime.now(timezone.utc).timestamp() - last) >= refresh_sec


def compute_contributor_labels(
    reddit,
    username: str,
    subreddit_name: str,
    state: dict,
    llm_model,
) -> tuple[str | None, str | None]:
    """Return (milestone_label, specialist_label)."""
    history = fetch_user_local_history(reddit, username, subreddit_name, limit=100)
    total_activity = len(history["comments"]) + history["posts_count"]

    milestone = None
    if config.MILESTONE_FLAIR_ENABLED and total_activity > 0:
        milestone = calculate_milestone_tier(total_activity)

    specialist = None
    if config.SPECIALIST_FLAIR_ENABLED and history["comments"] and _specialist_due(state, username):
        sample = "\n---\n".join(c["body"][:400] for c in history["comments"][:30])
        specialist = classify_specialist_role(sample, llm_model)
        if specialist:
            state["contributor_flair"]["specialist_refresh"][username] = (
                datetime.now(timezone.utc).timestamp()
            )

    return milestone, specialist


def apply_user_flair_text(subreddit, username: str, flair_text: str, dry_run: bool = False) -> bool:
    if dry_run:
        print(f"    [DRY RUN] Would set flair for u/{username}: {flair_text!r}")
        return True
    try:
        template_id = get_first_flair_template(subreddit)
        text = truncate_flair_text(flair_text)
        if template_id:
            subreddit.flair.set(username, text=text, flair_template_id=template_id)
        else:
            subreddit.flair.set(username, text=text or None)
        return True
    except Exception as e:
        print(f"    ❌ Error setting flair for u/{username}: {e}")
        return False


def apply_combined_user_flair(
    subreddit,
    reddit,
    username: str,
    state: dict,
    llm_model,
    acceleration_tier: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Apply milestone/specialist labels combined with optional acceleration tier."""
    if not (config.MILESTONE_FLAIR_ENABLED or config.SPECIALIST_FLAIR_ENABLED or acceleration_tier):
        if acceleration_tier:
            from acceleration_handler import update_user_flair
            return update_user_flair(subreddit, username, acceleration_tier, remove=False)
        return False

    milestone, specialist = compute_contributor_labels(
        reddit, username, config.SUBREDDIT, state, llm_model,
    )
    flair_text = build_user_flair_text(
        acceleration=acceleration_tier,
        milestone=milestone,
        specialist=specialist,
    )
    if not flair_text:
        return False
    ok = apply_user_flair_text(subreddit, username, flair_text, dry_run=dry_run)
    if ok:
        print(f"    ✅ Flair for u/{username}: {flair_text}")
    return ok


def try_acceleration_autoban(
    subreddit,
    username: str,
    pro_ai_karma: int,
    state: dict,
    dry_run: bool = False,
) -> bool:
    """Ban user when pro-AI karma below threshold (opt-in)."""
    if not config.ACCELERATION_AUTOBAN_ENABLED:
        return False
    if pro_ai_karma >= config.ACCELERATION_AUTOBAN_THRESHOLD:
        return False

    banned = set(state.get("banned_users", []))
    if username in banned:
        return False

    reason = (
        f"Auto-ban: pro-AI karma {pro_ai_karma} below threshold "
        f"{config.ACCELERATION_AUTOBAN_THRESHOLD}"
    )
    if dry_run:
        print(f"    [DRY RUN] Would ban u/{username}: {reason}")
        return True

    try:
        subreddit.banned.add(
            username,
            ban_reason=reason[:100],
            ban_message=(
                f"Your account was banned from r/{config.SUBREDDIT} due to sustained "
                f"negative engagement patterns across pro-AI communities."
            ),
        )
        banned.add(username)
        state["banned_users"] = list(banned)[-500:]
        from audit_log import log_audit_event
        log_audit_event("autoban", username, username, reason[:80], "banned", True)
        print(f"    ⛔ Auto-banned u/{username} ({reason})")
        return True
    except Exception as e:
        print(f"    ❌ Auto-ban failed for u/{username}: {e}")
        return False
