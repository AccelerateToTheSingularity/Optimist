"""
Standard footer for public bot comments.
Idempotent: appends footer only once, replaces old footer format.
"""

import re

BOT_COMMENT_FOOTER = "*^(AI assistant \u00b7 mention the bot, mod bot, or use !bot)*"

# Match the footer pattern — starts with *^ or **, ends with *) or *)
CURRENT_FOOTER_REGEX = re.compile(
    r"\*+\^?\(AI assistant \u00b7 mention the bot, mod bot, or use !bot\)\*+",
    re.IGNORECASE,
)


def format_bot_comment(body: str) -> str:
    """Append the standard footer once (idempotent if already present)."""
    trimmed = body.rstrip()
    match = CURRENT_FOOTER_REGEX.search(trimmed)
    if match:
        before_footer = trimmed[: match.start()].rstrip("\n- ").rstrip()
        return f"{before_footer}\n\n---\n{BOT_COMMENT_FOOTER}"
    return f"{trimmed}\n\n---\n{BOT_COMMENT_FOOTER}"
