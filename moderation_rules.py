"""
Discrete rule-based moderation system.

Rules are independent yes/no questions evaluated by the LLM against each
post/comment. Each rule carries its own action, conditions, and target
scope. Rules are loaded from a JSON file with an optional env-var override.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModerationRule:
    """A single moderation rule evaluated against Reddit content."""

    name: str
    description: str
    active: bool = True
    order: int = 100
    target: str = "both"  # "posts", "comments", or "both"
    actions: list[str] = field(default_factory=lambda: ["report"])
    conditions: dict = field(default_factory=dict)
    flairs: list[str] = field(default_factory=list)
    use_vision: bool = False

    @property
    def stop_on_match(self) -> bool:
        return self.conditions.get("stop_on_match", False)

    @property
    def skip_mods(self) -> bool:
        return self.conditions.get("skip_mods", False)

    @property
    def skip_approved(self) -> bool:
        return self.conditions.get("skip_approved", False)

    def applies_to(self, content_type: str) -> bool:
        """Return True if this rule applies to the given content type."""
        if self.target == "both":
            return True
        return self.target == content_type


class RuleLoadError(Exception):
    """Raised when rules cannot be loaded or validated."""


def _validate_rule(rule_dict: dict, index: int) -> ModerationRule:
    """Validate a single rule dict and return a ModerationRule."""
    if "name" not in rule_dict:
        raise RuleLoadError(f"Rule at index {index} is missing 'name'")
    if "description" not in rule_dict:
        raise RuleLoadError(f"Rule '{rule_dict.get('name', '?')}' is missing 'description'")

    name = rule_dict["name"]
    if not isinstance(name, str) or not name.strip():
        raise RuleLoadError(f"Rule at index {index} has empty 'name'")
    if " " in name:
        raise RuleLoadError(
            f"Rule name '{name}' contains spaces; use underscores"
        )

    valid_targets = {"posts", "comments", "both"}
    target = rule_dict.get("target", "both")
    if target not in valid_targets:
        raise RuleLoadError(
            f"Rule '{name}' has invalid target '{target}'; "
            f"must be one of {valid_targets}"
        )

    actions = rule_dict.get("actions", ["report"])
    if not isinstance(actions, list) or not actions:
        raise RuleLoadError(f"Rule '{name}' must have at least one action")

    valid_actions = {
        "remove", "report", "ban", "lock", "unlock", "spam",
        "approve", "modmail", "notify_discord", "reply", "set_flair",
    }
    for action in actions:
        if action not in valid_actions:
            raise RuleLoadError(
                f"Rule '{name}' has invalid action '{action}'; "
                f"must be one of {valid_actions}"
            )

    order = rule_dict.get("order", 100)
    if not isinstance(order, int):
        raise RuleLoadError(f"Rule '{name}' has non-integer order")

    return ModerationRule(
        name=name,
        description=rule_dict["description"],
        active=rule_dict.get("active", True),
        order=order,
        target=target,
        actions=actions,
        conditions=rule_dict.get("conditions", {}),
        flairs=rule_dict.get("flairs", []),
        use_vision=rule_dict.get("use_vision", False),
    )


def load_rules(path: str | Path | None = None) -> list[ModerationRule]:
    """
    Load moderation rules from a JSON file or the env-var override.

    Resolution order:
      1. BOT_MODERATION_RULES_JSON env var (JSON string)
      2. path argument (file path)
      3. data/rules.json (default)

    Returns a list sorted by order (ascending).
    Raises RuleLoadError on validation failure or missing file.
    """
    # 1. Check env var override
    env_json = os.environ.get("BOT_MODERATION_RULES_JSON", "").strip()
    if env_json:
        try:
            raw = json.loads(env_json)
        except json.JSONDecodeError as e:
            raise RuleLoadError(
                f"BOT_MODERATION_RULES_JSON contains invalid JSON: {e}"
            )
        if not isinstance(raw, list):
            raise RuleLoadError(
                "BOT_MODERATION_RULES_JSON must be a JSON array of rule objects"
            )
        rules = [_validate_rule(r, i) for i, r in enumerate(raw)]
        return sorted(rules, key=lambda r: r.order)

    # 2. Resolve file path
    if path is None:
        path = Path("data/rules.json")
    else:
        path = Path(path)

    if not path.exists():
        raise RuleLoadError(f"Rules file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise RuleLoadError(f"Rules file contains invalid JSON: {e}")

    if not isinstance(raw, list):
        raise RuleLoadError("Rules file must contain a JSON array of rule objects")

    rules = [_validate_rule(r, i) for i, r in enumerate(raw)]
    return sorted(rules, key=lambda r: r.order)


def filter_rules(
    rules: list[ModerationRule],
    content_type: str,
    *,
    active_only: bool = True,
) -> list[ModerationRule]:
    """
    Filter rules by content type and active status.

    Args:
        rules: All loaded rules
        content_type: "posts" or "comments"
        active_only: If True, skip inactive rules

    Returns:
        Filtered list sorted by order
    """
    result = []
    for rule in rules:
        if active_only and not rule.active:
            continue
        if not rule.applies_to(content_type):
            continue
        result.append(rule)
    return sorted(result, key=lambda r: r.order)
