"""Apply/reset/undo mutation API (no Qt)."""
from __future__ import annotations

import os

from .desktop import (
    _atomic_copy_file,
    _atomic_write_text,
    _backup_desktop_if_enabled,
    clear_desktop_icon_py,
    find_any_desktop_path,
    find_system_desktop_path,
    is_valid_desktop_id,
    read_desktop_icon_value,
    set_desktop_icon_py,
    snapshot_user_desktop,
    user_override_only_differs_by_icon,
)
from .icons import is_kappicon_icon_name, prepare_icon_value
from .lock import ApplyError
from .paths import USER_APPS_DIR

def apply_icon_to_desktop(desktop_id, selected_icon, *, shape="as-is", backup=False):
    """
    Apply icon or RESET to one app. Caller must hold apply_lock.
    Returns dict with desktop_id, icon_value, previous_bytes, display path info.
    """
    if not is_valid_desktop_id(desktop_id):
        raise ApplyError(f"Invalid application id:\n{desktop_id}")
    if isinstance(selected_icon, str) and ("\n" in selected_icon or "\r" in selected_icon):
        raise ApplyError("Invalid icon selection (control characters).")

    previous_bytes = snapshot_user_desktop(desktop_id)
    user_path = os.path.join(USER_APPS_DIR, desktop_id)
    app_path = find_any_desktop_path(desktop_id)
    if not app_path or not os.path.isfile(app_path):
        raise ApplyError(f"Could not find desktop entry: {desktop_id}")

    if selected_icon == "RESET":
        _backup_desktop_if_enabled(user_path if os.path.isfile(user_path) else app_path, backup)
        if not os.path.isfile(user_path):
            return {
                "desktop_id": desktop_id,
                "icon_value": read_desktop_icon_value(app_path) or "",
                "previous_bytes": previous_bytes,
                "reset": True,
                "noop": True,
            }
        sys_path = find_system_desktop_path(desktop_id)
        if not sys_path:
            # User-only launcher: no package default to restore (same as Overrides)
            raise ApplyError(
                "No system .desktop was found for this launcher.\n"
                "Reset cannot invent an original icon for a user-only app.\n"
                "Use a backup restore if you saved one, or set an icon on Map."
            )
        # Prefer removing a kAppIcon-only override so the launcher follows packages again
        if user_override_only_differs_by_icon(user_path, sys_path):
            try:
                os.unlink(user_path)
            except OSError as e:
                raise ApplyError(f"Could not remove user override:\n{e}") from e
            icon_value = read_desktop_icon_value(sys_path) or ""
            return {
                "desktop_id": desktop_id,
                "icon_value": icon_value,
                "previous_bytes": previous_bytes,
                "reset": True,
                "noop": False,
                "removed_override": True,
            }
        # Preserve other customizations (actions, etc.): only restore Icon=
        orig = read_desktop_icon_value(sys_path)
        if orig:
            set_desktop_icon_py(user_path, orig)
            icon_value = orig
        else:
            clear_desktop_icon_py(user_path)
            icon_value = ""
        return {
            "desktop_id": desktop_id,
            "icon_value": icon_value,
            "previous_bytes": previous_bytes,
            "reset": True,
            "noop": False,
            "removed_override": False,
        }

    _backup_desktop_if_enabled(app_path, backup)
    icon_value = prepare_icon_value(selected_icon, desktop_id, shape=shape)

    # Ensure user copy exists
    if app_path != user_path:
        _atomic_copy_file(app_path, user_path)
    try:
        os.chmod(user_path, 0o644)
    except OSError:
        pass
    set_desktop_icon_py(user_path, icon_value)
    return {
        "desktop_id": desktop_id,
        "icon_value": icon_value,
        "previous_bytes": previous_bytes,
        "reset": False,
        "noop": False,
    }



def undo_keep_icon_names(undo_stack):
    """Parse Icon= from undo snapshots so prune does not delete still-revertable assets."""
    keep = set()
    for entry in undo_stack or []:
        raw = entry.get("previous_bytes")
        if not raw:
            continue
        try:
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        except Exception:
            continue
        in_entry = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                in_entry = s == "[Desktop Entry]"
                continue
            if in_entry and s.startswith("Icon="):
                name = s.split("=", 1)[1].strip()
                if is_kappicon_icon_name(name):
                    keep.add(name)
                break
    return keep


_cache_refresh_timer = None



