"""
Troll alert modmail when a user's local comment average score is very low.
"""

from __future__ import annotations

from datetime import datetime, timezone

import config
from bot_utils import claim_action, has_action_claim
from contributor_flair import fetch_user_local_history
from mod_attention import build_troll_modmail_body, generate_mod_attention_summary


def _eval_cooldown_active(state: dict, username: str) -> bool:
    cooldowns = state.setdefault("troll_eval_cooldowns", {})
    last = cooldowns.get(username, 0)
    hours = config.TROLL_EVAL_COOLDOWN_HOURS
    return (datetime.now(timezone.utc).timestamp() - last) < hours * 3600


def _mark_eval(state: dict, username: str) -> None:
    state.setdefault("troll_eval_cooldowns", {})[username] = (
        datetime.now(timezone.utc).timestamp()
    )


def maybe_evaluate_troll_alert(
    subreddit,
    reddit,
    username: str,
    state: dict,
    llm_model=None,
    dry_run: bool = False,
) -> bool:
    """
    Send modmail if user has enough local comments and average score below threshold.
    Returns True if alert was sent (or would be sent in dry-run).
    """
    if not config.TROLL_ALERT_ENABLED or not username:
        return False

    if _eval_cooldown_active(state, username):
        return False

    alert_key = f"troll_alert:{username.lower()}"
    if has_action_claim(state, alert_key):
        return False

    _mark_eval(state, username)

    history = fetch_user_local_history(reddit, username, config.SUBREDDIT, limit=100)
    comments = history["comments"]
    if len(comments) < config.TROLL_MIN_COMMENTS:
        return False

    total_score = sum(c["score"] for c in comments)
    average_score = total_score / len(comments)
    if average_score >= config.TROLL_AVG_SCORE_THRESHOLD:
        return False

    if not claim_action(state, alert_key):
        return False

    milestone, specialist = (None, None)
    if config.MILESTONE_FLAIR_ENABLED:
        from contributor_flair import calculate_milestone_tier
        total = len(comments) + history["posts_count"]
        milestone = calculate_milestone_tier(total)

    metrics = {
        "username": username,
        "subreddit": config.SUBREDDIT,
        "average_score": average_score,
        "comment_count": len(comments),
        "total_sub_activity": len(comments) + history["posts_count"],
        "milestone": milestone,
        "specialist": specialist,
    }

    summary = None
    if llm_model and not dry_run:
        try:
            sorted_comments = sorted(comments, key=lambda c: c["score"])[:8]
            sample = [f"[score {c['score']}] {c['body'][:200]}" for c in sorted_comments]
            summary = generate_mod_attention_summary(
                {
                    "kind": "troll_alert",
                    "subreddit": config.SUBREDDIT,
                    "username": username,
                    "metrics": metrics,
                    "sample_comments": sample,
                },
                llm_model,
            )
        except Exception as e:
            print(f"    ⚠️ Troll alert summary failed: {e}")

    body = build_troll_modmail_body(metrics, summary)
    subject = f"⚠️ Troll Alert: u/{username}"

    if dry_run:
        print(f"    [DRY RUN] Would send troll alert modmail for u/{username} (avg {average_score:.1f})")
        from audit_log import log_audit_event
        log_audit_event("troll_alert", username, username, f"avg={average_score:.1f}", "dry-run", True)
        return True

    try:
        subreddit.message(subject, body)
        alerted = state.setdefault("troll_alerted_users", {})
        alerted[username] = datetime.now(timezone.utc).timestamp()
        from audit_log import log_audit_event
        log_audit_event("troll_alert", username, username, f"avg={average_score:.1f}", "modmail", True)
        print(f"    📧 Troll alert modmail sent for u/{username} (avg score {average_score:.1f})")
        return True
    except Exception as e:
        print(f"    ❌ Troll alert modmail failed for u/{username}: {e}")
        return False


def prune_troll_state(state: dict) -> None:
    """Drop old troll alert records beyond cooldown window."""
    days = config.TROLL_ALERT_COOLDOWN_DAYS
    cutoff = datetime.now(timezone.utc).timestamp() - days * 24 * 3600
    alerted = state.get("troll_alerted_users", {})
    if isinstance(alerted, dict):
        state["troll_alerted_users"] = {
            u: t for u, t in alerted.items() if t >= cutoff
        }
