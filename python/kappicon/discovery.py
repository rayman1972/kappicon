"""Non-Qt discovery helpers for launchers and themes."""
from __future__ import annotations

import os
import re

from .desktop import is_valid_desktop_id, path_is_under, read_desktop_icon_value
from .paths import USER_APPS_DIR, USER_ICONS_DIR


def icon_resolves(icon_name):
    """Best-effort icon resolvability without Qt (GUI may override with QIcon)."""
    if not icon_name or not isinstance(icon_name, str):
        return False
    name = icon_name.strip()
    if not name:
        return False
    if name.startswith(("/", "http://", "https://", "file:", "data:")):
        return os.path.isfile(name) if name.startswith("/") else True
    if os.path.sep in name or (os.path.altsep and os.path.altsep in name):
        return os.path.isfile(name)
    # Theme name: cannot fully resolve without Qt; treat non-empty as potentially OK
    return True

def collect_system_icons(app_data):
    """Unique theme icon names already used by installed apps, with sources."""
    by_icon = {}
    for desktop_name, icon_name in app_data:
        if not icon_name:
            continue
        # Skip absolute paths / URIs — those aren't theme names
        if icon_name.startswith(("/", "http://", "https://", "data:", "file:")):
            continue
        if os.path.isabs(icon_name) or os.path.sep in icon_name:
            continue
        by_icon.setdefault(icon_name, []).append(desktop_name)
    return sorted(by_icon.items(), key=lambda kv: kv[0].lower())


THEME_ICON_FILE_EXTS = {".png", ".svg", ".svgz", ".xpm", ".jpg", ".jpeg", ".webp"}
# Prefer larger / scalable assets when a theme ships multiple sizes of the same name
_THEME_SIZE_SCORE = {
    "scalable": 1000,
    "512x512": 512, "512": 512,
    "256x256": 256, "256": 256,
    "128x128": 128, "128": 128,
    "96x96": 96, "96": 96,
    "72x72": 72, "72": 72,
    "64x64": 64, "64": 64,
    "48x48": 48, "48": 48,
    "32x32": 32, "32": 32,
    "24x24": 24, "24": 24,
    "22x22": 22, "22": 22,
    "16x16": 16, "16": 16,
    "symbolic": 10,
}


