"""Icon prepare/install/prune (no Qt)."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile

from .desktop import (
    _atomic_copy_file,
    is_valid_desktop_id,
    read_desktop_icon_value,
)
from .lock import ApplyError
from .paths import (
    BACKUP_DIR,
    TARGET_DIR,
    THEME_ICON_PREFIX,
    USER_APPS_DIR,
    USER_ICONS_DIR,
)

def find_magick_cmd():
    for name in ("magick", "convert"):
        if shutil.which(name):
            return name
    return None


def _render_icon_png(src, out_path, shape, magick):
    size = 512
    radius = 96
    half = size // 2
    work = tempfile.mkdtemp(prefix="kappicon-render-")
    try:
        tmp = os.path.join(work, "base.png")
        staged = os.path.join(work, "out.png")
        r = subprocess.run(
            [
                magick, src, "-background", "none", "-alpha", "set",
                "-resize", f"{size}x{size}", "-gravity", "center",
                "-extent", f"{size}x{size}", tmp,
            ],
            capture_output=True,
        )
        if r.returncode != 0 or not os.path.isfile(tmp):
            raise ApplyError("Could not process this image.")
        shape = (shape or "as-is").lower().strip()
        if shape == "circle":
            r = subprocess.run(
                [
                    magick, tmp,
                    "(", "+clone", "-threshold", "-1", "-negate", "-fill", "white",
                    "-draw", f"circle {half},{half} {half},0", ")",
                    "-alpha", "off", "-compose", "copy_opacity", "-composite", staged,
                ],
                capture_output=True,
            )
        elif shape == "rounded":
            r = subprocess.run(
                [
                    magick, tmp,
                    "(", "-size", f"{size}x{size}", "xc:none", "-fill", "white",
                    "-draw",
                    f"roundrectangle 0,0 {size - 1},{size - 1} {radius},{radius}",
                    ")",
                    "-compose", "DstIn", "-composite", staged,
                ],
                capture_output=True,
            )
        else:
            shutil.copy2(tmp, staged)
            r = type("R", (), {"returncode": 0})()
        if getattr(r, "returncode", 1) != 0 or not os.path.isfile(staged) or os.path.getsize(staged) == 0:
            raise ApplyError(f"Could not process this image (shape: {shape}).")
        _atomic_copy_file(staged, out_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _safe_label_from_desktop_id(desktop_id):
    """Human-readable fragment only (not unique — pair with id hash)."""
    base = desktop_id[:-8] if desktop_id.endswith(".desktop") else desktop_id
    cleaned = "".join(c if c.isalnum() or c in "._+-" else "_" for c in base)
    cleaned = cleaned.strip("_") or "app"
    return cleaned[:48]


def _file_sha256(path, extra=b""):
    h = hashlib.sha256()
    if extra:
        h.update(extra)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def kappicon_theme_name(desktop_id, source_path, shape="as-is"):
    """Collision-resistant, content-addressed Icon= name for custom assets.

    - desktop-id hash prevents foo_bar vs foo bar collisions
    - content+shape hash means re-applying a new image never overwrites the
      previous asset, so Undo of Icon= still resolves the old pixmap
    """
    if not is_valid_desktop_id(desktop_id):
        raise ApplyError(f"Invalid application id:\n{desktop_id}")
    label = _safe_label_from_desktop_id(desktop_id)
    id_hash = hashlib.sha256(desktop_id.encode("utf-8")).hexdigest()[:10]
    shape = (shape or "as-is").lower().strip()
    content = _file_sha256(
        source_path,
        extra=f"{shape}\0{desktop_id}".encode("utf-8"),
    )[:12]
    return f"kappicon-{label}-{id_hash}-{content}"


def is_kappicon_icon_name(name):
    """True if Icon= looks like a kAppIcon-managed hicolor asset."""
    if not name or not isinstance(name, str):
        return False
    return bool(re.match(r"^kappicon-[A-Za-z0-9._+-]+$", name.strip()))


def _install_hicolor_icon(icon_path, theme_name, magick):
    """Install custom file into user hicolor; return freedesktop icon name."""
    if not theme_name or any(c in theme_name for c in "/\\\n\r"):
        raise ApplyError("Invalid theme icon name for install.")
    hicolor = os.path.join(USER_ICONS_DIR, "hicolor")
    ext = os.path.splitext(icon_path)[1].lower().lstrip(".")
    if ext in ("svg", "svgz"):
        dest_dir = os.path.join(hicolor, "scalable", "apps")
        dest = os.path.join(dest_dir, f"{theme_name}.{ext}")
        _atomic_copy_file(icon_path, dest)
        return theme_name
    if not magick:
        raise ApplyError("ImageMagick is not installed (need magick or convert).")
    for sz in (512, 256, 128, 64, 48):
        dest_dir = os.path.join(hicolor, f"{sz}x{sz}", "apps")
        dest = os.path.join(dest_dir, f"{theme_name}.png")
        if sz == 512:
            _atomic_copy_file(icon_path, dest)
        else:
            os.makedirs(dest_dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".kappicon-", suffix=".png", dir=dest_dir)
            os.close(fd)
            try:
                r = subprocess.run(
                    [magick, icon_path, "-background", "none", "-resize", f"{sz}x{sz}", tmp],
                    capture_output=True,
                )
                if r.returncode != 0 or not os.path.isfile(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    continue
                os.chmod(tmp, 0o644)
                os.replace(tmp, dest)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    if not os.path.isfile(os.path.join(hicolor, "512x512", "apps", f"{theme_name}.png")):
        raise ApplyError("Failed to install icon into the hicolor theme.")
    return theme_name


def prepare_icon_value(selected_icon, desktop_id, shape="as-is"):
    """Resolve selection to Icon= value (theme name or installed hicolor name)."""
    if not selected_icon or selected_icon == "RESET":
        raise ApplyError("No icon selected.")
    shape = (shape or "as-is").lower().strip()
    if shape not in ("as-is", "square", "rounded", "circle"):
        shape = "as-is"
    magick = find_magick_cmd()

    if isinstance(selected_icon, str) and selected_icon.startswith(THEME_ICON_PREFIX):
        name = selected_icon[len(THEME_ICON_PREFIX):]
        if not name or any(c in name for c in "/\\\n\r"):
            raise ApplyError("Invalid theme icon name.")
        return name  # pure theme name — fidelity preserved

    path = selected_icon
    if not os.path.isfile(path):
        raise ApplyError(f"Icon file not found:\n{path}")
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        raise ApplyError(f"Icon file not found after resolving symlink:\n{path}")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    # Content-addressed name so Undo never points at an overwritten asset
    theme_name = kappicon_theme_name(desktop_id, path, shape=shape)
    # Staging render under TARGET_DIR (unique per theme_name)
    png_out = os.path.join(TARGET_DIR, f"{theme_name}.png")

    # As designed + SVG: keep vector (install scalable under theme_name)
    if shape == "as-is" and ext in ("svg", "svgz"):
        icon_file = path
    else:
        if not magick and ext not in ("png",):
            if ext != "png" or shape not in ("as-is", "square"):
                raise ApplyError("ImageMagick is not installed (need magick or convert).")
        work = tempfile.mkdtemp(prefix="kappicon-src-")
        try:
            src_copy = os.path.join(work, f"source.{ext}")
            shutil.copy2(path, src_copy)
            raster_src = src_copy
            if ext == "icns":
                if not shutil.which("icns2png"):
                    raise ApplyError(
                        "icns2png is not installed (package: libicns / icnsutils)."
                    )
                subprocess.run(
                    ["icns2png", "-x", src_copy],
                    cwd=work, capture_output=True,
                )
                pngs = []
                for name in os.listdir(work):
                    if name.endswith(".png"):
                        pngs.append(os.path.join(work, name))
                if not pngs:
                    raise ApplyError("Could not extract a valid PNG from this .icns file.")
                pngs.sort(key=lambda p: os.path.getsize(p), reverse=True)
                raster_src = pngs[0]
            elif ext not in (
                "png", "jpg", "jpeg", "webp", "bmp", "gif", "xpm", "svg", "svgz"
            ):
                raise ApplyError(
                    f"Unsupported file type: .{ext}\nUse PNG, JPG, WEBP, SVG, or ICNS."
                )
            if shape == "as-is" and ext == "png" and not magick:
                shutil.copy2(raster_src, png_out)
            else:
                if not magick:
                    raise ApplyError("ImageMagick is not installed (need magick or convert).")
                _render_icon_png(raster_src, png_out, shape, magick)
            icon_file = png_out
        finally:
            shutil.rmtree(work, ignore_errors=True)

    return _install_hicolor_icon(icon_file, theme_name, magick)


def collect_referenced_kappicon_names():
    """Icon= names starting with kappicon- still referenced by launchers or backups."""
    refs = set()

    def _add_from_desktop_file(path):
        icon = read_desktop_icon_value(path)
        if icon and is_kappicon_icon_name(icon):
            refs.add(icon.strip())

    if os.path.isdir(USER_APPS_DIR):
        try:
            names = os.listdir(USER_APPS_DIR)
        except OSError:
            names = []
        for name in names:
            if not is_valid_desktop_id(name):
                continue
            _add_from_desktop_file(os.path.join(USER_APPS_DIR, name))

    # Backups must keep their assets: restore can revive an old Icon= after Undo ages out
    if os.path.isdir(BACKUP_DIR):
        try:
            bnames = os.listdir(BACKUP_DIR)
        except OSError:
            bnames = []
        for name in bnames:
            if ".backup." not in name or os.path.sep in name or ".." in name:
                continue
            path = os.path.join(BACKUP_DIR, name)
            if os.path.isfile(path):
                _add_from_desktop_file(path)
    return refs


def prune_unreferenced_kappicon_assets(extra_keep=None):
    """Remove kappicon-* assets not referenced by launchers, backups, or extra_keep.

    Caller must hold apply_lock() so a concurrent apply cannot install an asset
    that is not yet written to a launcher while we delete it.
    """
    keep = set(collect_referenced_kappicon_names())
    if extra_keep:
        for n in extra_keep:
            if n and is_kappicon_icon_name(n):
                keep.add(n.strip())
    hicolor = os.path.join(USER_ICONS_DIR, "hicolor")
    removed = 0
    search_dirs = []
    if os.path.isdir(hicolor):
        try:
            for entry in os.listdir(hicolor):
                apps = os.path.join(hicolor, entry, "apps")
                if os.path.isdir(apps):
                    search_dirs.append(apps)
        except OSError:
            pass
    if os.path.isdir(TARGET_DIR):
        search_dirs.append(TARGET_DIR)
    for apps in search_dirs:
        try:
            files = os.listdir(apps)
        except OSError:
            continue
        for fn in files:
            base, ext = os.path.splitext(fn)
            if not is_kappicon_icon_name(base):
                continue
            if base in keep:
                continue
            path = os.path.join(apps, fn)
            if not os.path.isfile(path):
                continue
            try:
                os.unlink(path)
                removed += 1
            except OSError:
                pass
    return removed



