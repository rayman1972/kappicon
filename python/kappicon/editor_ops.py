"""Pure QImage prep ops for the Create tab (no Qt widgets).

All functions return a new ARGB32 image; callers own undo history.
Kept free of UI so they can be unit-tested without a display.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QImage, QPainter, QTransform


def _as_argb(img: QImage) -> QImage:
    if img.isNull():
        return img
    return img.convertToFormat(QImage.Format.Format_ARGB32)


# ── Import quality helpers (low-resolution sources) ─────────────────────

# Below this max side, treat the source as low-res for icons (needs help).
LOW_RES_MAX_SIDE = 128
# Softer warning band: small but usable with care.
MODEST_RES_MAX_SIDE = 256


def source_max_side(img: QImage) -> int:
    if img is None or img.isNull():
        return 0
    return max(img.width(), img.height())


def is_low_resolution(img: QImage, threshold: int = LOW_RES_MAX_SIDE) -> bool:
    """True when the longest side is below *threshold* (default 128)."""
    return source_max_side(img) > 0 and source_max_side(img) < int(threshold)


def is_modest_resolution(img: QImage) -> bool:
    """True for sources under 256px — still a bit small for crisp 512 icons."""
    side = source_max_side(img)
    return 0 < side < MODEST_RES_MAX_SIDE


def recommended_scale_mode(img: QImage) -> str:
    """'crisp' for small sources (avoids blurry soft-upscale); else 'smooth'."""
    return "crisp" if is_modest_resolution(img) else "smooth"


def max_integer_scale(src_w: int, src_h: int, canvas: int) -> int:
    """Largest integer N such that N·src fits inside canvas×canvas."""
    if src_w < 1 or src_h < 1 or canvas < 1:
        return 1
    return max(1, min(int(canvas) // int(src_w), int(canvas) // int(src_h)))


def import_quality_hint(img: QImage, canvas: int = 512) -> str:
    """Short user-facing tip for the import dialog (empty if source is fine)."""
    if img is None or img.isNull():
        return ""
    w, h = img.width(), img.height()
    side = max(w, h)
    if side >= MODEST_RES_MAX_SIDE:
        return ""
    n = max_integer_scale(w, h, canvas)
    if side < LOW_RES_MAX_SIDE:
        return (
            f"Small source ({w}×{h}). Soft upscaling will look blurry — "
            f"use Crisp scaling and integer zoom (e.g. ×{n}), then Pad on the canvas. "
            f"A {MODEST_RES_MAX_SIDE}×{MODEST_RES_MAX_SIDE}+ image is ideal for launcher icons."
        )
    return (
        f"Modest source ({w}×{h}). Prefer Crisp scaling so edges stay sharp; "
        f"integer ×{n} fills the canvas without fractional stretch."
    )


def upscale_nearest(img: QImage, target_w: int, target_h: int | None = None) -> QImage:
    """Nearest-neighbor resize (keeps pixel-art edges)."""
    img = _as_argb(img)
    if img.isNull():
        return img
    tw = max(1, int(target_w))
    th = max(1, int(target_h if target_h is not None else target_w))
    return img.scaled(
        tw, th,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    ).convertToFormat(QImage.Format.Format_ARGB32)


def content_bbox(img: QImage, alpha_threshold: int = 8) -> QRect | None:
    """Tight rectangle of pixels with alpha > threshold, or None if blank."""
    img = _as_argb(img)
    w, h = img.width(), img.height()
    if w < 1 or h < 1:
        return None
    min_x, min_y = w, h
    max_x, max_y = -1, -1
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() > alpha_threshold:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return None
    return QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def flip_horizontal(img: QImage) -> QImage:
    img = _as_argb(img)
    return img.mirrored(True, False)


def flip_vertical(img: QImage) -> QImage:
    img = _as_argb(img)
    return img.mirrored(False, True)


def rotate_90(img: QImage, clockwise: bool = True) -> QImage:
    """Rotate 90°; canvas stays square (same side length)."""
    img = _as_argb(img)
    t = QTransform()
    t.rotate(90 if clockwise else -90)
    out = img.transformed(t, Qt.TransformationMode.FastTransformation)
    return _as_argb(out)


def center_content(img: QImage, alpha_threshold: int = 8) -> QImage:
    """Re-center opaque content on a same-size transparent canvas."""
    img = _as_argb(img)
    box = content_bbox(img, alpha_threshold)
    if box is None:
        return img.copy()
    w, h = img.width(), img.height()
    cropped = img.copy(box)
    out = QImage(w, h, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    x = (w - box.width()) // 2
    y = (h - box.height()) // 2
    p = QPainter(out)
    p.drawImage(x, y, cropped)
    p.end()
    return out


def trim_to_content(
    img: QImage,
    *,
    alpha_threshold: int = 8,
    square: bool = True,
) -> QImage:
    """Crop to content; optionally letterbox back into a square of the original size."""
    img = _as_argb(img)
    box = content_bbox(img, alpha_threshold)
    if box is None:
        return img.copy()
    cropped = img.copy(box)
    if not square:
        return _as_argb(cropped)
    side = max(img.width(), img.height())
    out = QImage(side, side, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    # Scale content to fit with a tiny margin so trim doesn't touch edges
    margin = max(1, side // 32)
    max_inner = side - 2 * margin
    scaled = cropped.scaled(
        max_inner,
        max_inner,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
        if max(cropped.width(), cropped.height()) > max_inner
        else Qt.TransformationMode.FastTransformation,
    )
    x = (side - scaled.width()) // 2
    y = (side - scaled.height()) // 2
    p = QPainter(out)
    p.drawImage(x, y, scaled)
    p.end()
    return out


def apply_padding(img: QImage, percent: float) -> QImage:
    """Inset content by *percent* of the shorter side (0–45), re-center.

    0 leaves the image unchanged. 20 means content fills the inner 60% box.
    """
    img = _as_argb(img)
    pct = max(0.0, min(45.0, float(percent)))
    if pct < 0.05:
        return img.copy()
    w, h = img.width(), img.height()
    side = min(w, h)
    inset = int(round(side * (pct / 100.0)))
    inset = max(1, min(inset, side // 2 - 1))
    inner = side - 2 * inset
    if inner < 1:
        return img.copy()
    box = content_bbox(img)
    if box is None:
        return img.copy()
    content = img.copy(box)
    scaled = content.scaled(
        inner,
        inner,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
        if max(content.width(), content.height()) > inner
        else Qt.TransformationMode.FastTransformation,
    )
    out = QImage(w, h, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    x = (w - scaled.width()) // 2
    y = (h - scaled.height()) // 2
    p = QPainter(out)
    p.drawImage(x, y, scaled)
    p.end()
    return out


def monochrome(img: QImage, color: QColor | None = None) -> QImage:
    """Keep alpha; set RGB to luminance gray or a solid tint color."""
    img = _as_argb(img)
    w, h = img.width(), img.height()
    out = QImage(w, h, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    use_tint = color is not None and color.isValid()
    tr = tg = tb = 0
    if use_tint:
        tr, tg, tb = color.red(), color.green(), color.blue()
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            a = c.alpha()
            if a == 0:
                continue
            if use_tint:
                out.setPixelColor(x, y, QColor(tr, tg, tb, a))
            else:
                g = (c.red() * 77 + c.green() * 150 + c.blue() * 29) >> 8
                out.setPixelColor(x, y, QColor(g, g, g, a))
    return out


def tint(img: QImage, color: QColor, amount: float = 0.5) -> QImage:
    """Blend each pixel's RGB toward *color* by *amount* (0–1); keep alpha."""
    img = _as_argb(img)
    if not color.isValid():
        return img.copy()
    amt = max(0.0, min(1.0, float(amount)))
    if amt < 1e-6:
        return img.copy()
    w, h = img.width(), img.height()
    out = QImage(w, h, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    tr, tg, tb = color.red(), color.green(), color.blue()
    inv = 1.0 - amt
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            a = c.alpha()
            if a == 0:
                continue
            r = int(round(c.red() * inv + tr * amt))
            g = int(round(c.green() * inv + tg * amt))
            b = int(round(c.blue() * inv + tb * amt))
            out.setPixelColor(x, y, QColor(r, g, b, a))
    return out


def _box_blur_alpha(src: QImage, radius: int) -> QImage:
    """Separable box blur on alpha only; RGB forced to black (shadow matte)."""
    w, h = src.width(), src.height()

    def _pass_h(inp: QImage) -> list[list[int]]:
        rows: list[list[int]] = []
        diam = radius * 2 + 1
        for y in range(h):
            row = [inp.pixelColor(x, y).alpha() for x in range(w)]
            if radius < 1:
                rows.append(row)
                continue
            out_row = [0] * w
            # prefix sums with edge clamp
            pref = [0] * (w + 1)
            for i, a in enumerate(row):
                pref[i + 1] = pref[i] + a
            for x in range(w):
                lo = max(0, x - radius)
                hi = min(w - 1, x + radius)
                # expand weight for clamped edges so edge alphas don't fade oddly
                total = pref[hi + 1] - pref[lo]
                count = hi - lo + 1
                out_row[x] = total // count if count else 0
            rows.append(out_row)
        return rows

    def _pass_v(rows: list[list[int]]) -> QImage:
        out = QImage(w, h, QImage.Format.Format_ARGB32)
        out.fill(Qt.GlobalColor.transparent)
        if radius < 1:
            for y in range(h):
                for x in range(w):
                    a = rows[y][x]
                    if a:
                        out.setPixelColor(x, y, QColor(0, 0, 0, a))
            return out
        for x in range(w):
            col = [rows[y][x] for y in range(h)]
            pref = [0] * (h + 1)
            for i, a in enumerate(col):
                pref[i + 1] = pref[i] + a
            for y in range(h):
                lo = max(0, y - radius)
                hi = min(h - 1, y + radius)
                total = pref[hi + 1] - pref[lo]
                count = hi - lo + 1
                a = total // count if count else 0
                if a:
                    out.setPixelColor(x, y, QColor(0, 0, 0, a))
        return out

    return _pass_v(_pass_h(src))


def drop_shadow(
    img: QImage,
    *,
    offset_x: int = 4,
    offset_y: int = 6,
    blur: int = 6,
    opacity: float = 0.45,
    color: QColor | None = None,
) -> QImage:
    """Composite a soft shadow under the icon; canvas size unchanged."""
    img = _as_argb(img)
    w, h = img.width(), img.height()
    # Shadow matte from alpha
    matte = QImage(w, h, QImage.Format.Format_ARGB32)
    matte.fill(Qt.GlobalColor.transparent)
    sc = color if color is not None and color.isValid() else QColor(0, 0, 0)
    op = max(0.0, min(1.0, float(opacity)))
    for y in range(h):
        for x in range(w):
            a = img.pixelColor(x, y).alpha()
            if a:
                sa = int(round(a * op))
                if sa:
                    matte.setPixelColor(x, y, QColor(sc.red(), sc.green(), sc.blue(), sa))

    blur_r = max(0, min(32, int(blur)))
    # Blur on alpha; re-apply shadow RGB
    if blur_r > 0:
        # Use grayscale alpha blur then recolor
        alpha_src = QImage(w, h, QImage.Format.Format_ARGB32)
        alpha_src.fill(Qt.GlobalColor.transparent)
        for y in range(h):
            for x in range(w):
                a = matte.pixelColor(x, y).alpha()
                if a:
                    alpha_src.setPixelColor(x, y, QColor(0, 0, 0, a))
        blurred = _box_blur_alpha(alpha_src, blur_r)
        shadow = QImage(w, h, QImage.Format.Format_ARGB32)
        shadow.fill(Qt.GlobalColor.transparent)
        for y in range(h):
            for x in range(w):
                a = blurred.pixelColor(x, y).alpha()
                if a:
                    shadow.setPixelColor(x, y, QColor(sc.red(), sc.green(), sc.blue(), a))
    else:
        shadow = matte

    out = QImage(w, h, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.drawImage(int(offset_x), int(offset_y), shadow)
    p.drawImage(0, 0, img)
    p.end()
    return out


def outline(
    img: QImage,
    *,
    width: int = 2,
    color: QColor | None = None,
) -> QImage:
    """Draw a solid outline around opaque content (under the original)."""
    img = _as_argb(img)
    w, h = img.width(), img.height()
    thr = 16
    oc = color if color is not None and color.isValid() else QColor(0, 0, 0)
    rad = max(1, min(16, int(width)))
    # Dilate alpha
    ring = QImage(w, h, QImage.Format.Format_ARGB32)
    ring.fill(Qt.GlobalColor.transparent)
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() <= thr:
                continue
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    if dx * dx + dy * dy > rad * rad:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        ring.setPixelColor(
                            nx, ny, QColor(oc.red(), oc.green(), oc.blue(), 255)
                        )
    out = QImage(w, h, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawImage(0, 0, ring)
    p.drawImage(0, 0, img)
    p.end()
    return out
