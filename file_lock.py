"""
Cross-platform file locking utility for preventing concurrent access.

Uses fcntl on Unix and msvcrt on Windows.
"""

import os
import sys
import time
import json


def _lock_file(file_path: str):
    """Acquire an exclusive lock on a file."""
    lock_path = file_path + ".lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)

    if sys.platform == "win32":
        import msvcrt
        f = open(lock_path, "w")
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            return None
        return f
    else:
        import fcntl
        f = open(lock_path, "w")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            f.close()
            return None
        return f


def _unlock_file(lock_file):
    """Release the lock on a file."""
    if lock_file is None:
        return
    lock_path = lock_file.name
    lock_file.close()
    try:
        os.unlink(lock_path)
    except OSError:
        pass


def safe_json_load(file_path: str, default: dict | list | None = None):
    """Safely load JSON with retry on lock contention."""
    if default is None:
        default = {}

    for attempt in range(5):
        lock = _lock_file(file_path)
        if lock is None:
            time.sleep(0.1 * (attempt + 1))
            continue

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default
        except Exception:
            return default
        finally:
            _unlock_file(lock)

    return default


def safe_json_save(file_path: str, data: dict | list) -> bool:
    """Safely save JSON with retry on lock contention."""
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

    for attempt in range(5):
        lock = _lock_file(file_path)
        if lock is None:
            time.sleep(0.1 * (attempt + 1))
            continue

        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False
        finally:
            _unlock_file(lock)

    return False
