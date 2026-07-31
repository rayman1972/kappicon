"""Portable icon-map export/import (zip + JSON). No Qt.

See plan: Overrides-shaped pack — kAppIcon-owned assets + theme-name overrides.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Any

from .desktop import (
    find_any_desktop_path,
    is_valid_desktop_id,
    path_is_under,
    set_desktop_icon_py,
    _atomic_copy_file,
    snapshot_user_desktop,
    _backup_desktop_if_enabled,
)
from .discovery import (
    _icon_looks_like_kappicon_apply,
    scan_user_launcher_overrides,
)
from .icons import (
    install_named_hicolor_asset,
    is_kappicon_icon_name,
    locate_hicolor_icon_file,
    prepare_icon_value,
)
from .lock import ApplyError
from .mutation import apply_icon_to_desktop
from .paths import (
    DATA_DIR,
    LIBRARY_DIR,
    TARGET_DIR,
    THEME_ICON_PREFIX,
    USER_APPS_DIR,
    USER_ICONS_DIR,
)

FORMAT_ID = "kappicon.iconmap"
FORMAT_VERSION = 1
MAX_ENTRIES = 500
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MiB
_SAFE_ASSET_BASENAME = re.compile(r"^[A-Za-z0-9._+-]+$")


class IconMapError(ApplyError):
    """User-facing error for export/import."""


def _read_app_version() -> str:
    for path in (
        os.path.join(os.path.dirname(__file__), "..", "..", "VERSION"),
        os.path.join(DATA_DIR, "VERSION"),
        "/usr/share/doc/kappicon/VERSION",
        "/usr/share/doc/kappicon-git/VERSION",
    ):
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    v = fh.read().strip()
                if v:
                    return v
        except OSError:
            continue
    return "unknown"


def _is_theme_name(icon: str) -> bool:
    icon = (icon or "").strip()
    if not icon:
        return False
    if icon.startswith("file:") or os.path.isabs(icon):
        return False
    if "/" in icon or "\\" in icon:
        return False
    if "\n" in icon or "\r" in icon:
        return False
    return True


def _resolve_asset_source(icon: str) -> str | None:
    """Filesystem path for a kAppIcon-owned Icon= value, or None."""
    icon = (icon or "").strip()
    if not icon:
        return None
    if icon.startswith("file:"):
        path = icon[5:]
        if os.path.isfile(path):
            return os.path.realpath(path)
        return None
    if os.path.isabs(icon) and os.path.isfile(icon):
        return os.path.realpath(icon)
    if is_kappicon_icon_name(icon):
        found = locate_hicolor_icon_file(icon)
        if found:
            return found
        # Staging renders under TARGET_DIR
        for ext in (".png", ".svg", ".svgz"):
            cand = os.path.join(TARGET_DIR, f"{icon}{ext}")
            if os.path.isfile(cand):
                return cand
        cand = os.path.join(LIBRARY_DIR, f"{icon}.png")
        if os.path.isfile(cand):
            return cand
    return None


def _safe_asset_member(basename: str) -> str:
    base = os.path.basename(basename.replace("\\", "/"))
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in (".png", ".svg", ".svgz"):
        ext = ".png"
    safe = "".join(c if c.isalnum() or c in "._+-" else "-" for c in stem).strip(".-") or "icon"
    if not _SAFE_ASSET_BASENAME.match(safe):
        safe = "icon"
    return f"assets/{safe}{ext}"


def build_export_entries(overrides: list[dict] | None = None) -> dict[str, Any]:
    """Classify Overrides rows into pack entries (no zip write).

    Returns dict with keys: entries, skipped, asset_count, theme_count.
    """
    rows = overrides if overrides is not None else scan_user_launcher_overrides()
    entries: list[dict] = []
    skipped: list[dict] = []
    asset_count = 0
    theme_count = 0
    used_members: set[str] = set()

    for row in rows:
        desktop_id = row.get("desktop_id") or ""
        if not is_valid_desktop_id(desktop_id):
            skipped.append({"desktop_id": desktop_id, "reason": "invalid id"})
            continue
        icon = (row.get("icon") or "").strip()
        display = row.get("display") or desktop_id
        if not icon:
            skipped.append({"desktop_id": desktop_id, "reason": "empty Icon="})
            continue

        if _icon_looks_like_kappicon_apply(icon):
            src = _resolve_asset_source(icon)
            if not src or not os.path.isfile(src):
                skipped.append({
                    "desktop_id": desktop_id,
                    "reason": "kAppIcon icon file missing",
                })
                continue
            # Prefer stable kappicon-* name for Icon= in pack
            if is_kappicon_icon_name(icon):
                icon_name = icon
            else:
                # Path-based: use basename stem if already kappicon-like, else derive
                stem = os.path.splitext(os.path.basename(src))[0]
                icon_name = stem if is_kappicon_icon_name(stem) else stem
                # Ensure installable name for import
                if not is_kappicon_icon_name(icon_name):
                    icon_name = f"kappicon-import-{desktop_id.replace('.desktop', '')[:32]}"
                    icon_name = re.sub(r"[^A-Za-z0-9._+-]", "-", icon_name)
            ext = os.path.splitext(src)[1].lower() or ".png"
            member = _safe_asset_member(f"{icon_name}{ext}")
            # Disambiguate collisions
            base_member = member
            n = 2
            while member in used_members:
                stem_m, ext_m = os.path.splitext(base_member)
                member = f"{stem_m}-{n}{ext_m}"
                n += 1
            used_members.add(member)
            entries.append({
                "desktop_id": desktop_id,
                "display": display,
                "icon": icon_name if is_kappicon_icon_name(icon_name) else icon,
                "kind": "asset",
                "asset": member,
                "_source_path": src,
            })
            asset_count += 1
            continue

        if _is_theme_name(icon):
            entries.append({
                "desktop_id": desktop_id,
                "display": display,
                "icon": icon,
                "kind": "theme",
            })
            theme_count += 1
            continue

        skipped.append({
            "desktop_id": desktop_id,
            "reason": "foreign absolute path or unportable Icon=",
        })

    return {
        "entries": entries,
        "skipped": skipped,
        "asset_count": asset_count,
        "theme_count": theme_count,
    }


def export_icon_map(zip_path: str, *, overrides: list[dict] | None = None) -> dict[str, Any]:
    """Write icon-map zip to *zip_path*. Returns summary dict."""
    built = build_export_entries(overrides)
    entries = built["entries"]
    if len(entries) > MAX_ENTRIES:
        raise IconMapError(f"Too many overrides to export (max {MAX_ENTRIES}).")

    manifest_entries = []
    for e in entries:
        me = {
            "desktop_id": e["desktop_id"],
            "display": e.get("display") or e["desktop_id"],
            "icon": e["icon"],
            "kind": e["kind"],
        }
        if e["kind"] == "asset":
            me["asset"] = e["asset"]
        manifest_entries.append(me)

    manifest = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "kappicon_version": _read_app_version(),
        "entries": manifest_entries,
    }
    readme = (
        "kAppIcon icon map\n"
        "=================\n\n"
        "This archive holds launcher icon overrides for import into kAppIcon.\n\n"
        "Import:\n"
        "  1. Open kAppIcon\n"
        "  2. Settings → Icon map (transfer) → Import icon map…\n"
        "  3. Review the preview, then Apply icon map\n\n"
        "Theme-name entries need the same icon themes installed on the target system.\n"
        "Custom kappicon-* icons are embedded under assets/.\n"
    )

    dest = os.path.realpath(zip_path)
    dest_dir = os.path.dirname(dest) or "."
    os.makedirs(dest_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kappicon-map-", suffix=".zip", dir=dest_dir)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("kappicon-map.json", json.dumps(manifest, indent=2) + "\n")
            zf.writestr("README.txt", readme)
            for e in entries:
                if e["kind"] != "asset":
                    continue
                src = e["_source_path"]
                zf.write(src, e["asset"])
        os.replace(tmp, dest)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return {
        "path": dest,
        "count": len(entries),
        "asset_count": built["asset_count"],
        "theme_count": built["theme_count"],
        "skipped": built["skipped"],
        "skipped_count": len(built["skipped"]),
    }


def _validate_zip_member(name: str) -> None:
    if not name or name.startswith("/") or name.startswith("\\"):
        raise IconMapError("Invalid path in icon map archive.")
    # Normalize and reject traversal
    parts = name.replace("\\", "/").split("/")
    if ".." in parts or any(p == "" and False for p in parts):
        raise IconMapError(f"Unsafe path in archive: {name}")
    if any(p == ".." for p in parts):
        raise IconMapError(f"Unsafe path in archive: {name}")
    if name != "kappicon-map.json" and name != "README.txt" and not name.startswith("assets/"):
        # Allow only known roots
        if name not in ("kappicon-map.json", "README.txt"):
            raise IconMapError(f"Unexpected file in archive: {name}")


def _safe_extract_asset(zf: zipfile.ZipFile, member: str, dest_dir: str) -> str:
    """Extract one asset member to dest_dir; return filesystem path."""
    member = member.replace("\\", "/")
    if not member.startswith("assets/") or ".." in member.split("/"):
        raise IconMapError(f"Unsafe asset path: {member}")
    base = os.path.basename(member)
    if not base or base in (".", ".."):
        raise IconMapError(f"Unsafe asset path: {member}")
    stem, ext = os.path.splitext(base)
    if ext.lower() not in (".png", ".svg", ".svgz"):
        raise IconMapError(f"Unsupported asset type: {base}")
    if not re.match(r"^[A-Za-z0-9._+-]+$", stem):
        raise IconMapError(f"Unsafe asset name: {base}")
    try:
        info = zf.getinfo(member)
    except KeyError as e:
        raise IconMapError(f"Missing asset in archive: {member}") from e
    if info.file_size > MAX_UNCOMPRESSED_BYTES:
        raise IconMapError("Asset too large in icon map.")
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, base)
    parent = os.path.realpath(dest_dir)
    out_real = os.path.realpath(out)
    if out_real != out and not path_is_under(out_real, parent):
        # Before write, realpath of non-existent file is parent+name on most OS
        pass
    if os.path.dirname(out_real) != parent and not path_is_under(out_real, parent):
        raise IconMapError("Refusing to extract outside staging directory.")
    with zf.open(member) as src, open(out, "wb") as dst:
        data = src.read()
        if len(data) > MAX_UNCOMPRESSED_BYTES:
            raise IconMapError("Asset too large in icon map.")
        dst.write(data)
    return out


def plan_import(zip_path: str) -> dict[str, Any]:
    """Validate zip and classify entries. No desktop mutations.

    Returns plan with apply / skip lists and extracted asset staging paths
    under a temp dir (caller should not need them until apply_import).
    For apply_import, pass the same zip_path again (re-extracts).
    """
    if not zip_path or not os.path.isfile(zip_path):
        raise IconMapError("Icon map file not found.")

    apply_list: list[dict] = []
    skip_missing: list[dict] = []
    skip_bad: list[dict] = []
    theme_apply = 0
    asset_apply = 0

    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile as e:
        raise IconMapError("Not a valid zip archive.") from e

    with zf:
        names = zf.namelist()
        total_size = 0
        for n in names:
            info = zf.getinfo(n)
            total_size += info.file_size
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise IconMapError("Icon map archive is too large.")
            # Basic zip-slip on member names
            if ".." in n.replace("\\", "/").split("/"):
                raise IconMapError(f"Unsafe path in archive: {n}")
            if n.startswith("/") or n.startswith("\\"):
                raise IconMapError(f"Unsafe path in archive: {n}")

        if "kappicon-map.json" not in names:
            raise IconMapError("Archive is missing kappicon-map.json.")

        try:
            raw = zf.read("kappicon-map.json").decode("utf-8")
            manifest = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise IconMapError("Invalid kappicon-map.json.") from e

        if manifest.get("format") != FORMAT_ID:
            raise IconMapError("This file is not a kAppIcon icon map.")
        ver = manifest.get("version")
        if ver != FORMAT_VERSION:
            raise IconMapError(
                f"Unsupported icon map version {ver!r} (need {FORMAT_VERSION})."
            )
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            raise IconMapError("Icon map has no entries list.")
        if len(entries) > MAX_ENTRIES:
            raise IconMapError(f"Too many entries (max {MAX_ENTRIES}).")

        for ent in entries:
            if not isinstance(ent, dict):
                skip_bad.append({"reason": "invalid entry"})
                continue
            desktop_id = ent.get("desktop_id") or ""
            kind = (ent.get("kind") or "").strip()
            icon = (ent.get("icon") or "").strip()
            display = ent.get("display") or desktop_id
            if not is_valid_desktop_id(desktop_id):
                skip_bad.append({"desktop_id": desktop_id, "reason": "invalid id"})
                continue
            if kind not in ("asset", "theme"):
                skip_bad.append({"desktop_id": desktop_id, "reason": "bad kind"})
                continue
            if not icon or "\n" in icon or "\r" in icon:
                skip_bad.append({"desktop_id": desktop_id, "reason": "bad icon"})
                continue
            if kind == "asset":
                asset = (ent.get("asset") or "").replace("\\", "/")
                if not asset.startswith("assets/") or ".." in asset.split("/"):
                    skip_bad.append({"desktop_id": desktop_id, "reason": "bad asset path"})
                    continue
                if asset not in names:
                    skip_bad.append({"desktop_id": desktop_id, "reason": "missing asset"})
                    continue
            # App present?
            app_path = find_any_desktop_path(desktop_id)
            if not app_path or not os.path.isfile(app_path):
                skip_missing.append({
                    "desktop_id": desktop_id,
                    "display": display,
                    "reason": "app not installed",
                })
                continue
            item = {
                "desktop_id": desktop_id,
                "display": display,
                "icon": icon,
                "kind": kind,
                "asset": ent.get("asset") if kind == "asset" else None,
            }
            apply_list.append(item)
            if kind == "theme":
                theme_apply += 1
            else:
                asset_apply += 1

    return {
        "zip_path": os.path.realpath(zip_path),
        "apply": apply_list,
        "skip_missing": skip_missing,
        "skip_bad": skip_bad,
        "theme_count": theme_apply,
        "asset_count": asset_apply,
        "apply_count": len(apply_list),
        "kappicon_version": manifest.get("kappicon_version"),
        "exported_at": manifest.get("exported_at"),
    }


def apply_import_plan(
    plan: dict[str, Any],
    *,
    backup: bool = False,
    shape: str = "as-is",
) -> dict[str, Any]:
    """Apply a plan from plan_import. Caller must hold apply_lock.

    Returns summary with applied, failed, previous_bytes list for undo.
    """
    zip_path = plan.get("zip_path")
    if not zip_path or not os.path.isfile(zip_path):
        raise IconMapError("Icon map file not found.")

    applied: list[dict] = []
    failed: list[dict] = []
    undo_entries: list[dict] = []

    staging = tempfile.mkdtemp(prefix="kappicon-import-")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for item in plan.get("apply") or []:
                desktop_id = item["desktop_id"]
                kind = item["kind"]
                icon = item["icon"]
                display = item.get("display") or desktop_id
                try:
                    previous_bytes = snapshot_user_desktop(desktop_id)
                    if kind == "theme":
                        result = apply_icon_to_desktop(
                            desktop_id,
                            f"{THEME_ICON_PREFIX}{icon}",
                            shape=shape,
                            backup=backup,
                        )
                        icon_value = result.get("icon_value") or icon
                    else:
                        member = item.get("asset") or ""
                        asset_path = _safe_extract_asset(zf, member, staging)
                        # Preserve pack icon name when valid kappicon-*
                        if is_kappicon_icon_name(icon):
                            install_named_hicolor_asset(asset_path, icon)
                            user_path = os.path.join(USER_APPS_DIR, desktop_id)
                            app_path = find_any_desktop_path(desktop_id)
                            if not app_path:
                                raise ApplyError(f"Missing desktop: {desktop_id}")
                            _backup_desktop_if_enabled(
                                user_path if os.path.isfile(user_path) else app_path,
                                backup,
                            )
                            if app_path != user_path:
                                from .desktop import _atomic_copy_file as acopy
                                acopy(app_path, user_path)
                            set_desktop_icon_py(user_path, icon)
                            icon_value = icon
                        else:
                            result = apply_icon_to_desktop(
                                desktop_id,
                                asset_path,
                                shape=shape,
                                backup=backup,
                            )
                            icon_value = result.get("icon_value") or icon
                    applied.append({
                        "desktop_id": desktop_id,
                        "display": display,
                        "icon_value": icon_value,
                    })
                    undo_entries.append({
                        "desktop_id": desktop_id,
                        "display": display,
                        "previous_bytes": previous_bytes,
                    })
                except Exception as e:
                    failed.append({
                        "desktop_id": desktop_id,
                        "display": display,
                        "error": str(e),
                    })
    finally:
        # Best-effort cleanup of staging
        try:
            for root, _dirs, files in os.walk(staging, topdown=False):
                for f in files:
                    try:
                        os.unlink(os.path.join(root, f))
                    except OSError:
                        pass
                try:
                    os.rmdir(root)
                except OSError:
                    pass
        except OSError:
            pass

    return {
        "applied": applied,
        "failed": failed,
        "applied_count": len(applied),
        "failed_count": len(failed),
        "undo_entries": undo_entries,
    }
