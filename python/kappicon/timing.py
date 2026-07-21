"""Opt-in performance timing for startup / discovery (PERF-01).

Enable with::

    KAPPICON_TIMING=1 kappicon

Logs go to stderr as ``kappicon timing: <label>: <ms> ms``.
Unset / empty / 0 / false / no / off → disabled (no spam).
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator


def timing_enabled() -> bool:
    """True when KAPPICON_TIMING is a truthy flag, or KAPPICON_DEBUG=timing."""
    v = (os.environ.get("KAPPICON_TIMING") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("", "0", "false", "no", "off"):
        debug = (os.environ.get("KAPPICON_DEBUG") or "").strip().lower()
        return debug == "timing"
    # Any other non-empty TIMING value counts as enabled
    return bool(v)


def log_timing(label: str, elapsed_s: float) -> None:
    """Print one timing line to stderr when enabled."""
    if not timing_enabled():
        return
    ms = elapsed_s * 1000.0
    print(f"kappicon timing: {label}: {ms:.1f} ms", file=sys.stderr, flush=True)


@contextmanager
def span(label: str) -> Iterator[None]:
    """Time a block with perf_counter; log on exit if timing is enabled."""
    if not timing_enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        log_timing(label, time.perf_counter() - t0)
