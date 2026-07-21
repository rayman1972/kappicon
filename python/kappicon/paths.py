"""XDG / kAppIcon path resolution from environment.

Import only after temp_xdg (or product shell) has set path env vars.
Constants bind at import time.
"""
from __future__ import annotations

import os
import shutil
import subprocess

def _env_path(key, *fallback_parts):
    """Prefer an exported path env var; otherwise join fallback parts."""
    v = (os.environ.get(key) or "").strip()
    if v:
        return v
    return os.path.join(*fallback_parts)


def _run_host(cmd, **kwargs):
    """Run a command on the host when inside Flatpak (for icon cache tools)."""
    if os.environ.get("FLATPAK_ID") and shutil.which("flatpak-spawn"):
        cmd = ["flatpak-spawn", "--host", "--"] + list(cmd)
    return subprocess.run(cmd, **kwargs)


def xdg_config_home():
    return _env_path("XDG_CONFIG_HOME", os.path.expanduser("~"), ".config")


def xdg_data_home():
    return _env_path("XDG_DATA_HOME", os.path.expanduser("~"), ".local/share")


def xdg_user_dir_default(name, english_name):
    """DOWNLOAD/PICTURES from env (set by bash) or ~/english_name."""
    env_key = f"XDG_{name}_DIR"
    v = (os.environ.get(env_key) or "").strip()
    if v and v != os.path.expanduser("~"):
        return v
    return os.path.join(os.path.expanduser("~"), english_name)


XDG_CONFIG_HOME = xdg_config_home()
XDG_DATA_HOME = xdg_data_home()
DATA_DIR = _env_path("DATA_DIR", XDG_DATA_HOME, "kappicon")
LIBRARY_DIR = _env_path("LIBRARY_DIR", DATA_DIR, "icons")
USER_APPS_DIR = _env_path("USER_APPS_DIR", XDG_DATA_HOME, "applications")
USER_ICONS_DIR = _env_path("USER_ICONS_DIR", XDG_DATA_HOME, "icons")
BACKUP_DIR = _env_path("BACKUP_DIR_DEFAULT", DATA_DIR, "backups")
TARGET_DIR = _env_path(
    "TARGET_DIR",
    os.path.join(xdg_user_dir_default("PICTURES", "Pictures"), "KAppIcon"),
)
DOWNLOADS_DIR_DEFAULT = _env_path(
    "DOWNLOADS_DIR", xdg_user_dir_default("DOWNLOAD", "Downloads")
)
os.makedirs(LIBRARY_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(USER_APPS_DIR, exist_ok=True)
os.makedirs(TARGET_DIR, exist_ok=True)
LOCK_FILE = os.path.join(DATA_DIR, "apply.lock")
# Sentinel stored on the empty-state list row so a click can open a file browser
BROWSE_FOR_ICON = "__browse_for_icon__"
# UserRole payload prefix for freedesktop/theme icon names (Icon=fooname)
THEME_ICON_PREFIX = "theme:"
DESKTOP_LIST_RAW = [d for d in os.environ.get("DESKTOP_LIST", "").strip().split("\n") if d]


# ── In-process apply engine (GUI stays open; exclusive lock; atomic writes) ──

