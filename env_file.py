"""
Load and save local .env files (no python-dotenv dependency).
"""

from __future__ import annotations

from pathlib import Path


def load_env_file(path: str | Path) -> dict[str, str]:
    """Parse a .env file into key -> value (no quotes unescaping beyond strip)."""
    path = Path(path)
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        result[key] = value
    return result


def save_env_file(path: str | Path, values: dict[str, str]) -> None:
    """Write .env preserving comments from template header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = load_env_file(path) if path.exists() else {}
    merged = {**existing, **{k: v for k, v in values.items() if v is not None}}

    lines = [
        "# Optimist Prime bot — local settings (gitignored; do not commit)",
        "# Edit via: py settings_gui.py",
        "",
    ]
    for key in sorted(merged.keys()):
        val = merged[key]
        if val == "":
            lines.append(f"{key}=")
        else:
            # Quote values with spaces or # characters
            if any(c in val for c in " #\t"):
                safe = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key}="{safe}"')
            else:
                lines.append(f"{key}={val}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_local_env(path: str | Path | None = None, *, override: bool = False) -> dict[str, str]:
    """
    Load .env from the repo root into os.environ.

    By default, existing environment variables are not overwritten (CI/shell wins).
    """
    import os

    repo_root = Path(__file__).resolve().parent
    env_path = Path(path) if path else repo_root / ".env"
    values = load_env_file(env_path)
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return values


def apply_env_to_os(values: dict[str, str]) -> None:
    """Apply dict to os.environ (for preview in same process)."""
    import os
    for k, v in values.items():
        if v == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