def _theme_index_name(theme_dir):
    """Human-readable Name= from index.theme, if present."""
    index = os.path.join(theme_dir, "index.theme")
    if not os.path.isfile(index):
        return None
    try:
        with open(index, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Name=") and not line.startswith("Name["):
                    return line.split("=", 1)[1].strip() or None
    except OSError:
        pass
    return None


def _is_cursor_theme(theme_dir, folder_name):
    low = folder_name.lower()
    if "cursor" in low:
        return True
    # Cursor themes often only have cursors/ and index.theme
    try:
        entries = set(os.listdir(theme_dir))
    except OSError:
        return True
    meaningful = entries - {"index.theme", "icon-theme.cache", "cursors", "cursor.theme"}
    if "cursors" in entries and not any(
        os.path.isdir(os.path.join(theme_dir, e)) and e not in ("cursors",)
        for e in meaningful
    ):
        return True
    return False


def discover_icon_themes():
    """Installed icon themes (custom + system), newest user themes first.

    Returns list of dicts: {id, name, path, is_user}
    """
    roots = [
        (USER_ICONS_DIR, True),
        (os.path.expanduser("~/.icons"), True),  # legacy user location
    ]
    # System + extra data roots from XDG_DATA_DIRS
    for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        d = d.strip()
        if d:
            roots.append((os.path.join(d, "icons"), False))
    # Flatpak: host OS share is mounted under /run/host
    if os.environ.get("FLATPAK_ID"):
        for d in ("/run/host/usr/share", "/run/host/usr/local/share"):
            roots.append((os.path.join(d, "icons"), False))

    # Deduplicate while preserving order
    _seen_roots = set()
    _uniq_roots = []
    for root, is_user in roots:
        real = os.path.realpath(root) if os.path.isdir(root) else root
        if real in _seen_roots:
            continue
        _seen_roots.add(real)
        _uniq_roots.append((root, is_user))
    roots = _uniq_roots
    seen_paths = set()
    themes = []
    for root, is_user in roots:
        if not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for folder in names:
            path = os.path.join(root, folder)
            if not os.path.isdir(path):
                continue
            real = os.path.realpath(path)
            if real in seen_paths:
                continue
            if _is_cursor_theme(path, folder):
                continue
            # Prefer themes with index.theme or an apps/ tree
            has_index = os.path.isfile(os.path.join(path, "index.theme"))
            has_apps = False
            try:
                for dirpath, dirnames, _files in os.walk(path):
                    base = os.path.basename(dirpath).lower()
                    if base in ("apps", "applications"):
                        has_apps = True
                        break
                    # Don't descend forever into huge trees for detection
                    if dirpath.count(os.sep) - path.count(os.sep) > 3:
                        dirnames.clear()
            except OSError:
                pass
            if not has_index and not has_apps:
                continue
            seen_paths.add(real)
            display = _theme_index_name(path) or folder
            themes.append({
                "id": folder,
                "name": display,
                "path": path,
                "is_user": is_user,
            })
    # User themes first, then A–Z by display name
    themes.sort(key=lambda t: (0 if t["is_user"] else 1, t["name"].lower()))
    return themes


def _path_size_score(dirpath):
    parts = dirpath.replace("\\", "/").split("/")
    score = 0
    for p in parts:
        pl = p.lower()
        if pl in _THEME_SIZE_SCORE:
            score = max(score, _THEME_SIZE_SCORE[pl])
        # "48" style
        if pl.isdigit():
            score = max(score, int(pl))
    return score


def scan_theme_icons(theme_path, contexts=None):
    """Icons in a theme pack. Returns [(icon_name, best_file_path), ...].

    Focuses on application icons by default (apps / applications).

    Supports both common layouts:
      - Theme/48x48/apps/foo.png   (Breeze, Tela, …)
      - Theme/apps/scalable/foo.svg (WhiteSur, McMojave, …)

    Follows directory symlinks (e.g. WhiteSur-dark/apps/scalable → WhiteSur/…).
    """
    if contexts is None:
        contexts = {"apps", "applications"}
    best = {}  # name -> (score, path)
    if not theme_path or not os.path.isdir(theme_path):
        return []

    visited = set()
    try:
        walker = os.walk(theme_path, followlinks=True)
    except OSError:
        return []

    for dirpath, dirnames, filenames in walker:
        try:
            real_dir = os.path.realpath(dirpath)
        except OSError:
            continue
        # Avoid cycles when following @2x / inheritance symlinks
        if real_dir in visited:
            dirnames[:] = []
            continue
        visited.add(real_dir)

        norm = dirpath.replace("\\", "/")
        low_parts = [p.lower() for p in norm.split("/") if p]
        if "cursors" in low_parts:
            dirnames[:] = []
            continue

        # Context may be any path component (…/apps/32, …/48x48/apps, or …/apps@2x/…)
        # WhiteSur uses apps@2x → apps symlinks; strip the @scale suffix.
        def _context_key(part: str) -> str:
            return part.split("@", 1)[0]

        if not any(_context_key(p) in contexts for p in low_parts):
            continue

        size_score = _path_size_score(dirpath)
        # WhiteSur-style: Theme/apps/scalable → basename is scalable (scored);
        # Theme/apps/32 → basename is 32 (scored as int in _path_size_score).
        for fname in filenames:
            root, ext = os.path.splitext(fname)
            if ext.lower() not in THEME_ICON_FILE_EXTS:
                continue
            if not root or root.endswith("@2x"):
                continue
            score = size_score
            # Prefer full-color over symbolic variants
            if root.endswith("-symbolic") or "symbolic" in low_parts:
                score -= 50
            path = os.path.join(dirpath, fname)
            prev = best.get(root)
            if prev is None or score > prev[0]:
                best[root] = (score, path)

    items = [(name, path) for name, (_s, path) in best.items()]
    items.sort(key=lambda t: t[0].lower())
    return items


def parse_desktop_fields(desktop_file):
    """Return (Name, Icon) from a .desktop file. Name prefers unlocalized Name=."""
    name = None
    name_en = None
    icon = None
    in_desktop_entry = False
    try:
        with open(desktop_file, "r", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    if line == "[Desktop Entry]":
                        in_desktop_entry = True
                    else:
                        in_desktop_entry = False
                        if (name or name_en) and icon:
                            break
                    continue
                if not in_desktop_entry:
                    continue
                if line.startswith("Name[en") and "=" in line and name_en is None:
                    name_en = line.split("=", 1)[1].strip()
                elif line.startswith("Name=") and name is None:
                    name = line.split("=", 1)[1].strip()
                elif line.startswith("Icon=") and icon is None:
                    val = line.split("=", 1)[1].strip()
                    if val and not val.startswith(("http://", "https://", "ftp://", "data:")):
                        if "?" not in val and "#" not in val:
                            icon = val
    except Exception:
        pass
    display = name or name_en or os.path.splitext(os.path.basename(desktop_file))[0]
    return display, icon


def parse_icon_name(desktop_file):
    _, icon = parse_desktop_fields(desktop_file)
    return icon


def friendly_desktop_label(desktop_basename, desktop_path_lookup):
    """Human label for a .desktop basename using a path map if available."""
    path = desktop_path_lookup.get(desktop_basename)
    if path:
        name, _ = parse_desktop_fields(path)
        return name
    return os.path.splitext(desktop_basename)[0]


def pick_primary_provider(desktops):
    """Choose the most representative .desktop that uses a shared theme icon."""
    if not desktops:
        return None
    def score(d):
        low = d.lower()
        s = 0
        if any(x in low for x in ("urlhandler", "handler", "autostart")):
            s -= 8
        if any(x in low for x in (".flatpak", ".snap", "solid_action")):
            s -= 3
        # Prefer shorter, “main” ids
        s -= low.count(".")
        s -= len(low) // 20
        return s
    return sorted(desktops, key=score, reverse=True)[0]


def _system_desktop_roots():
    """Directories that may hold system (non-user) .desktop files."""
    roots = []
    user_dir = os.path.normpath(USER_APPS_DIR)
    for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        d = d.strip()
        if not d:
            continue
        apps = os.path.join(d, "applications")
        if os.path.isdir(apps) and os.path.normpath(apps) != user_dir:
            roots.append(apps)
    for apps in (
        "/usr/share/applications",
        "/usr/local/share/applications",
        "/run/host/usr/share/applications",
        "/run/host/usr/local/share/applications",
        "/var/lib/flatpak/exports/share/applications",
    ):
        if os.path.isdir(apps) and os.path.normpath(apps) != user_dir:
            roots.append(apps)
    # DESKTOP_LIST entries: full file paths
    for fp in os.environ.get("DESKTOP_LIST", "").split("\n"):
        fp = fp.strip()
        if not fp or not os.path.isfile(fp):
            continue
        d = os.path.dirname(fp)
        if os.path.normpath(d) != user_dir and d not in roots:
            roots.append(d)
    # unique preserve order
    seen = set()
    out = []
    for r in roots:
        nr = os.path.normpath(r)
        if nr not in seen:
            seen.add(nr)
            out.append(r)
    return out


def _icon_looks_like_kappicon_apply(icon):
    """True if Icon= is clearly from kAppIcon (theme name or render path)."""
    if not icon:
        return False
    icon = str(icon).strip()
    if icon.startswith("kappicon-"):
        return True
    # Absolute / file: path under our data or Pictures render dir
    path = icon[5:] if icon.startswith("file:") else icon
    if not os.path.isabs(path):
        return False
    try:
        real = os.path.realpath(path)
    except OSError:
        real = path
    for root in (DATA_DIR, TARGET_DIR, LIBRARY_DIR):
        try:
            if path_is_under(real, root):
                return True
        except Exception:
            pass
    # Common default even if TARGET_DIR env differs mid-session
    pictures_k = os.path.join(os.path.expanduser("~"), "Pictures", "KAppIcon")
    try:
        if path_is_under(real, pictures_k):
            return True
    except Exception:
        pass
    return False


def _is_icon_override(icon, system_icon, system_path):
    """
    Only treat as an icon override we care about:
    - System launcher exists and Icon= differs, or
    - Icon= was applied by kAppIcon (kappicon-* name / our paths).

    Skip Steam/game shortcuts and other user-only .desktop files that are
    not icon customizations of a system app.
    """
    icon = (icon or "").strip()
    system_icon = (system_icon or "").strip()
    if _icon_looks_like_kappicon_apply(icon):
        return True
    if not system_path:
        return False
    # System app with a different Icon= (customized theme name or file)
    if icon != system_icon:
        return True
    return False


def scan_user_launcher_overrides():
    """User .desktop files that customize icons (not every Steam shortcut)."""
    rows = []
    user_dir = USER_APPS_DIR
    if not os.path.isdir(user_dir):
        return rows
    try:
        names = sorted(os.listdir(user_dir))
    except OSError:
        return rows
    sys_roots = _system_desktop_roots()
    skip_ids = {
        "kappicon.desktop",
        "io.github.rayman1972.kappicon.desktop",
    }
    for name in names:
        if not is_valid_desktop_id(name):
            continue
        if name in skip_ids:
            continue
        # Steam / Proton helpers: user-only game launchers, not icon overrides
        low = name.lower()
        if low.startswith("steam_app") or low.startswith("steam."):
            continue
        path = os.path.join(user_dir, name)
        if not os.path.isfile(path):
            continue
        display, icon = parse_desktop_fields(path)
        system_path = None
        system_icon = None
        for root in sys_roots:
            cand = os.path.join(root, name)
            if os.path.isfile(cand):
                system_path = cand
                _, system_icon = parse_desktop_fields(cand)
                break
        if not _is_icon_override(icon, system_icon, system_path):
            continue
        rows.append({
            "desktop_id": name,
            "path": path,
            "display": display or name,
            "icon": icon or "",
            "system_icon": system_icon or "",
            "system_path": system_path,
            "icon_ok": icon_resolves(icon) if icon else False,
        })
    return rows


def _desktop_bool(value):
    return (value or "").strip().lower() in ("1", "true", "yes")


def _current_desktop_envs():
    """Set of desktop ids from XDG_CURRENT_DESKTOP (colon-separated)."""
    raw = os.environ.get("XDG_CURRENT_DESKTOP") or ""
    return {e.strip() for e in raw.split(":") if e.strip()}


def parse_desktop_launcher_meta(desktop_file):
    """Fields needed to decide if a .desktop is a visible, user-runnable launcher.

    Returns dict with keys: type, no_display, hidden, only_show_in, not_show_in,
    exec, dbus_activatable, icon, name.
    """
    meta = {
        "type": "Application",
        "no_display": False,
        "hidden": False,
        "only_show_in": "",
        "not_show_in": "",
        "exec": "",
        "dbus_activatable": False,
        "icon": None,
        "name": None,
        "name_en": None,
    }
    in_entry = False
    try:
        with open(desktop_file, "r", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if not in_entry or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                val = val.strip()
                if key == "Type" and not meta.get("_type_set"):
                    meta["type"] = val or "Application"
                    meta["_type_set"] = True
                elif key == "NoDisplay":
                    meta["no_display"] = _desktop_bool(val)
                elif key == "Hidden":
                    meta["hidden"] = _desktop_bool(val)
                elif key == "OnlyShowIn" and not meta["only_show_in"]:
                    meta["only_show_in"] = val
                elif key == "NotShowIn" and not meta["not_show_in"]:
                    meta["not_show_in"] = val
                elif key == "Exec" and not meta["exec"]:
                    meta["exec"] = val
                elif key == "DBusActivatable":
                    meta["dbus_activatable"] = _desktop_bool(val)
                elif key == "Icon" and meta["icon"] is None:
                    if val and not val.startswith(("http://", "https://", "ftp://", "data:")):
                        if "?" not in val and "#" not in val:
                            meta["icon"] = val
                elif key == "Name" and meta["name"] is None:
                    meta["name"] = val
                elif key.startswith("Name[en") and meta["name_en"] is None:
                    meta["name_en"] = val
    except OSError:
        pass
    meta.pop("_type_set", None)
    return meta


def is_visible_user_launcher(desktop_file, meta=None):
    """True if this .desktop should appear as a normal runnable app in menus.

    Skips NoDisplay/Hidden helpers, non-Application types, entries with no
    Exec/DBusActivatable, and apps excluded by OnlyShowIn/NotShowIn for the
    current desktop environment.
    """
    if meta is None:
        meta = parse_desktop_launcher_meta(desktop_file)
    if (meta.get("type") or "Application") != "Application":
        return False
    if meta.get("no_display") or meta.get("hidden"):
        return False
    if not (meta.get("exec") or "").strip() and not meta.get("dbus_activatable"):
        return False
    envs = _current_desktop_envs()
    not_show = meta.get("not_show_in") or ""
    if not_show and envs:
        banned = {e.strip() for e in not_show.split(";") if e.strip()}
        if envs & banned:
            return False
    only = meta.get("only_show_in") or ""
    if only and envs:
        allowed = {e.strip() for e in only.split(";") if e.strip()}
        if allowed and not (envs & allowed):
            return False
    return True


def scan_apps_missing_icons(app_data):
    """Visible, user-runnable apps whose Icon= is empty or does not resolve.

    Hidden helpers (NoDisplay/Hidden), non-Application entries, and apps not
    meant for this desktop are omitted — empty icons there are usually intentional.
    """
    rows = []
    for desktop_id, icon_name, display_name, path in app_data:
        if not is_valid_desktop_id(desktop_id):
            continue
        if not path or not os.path.isfile(path):
            continue
        meta = parse_desktop_launcher_meta(path)
        if not is_visible_user_launcher(path, meta=meta):
            continue
        # Prefer Icon from the file we just read (same as app_data in practice)
        icon = icon_name if icon_name is not None else meta.get("icon")
        if icon_resolves(icon):
            continue
        display = display_name or meta.get("name") or meta.get("name_en") or desktop_id
        rows.append({
            "desktop_id": desktop_id,
            "path": path,
            "display": display,
            "icon": icon or "",
            "reason": "No Icon=" if not (icon or "").strip() else "Icon not found",
        })
    rows.sort(key=lambda r: (r["display"] or "").lower())
    return rows


# ── Icon editor (pixel canvas + image import) ────────────────────────────

