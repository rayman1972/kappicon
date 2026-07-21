"""Exclusive apply lock (fcntl)."""
from __future__ import annotations

import fcntl
import os
import time
from contextlib import contextmanager

from .paths import DATA_DIR, LOCK_FILE

class ApplyError(Exception):
    """User-visible apply failure (safe to show in a message box)."""



@contextmanager
def apply_lock(timeout=45.0):
    """Exclusive flock for desktop + hicolor mutations (pairs with CLI/shell)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = open(LOCK_FILE, "a+", encoding="utf-8")
    deadline = time.monotonic() + float(timeout)
    try:
        while True:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ApplyError(
                        "Another kAppIcon operation is in progress (lock timeout)."
                    )
                time.sleep(0.08)
        yield
    finally:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            fd.close()
        except OSError:
            pass



