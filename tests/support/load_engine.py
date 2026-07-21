"""
Load the kAppIcon mutation engine for tests.

Imports `kappicon` from `python/` with env already set by temp_xdg.
Does not read or exec `gui/kappicon` (thin launcher only).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PARENT = REPO_ROOT / "python"

_REQUIRED_SYMBOLS = (
    "ApplyError",
    "apply_lock",
    "apply_icon_to_desktop",
    "prepare_icon_value",
    "kappicon_theme_name",
    "is_kappicon_icon_name",
    "user_override_only_differs_by_icon",
    "_normalized_desktop_without_main_icon",
    "collect_referenced_kappicon_names",
    "prune_unreferenced_kappicon_assets",
    "undo_keep_icon_names",
    "snapshot_user_desktop",
    "restore_user_desktop_snapshot",
    "parse_backup_desktop_id",
    "is_valid_desktop_id",
    "read_desktop_icon_value",
    "set_desktop_icon_py",
    "find_system_desktop_path",
    "find_any_desktop_path",
    "_atomic_write_text",
    "_atomic_copy_file",
    "THEME_ICON_PREFIX",
    "LOCK_FILE",
    "DATA_DIR",
    "USER_APPS_DIR",
    "USER_ICONS_DIR",
    "BACKUP_DIR",
    "TARGET_DIR",
)

_engine_cache: Optional[types.ModuleType] = None
_engine_cache_key: Optional[str] = None


def _purge_kappicon_modules() -> None:
    for k in list(sys.modules):
        if k == "kappicon" or k.startswith("kappicon."):
            del sys.modules[k]


def load_engine(*, force_reload: bool = False) -> types.ModuleType:
    """
    Import kappicon package with current env (must enter temp_xdg first).

    Path constants bind at import time — reloads when DATA_DIR changes.
    """
    global _engine_cache, _engine_cache_key
    import os

    data_dir = os.environ.get("DATA_DIR") or ""
    if not data_dir:
        raise RuntimeError(
            "load_engine requires DATA_DIR in the environment (enter temp_xdg first)"
        )

    cache_key = data_dir
    if not force_reload and _engine_cache is not None and _engine_cache_key == cache_key:
        return _engine_cache

    pkg_parent = str(PACKAGE_PARENT.resolve())
    if pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)

    _purge_kappicon_modules()
    import kappicon  # noqa: E402

    missing = [name for name in _REQUIRED_SYMBOLS if not hasattr(kappicon, name)]
    if missing:
        raise RuntimeError(f"load_engine: missing symbols on kappicon package: {missing}")

    _engine_cache = kappicon
    _engine_cache_key = cache_key
    return kappicon


def clear_engine_cache() -> None:
    global _engine_cache, _engine_cache_key
    _engine_cache = None
    _engine_cache_key = None
    _purge_kappicon_modules()
