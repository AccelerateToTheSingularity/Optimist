"""Health diagnostics dump for agents and operators.

Implements Application Standard 20 (health diagnostics).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent

_PROCESS_STARTED_AT = time.time()


def _safe_read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _recent_audit_errors(limit: int = 10) -> list[dict[str, Any]]:
    from audit_log import AUDIT_LOG_FILE

    entries = _safe_read_json(Path(AUDIT_LOG_FILE), [])
    if not isinstance(entries, list):
        return []
    errors: list[dict[str, Any]] = []
    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue
        outcome = str(entry.get("outcome", "")).lower()
        if "error" in outcome or "fail" in outcome or entry.get("error"):
            errors.append(entry)
            if len(errors) >= limit:
                break
    return errors


def _tail_log_lines(path: Path, max_lines: int = 30) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-max_lines:]
    except OSError:
        return []


def dump_diagnostics() -> dict[str, Any]:
    """Return a machine-readable health snapshot (no secrets)."""
    from bot_logging import current_log_path, log_dir

    try:
        # Avoid importing bot_runner (heavy / side-effectful); keep in sync with BOT_VERSION there.
        version = "2.0"
        import ast

        runner = REPO_ROOT / "bot_runner.py"
        if runner.exists():
            for line in runner.read_text(encoding="utf-8").splitlines():
                if line.startswith("BOT_VERSION"):
                    version = ast.literal_eval(line.split("=", 1)[1].strip())
                    break
    except Exception:
        version = "unknown"

    env_path = REPO_ROOT / ".env"
    state_path = REPO_ROOT / "data" / "bot_state.json"
    prefs_path = REPO_ROOT / "data" / "settings_gui_prefs.json"
    log_path = current_log_path()

    state = _safe_read_json(state_path, {})
    last_run = None
    if isinstance(state, dict):
        last_run = state.get("last_run") or state.get("last_updated") or state.get("day")

    return {
        "ok": True,
        "actionId": "diagnostics.dump",
        "app": "Optimist Prime",
        "version": version,
        "pid": os.getpid(),
        "uptimeSeconds": round(time.time() - _PROCESS_STARTED_AT, 1),
        "startedAt": datetime.fromtimestamp(_PROCESS_STARTED_AT, tz=timezone.utc).isoformat(),
        "now": datetime.now(timezone.utc).isoformat(),
        "mode": {
            "profile": os.environ.get("BOT_PROFILE", ""),
            "subreddit": os.environ.get("BOT_SUBREDDIT", ""),
            "safeMode": os.environ.get("BOT_SAFE_MODE", "false"),
            "botEnabledHint": "Set GitHub variable BOT_ENABLED=true to run in Actions",
        },
        "paths": {
            "repoRoot": str(REPO_ROOT),
            "envFile": str(env_path),
            "envFileExists": env_path.exists(),
            "stateFile": str(state_path),
            "prefsFile": str(prefs_path),
            "logDir": str(log_dir()),
            "logFile": str(log_path),
            "logFileExists": log_path.exists(),
        },
        "integrations": {
            "redditRefreshTokenConfigured": bool(os.environ.get("REDDIT_REFRESH_TOKEN")),
            "redditPasswordAuthConfigured": bool(
                os.environ.get("REDDIT_USERNAME") and os.environ.get("REDDIT_PASSWORD")
            ),
            "llmKeyConfigured": bool(
                os.environ.get("OPENAI_API_KEY")
                or os.environ.get("LLM_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
            ),
        },
        "background": {
            "runtime": "github-actions-scheduled" if os.environ.get("GITHUB_ACTIONS") else "local",
            "lastKnownStateMarker": last_run,
        },
        "recentErrors": _recent_audit_errors(),
        "recentLogLines": _tail_log_lines(log_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump Optimist Prime health diagnostics")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args(argv)
    payload = dump_diagnostics()
    if args.pretty:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        json.dump(payload, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
