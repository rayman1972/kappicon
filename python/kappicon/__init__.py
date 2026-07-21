"""kAppIcon shared package — mutation/desktop/icon core.

Path constants bind at import time from the environment. Always set XDG / DATA_DIR
(via product shell or tests.support.xdg_sandbox.temp_xdg) before importing this package.
"""
from __future__ import annotations

from .desktop import (
    _atomic_copy_file,
    _atomic_write_text,
    _normalized_desktop_without_main_icon,
    find_any_desktop_path,
    find_system_desktop_path,
    is_valid_desktop_id,
    parse_backup_desktop_id,
    path_is_under,
    read_desktop_icon_value,
    restore_user_desktop_snapshot,
    set_desktop_icon_py,
    snapshot_user_desktop,
    user_override_only_differs_by_icon,
)
from .icons import (
    collect_referenced_kappicon_names,
    is_kappicon_icon_name,
    kappicon_theme_name,
    prepare_icon_value,
    prune_unreferenced_kappicon_assets,
)
from .lock import ApplyError, apply_lock
from .mutation import apply_icon_to_desktop, undo_keep_icon_names
from .paths import (
    BACKUP_DIR,
    DATA_DIR,
    LOCK_FILE,
    TARGET_DIR,
    THEME_ICON_PREFIX,
    USER_APPS_DIR,
    USER_ICONS_DIR,
)

__all__ = [
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
    "path_is_under",
]
