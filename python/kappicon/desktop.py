"""Desktop entry parse/write and path helpers (no Qt)."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import datetime

from .lock import ApplyError
from .paths import BACKUP_DIR, USER_APPS_DIR

def _atomic_write_text(path, text):
    dirn = os.path.dirname(path) or "."
    os.makedirs(dirn, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kappicon-", suffix=".tmp", dir=dirn)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _atomic_copy_file(src, dest):
    dirn = os.path.dirname(dest) or "."
    os.makedirs(dirn, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kappicon-", suffix=".tmp", dir=dirn)
    os.close(fd)
    try:
        shutil.copy2(src, tmp)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dest)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_desktop_icon_value(path):
    """Icon= from [Desktop Entry], or None."""
    if not path or not os.path.isfile(path):
        return None
    in_entry = False
    try:
        with open(path, "r", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("[") and line.endswith("]"):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if in_entry and line.startswith("Icon="):
                    return line.split("=", 1)[1]
    except OSError:
        return None
    return None


def set_desktop_icon_py(desktop_file, icon_value):
    """Set Icon= only inside [Desktop Entry], atomically."""
    if not desktop_file or not icon_value:
        raise ApplyError("Empty path or icon value.")
    try:
        with open(desktop_file, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        raise ApplyError(str(e)) from e
    out = []
    in_entry = False
    icon_set = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_entry and not icon_set:
                out.append(f"Icon={icon_value}\n")
                icon_set = True
            in_entry = stripped == "[Desktop Entry]"
            out.append(line if line.endswith("\n") else line + "\n")
            continue
        if in_entry and stripped.startswith("Icon="):
            if not icon_set:
                out.append(f"Icon={icon_value}\n")
                icon_set = True
            continue
        out.append(line if line.endswith("\n") or line == "" else line + "\n")
    if in_entry and not icon_set:
        out.append(f"Icon={icon_value}\n")
    elif not icon_set:
        out.insert(0, "[Desktop Entry]\n")
        out.insert(1, f"Icon={icon_value}\n")
    _atomic_write_text(desktop_file, "".join(out))


def clear_desktop_icon_py(desktop_file):
    try:
        with open(desktop_file, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        raise ApplyError(str(e)) from e
    out = []
    in_entry = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_entry = stripped == "[Desktop Entry]"
            out.append(line if line.endswith("\n") else line + "\n")
            continue
        if in_entry and stripped.startswith("Icon="):
            continue
        out.append(line if line.endswith("\n") or line == "" else line + "\n")
    _atomic_write_text(desktop_file, "".join(out))


def find_system_desktop_path(desktop_id):
    """First non-user applications path containing desktop_id."""
    user = os.path.normpath(USER_APPS_DIR)
    candidates = []
    for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        d = d.strip()
        if d:
            candidates.append(os.path.join(d, "applications"))
    for extra in (
        "/usr/local/share/applications",
        "/usr/share/applications",
    ):
        if extra not in candidates:
            candidates.append(extra)
    for apps in candidates:
        if os.path.normpath(apps) == user:
            continue
        cand = os.path.join(apps, desktop_id)
        if os.path.isfile(cand):
            return cand
    return None


def find_any_desktop_path(desktop_id):
    user = os.path.join(USER_APPS_DIR, desktop_id)
    if os.path.isfile(user):
        return user
    return find_system_desktop_path(desktop_id)


def _backup_desktop_if_enabled(path, enabled):
    if not enabled:
        return
    if not path or not os.path.isfile(path):
        raise ApplyError("Backup failed; aborting to avoid an unrecoverable change.")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    base = os.path.basename(path)
    if not is_valid_desktop_id(base):
        raise ApplyError("Backup failed; invalid desktop id.")
    dest = os.path.join(
        BACKUP_DIR,
        f"{base}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}.{os.getpid()}.{os.urandom(2).hex()}",
    )
    try:
        shutil.copy2(path, dest)
    except OSError as e:
        raise ApplyError(f"Backup failed; aborting.\n{e}") from e


def _normalized_desktop_without_main_icon(path):
    """Full .desktop text for comparison, stripping only Icon= in [Desktop Entry].

    Keeps every other section (Desktop Action …, etc.) so Reset never treats
    action customizations as “icon-only” and deletes them.
    """
    if not path or not os.path.isfile(path):
        return None
    out = []
    in_entry = False
    try:
        with open(path, "r", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_entry = stripped == "[Desktop Entry]"
                    out.append(stripped)
                    continue
                if in_entry and stripped.startswith("Icon="):
                    continue
                if stripped.startswith("#"):
                    continue
                # Preserve blank lines as empty markers for structure
                out.append(stripped)
    except OSError:
        return None
    # Drop trailing empties for stable compare
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def user_override_only_differs_by_icon(user_path, system_path):
    """True if user .desktop matches system except Icon= in [Desktop Entry].

    Compares the entire file (all groups). Safe to delete override on Reset only
    when no Desktop Actions or other sections were customized.
    """
    u = _normalized_desktop_without_main_icon(user_path)
    s = _normalized_desktop_without_main_icon(system_path)
    if u is None or s is None:
        return False
    return u == s


# Backup basenames: <desktop_id>.backup.<YYYYMMDDHHMMSS>.<pid>.<suffix>
_BACKUP_NAME_RE = re.compile(
    r"^(.+)\.backup\.(\d{14})\.(\d+)\.([A-Za-z0-9]+)$"
)


def parse_backup_desktop_id(backup_basename):
    """Extract desktop id from a backup basename (handles ids containing '.backup.')."""
    if not backup_basename or os.path.sep in backup_basename or ".." in backup_basename:
        return None
    m = _BACKUP_NAME_RE.match(backup_basename)
    if not m:
        return None
    desktop_id = m.group(1)
    if not is_valid_desktop_id(desktop_id):
        return None
    return desktop_id


def snapshot_user_desktop(desktop_id):
    """Bytes of user override or None if absent — for undo."""
    path = os.path.join(USER_APPS_DIR, desktop_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def restore_user_desktop_snapshot(desktop_id, previous_bytes):
    """Undo helper: restore prior file bytes or remove override."""
    path = os.path.join(USER_APPS_DIR, desktop_id)
    if previous_bytes is None:
        if os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError as e:
                raise ApplyError(f"Could not remove override:\n{e}") from e
        return
    _atomic_write_text(path, previous_bytes.decode("utf-8", errors="replace"))
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass


def is_valid_desktop_id(desktop_id):
    """True if desktop_id is a safe freedesktop basename (no path components)."""
    if not desktop_id or not isinstance(desktop_id, str):
        return False
    if "\n" in desktop_id or "\r" in desktop_id or "\0" in desktop_id:
        return False
    if os.path.sep in desktop_id or (os.path.altsep and os.path.altsep in desktop_id):
        return False
    if "/" in desktop_id or "\\" in desktop_id or ".." in desktop_id:
        return False
    if desktop_id.startswith("."):
        return False
    if not desktop_id.endswith(".desktop"):
        return False
    if os.path.basename(desktop_id) != desktop_id:
        return False
    # Non-empty stem (".desktop" alone is 8 chars)
    if len(desktop_id) <= 8:
        return False
    return True


def path_is_under(path, root):
    """True if path resolves inside root (after realpath)."""
    try:
        real_path = os.path.realpath(path)
        real_root = os.path.realpath(root)
    except OSError:
        return False
    if real_path == real_root:
        return True
    prefix = real_root if real_root.endswith(os.sep) else real_root + os.sep
    return real_path.startswith(prefix)



