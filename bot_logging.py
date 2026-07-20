"""Observable rotating JSONL logging for local and CI bot runs.

Implements Application Standard 14 (observable logging).
"""

from __future__ import annotations

import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = REPO_ROOT / "logs"
APP_LOGGER_NAME = "optimist_prime"


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr, key in (
            ("event_name", "eventName"),
            ("correlation_id", "correlationId"),
            ("action_id", "actionId"),
            ("component", "component"),
        ):
            if hasattr(record, attr):
                payload[key] = getattr(record, attr)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def log_dir() -> Path:
    raw = os.environ.get("BOT_LOG_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_LOG_DIR


def current_log_path() -> Path:
    return log_dir() / f"{APP_LOGGER_NAME}.jsonl"


def configure_logging(*, retention_days: int = 14, also_stderr: bool = True) -> Path:
    """Configure app logging; return the active JSONL log path."""
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = current_log_path()

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers when reconfigured in tests
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    file_handler = TimedRotatingFileHandler(
        filename=path,
        when="midnight",
        backupCount=retention_days,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setFormatter(JsonLineFormatter())
    root.addHandler(file_handler)

    if also_stderr:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        root.addHandler(stream)

    logging.getLogger(APP_LOGGER_NAME).info(
        "logging configured",
        extra={"event_name": "logging.configured", "component": "bot_logging"},
    )
    return path


def get_logger(name: str = APP_LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    event_name: str,
    message: str,
    *,
    level: int = logging.INFO,
    correlation_id: str | None = None,
    action_id: str | None = None,
    component: str | None = None,
    **extra: Any,
) -> None:
    payload = {"event_name": event_name}
    if correlation_id:
        payload["correlation_id"] = correlation_id
    if action_id:
        payload["action_id"] = action_id
    if component:
        payload["component"] = component
    payload.update(extra)
    get_logger().log(level, message, extra=payload)
