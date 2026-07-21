"""kAppIcon Qt UI (Map / Create / Settings / …)."""
from __future__ import annotations

import sys, os, subprocess, tempfile, shutil, fcntl, time, json, hashlib, re
from contextlib import contextmanager
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QSplitter,
    QFrame, QTabWidget, QCheckBox, QComboBox, QFileDialog,
    QButtonGroup, QColorDialog, QMessageBox, QToolButton, QSizePolicy,
    QMainWindow, QGroupBox, QFormLayout, QDialogButtonBox, QStatusBar,
    QStyle, QStyleFactory, QRadioButton, QDialog, QSlider,
    QAbstractItemView, QMenu, QAbstractSpinBox, QTextEdit, QPlainTextEdit,
)
from PyQt6.QtGui import (
    QPixmap, QIcon, QColor, QPainter, QPainterPath, QPalette,
    QCursor, QImage, QPen, QKeySequence, QShortcut, QAction,
    QDragEnterEvent, QDropEvent,
)
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, pyqtSignal, QPointF, QRectF, QUrl

from kappicon import (
    ApplyError,
    THEME_ICON_PREFIX,
    apply_icon_to_desktop,
    apply_lock,
    is_kappicon_icon_name,
    is_valid_desktop_id,
    prepare_icon_value,
    prune_unreferenced_kappicon_assets,
    restore_user_desktop_snapshot,
    snapshot_user_desktop,
    undo_keep_icon_names,
)
from kappicon.desktop import (
    find_any_desktop_path,
    find_system_desktop_path,
    path_is_under,
    read_desktop_icon_value,
    set_desktop_icon_py,
    user_override_only_differs_by_icon,
)
from kappicon.discovery import (
    collect_system_icons,
    discover_icon_themes,
    friendly_desktop_label,
    is_visible_user_launcher,
    parse_desktop_fields,
    parse_desktop_launcher_meta,
    parse_icon_name,
    pick_primary_provider,
    scan_apps_missing_icons,
    scan_theme_icons,
    scan_user_launcher_overrides,
)
from kappicon.icons import find_magick_cmd, is_kappicon_icon_name as _is_k_icon
from kappicon.paths import (
    BACKUP_DIR,
    DATA_DIR,
    DOWNLOADS_DIR_DEFAULT,
    LIBRARY_DIR,
    LOCK_FILE,
    TARGET_DIR,
    USER_APPS_DIR,
    USER_ICONS_DIR,
    _run_host,
)

ICON_EXTENSIONS = {".icns", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".svgz", ".bmp", ".gif", ".xpm"}
IMAGE_IMPORT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg", ".svgz"}
STANDARD_ICON_SIZE = 512
APPLY_UNDO_MAX = 15
RECENT_MAX = 12
MAP_ICON_SIZES = (32, 48, 64)
BROWSE_FOR_ICON = "__browse_for_icon__"
DESKTOP_LIST_RAW = [d for d in os.environ.get("DESKTOP_LIST", "").strip().split("\n") if d]

def make_rounded_pixmap(pixmap, radius=18):
    size = pixmap.size()
    rounded = QPixmap(size)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


def extract_preview(file_path):
    """Return a path QPixmap can load. For .icns, extracts into a temp dir.

    On success with .icns the returned path lives under a temp dir; the caller
    owns cleanup of that directory (dirname of the returned path).
    """
    if not file_path or not os.path.isfile(file_path):
        return None
    ext = os.path.splitext(file_path)[1].lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg", ".svgz", ".xpm"}:
        # QPixmap / QIcon can load these directly
        return file_path
    if ext != ".icns":
        return None
    tmpdir = tempfile.mkdtemp(prefix="kappicon-preview-")
    try:
        subprocess.run(
            ["icns2png", "-x", file_path],
            cwd=tmpdir, capture_output=True, timeout=15, check=False,
        )
        candidates = sorted(
            [f for f in os.listdir(tmpdir) if f.endswith(".png")],
            key=lambda f: os.path.getsize(os.path.join(tmpdir, f)), reverse=True,
        )
        if candidates:
            # Caller must clean dirname(returned path)
            return os.path.join(tmpdir, candidates[0])
    except Exception:
        pass
    shutil.rmtree(tmpdir, ignore_errors=True)
    return None


def resolve_icon(icon_name, size=28):
    """Resolve Icon= to a QPixmap at roughly ``size`` pixels (theme name or file path)."""
    if not icon_name:
        return None
    try:
        size = max(16, int(size))
    except (TypeError, ValueError):
        size = 28
    if os.path.isabs(icon_name):
        if os.path.isfile(icon_name):
            pix = QPixmap(icon_name)
            if not pix.isNull():
                return pix.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        return None
    if any(c in icon_name for c in "/?#<>:\"|*"):
        return None
    from PyQt6.QtGui import QIcon
    theme_icon = QIcon.fromTheme(icon_name)
    if not theme_icon.isNull():
        pix = theme_icon.pixmap(size, size)
        if not pix.isNull():
            return pix
    bases = [USER_ICONS_DIR]
    for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        d = d.strip()
        if d:
            bases.append(os.path.join(d, "icons"))
            bases.append(os.path.join(d, "pixmaps"))
    bases.append("/usr/share/pixmaps")
    for base in bases:
        for theme in ("hicolor", "breeze", "Papirus", "Numix", "Adwaita"):
            for sz in ("48x48", "64x64", "256x256", "scalable", "32x32", "22x22"):
                for ext in (".png", ".svg", ".xpm"):
                    candidate = os.path.join(base, theme, sz, "apps", icon_name + ext)
                    if os.path.isfile(candidate):
                        pix = QPixmap(candidate)
                        if not pix.isNull():
                            return pix.scaled(
                                size, size,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
    return None


def icon_resolves(icon_name):
    """True if Icon= looks usable (file exists or theme name resolves)."""
    if not icon_name or not str(icon_name).strip():
        return False
    icon_name = str(icon_name).strip()
    if os.path.isabs(icon_name) or icon_name.startswith("file:"):
        path = icon_name[5:] if icon_name.startswith("file:") else icon_name
        return os.path.isfile(path)
    if any(c in icon_name for c in "/?#<>:\"|*"):
        return False
    from PyQt6.QtGui import QIcon
    ic = QIcon.fromTheme(icon_name)
    if not ic.isNull():
        sizes = ic.availableSizes()
        if sizes:
            return True
        # Some themes report empty sizes but still paint
        pix = ic.pixmap(32, 32)
        if not pix.isNull() and not pix.toImage().isNull():
            # fully transparent 32x32 still "resolves" — check alpha roughly
            img = pix.toImage()
            if img.width() > 0:
                return True
    return resolve_icon(icon_name) is not None



def schedule_icon_cache_refresh(parent_widget=None):
    """Debounce expensive cache tools; always runs after lock is released."""
    global _cache_refresh_timer
    app = QApplication.instance()

    def _run():
        cmds = [
            ["kbuildsycoca6", "--noincremental"],
            ["kbuildsycoca6"],
            ["kbuildsycoca5", "--noincremental"],
            ["kbuildsycoca5"],
        ]
        for cmd in cmds:
            if not shutil.which(cmd[0]):
                continue
            try:
                _run_host(cmd, capture_output=True, timeout=60)
                break
            except Exception:
                continue
        try:
            _run_host(
                ["update-desktop-database", USER_APPS_DIR],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
        for p in (
            os.path.join(USER_ICONS_DIR, "hicolor"),
            os.path.expanduser("~/.icons"),
            USER_ICONS_DIR,
        ):
            if os.path.isdir(p) and shutil.which("gtk-update-icon-cache"):
                try:
                    _run_host(
                        ["gtk-update-icon-cache", "-f", "-t", p],
                        capture_output=True, timeout=30,
                    )
                except Exception:
                    pass

    # Use QTimer when Qt is alive so we don't block the UI mid-click
    if app is not None:
        if _cache_refresh_timer is None:
            _cache_refresh_timer = QTimer()
            _cache_refresh_timer.setSingleShot(True)
            _cache_refresh_timer.timeout.connect(_run)
        _cache_refresh_timer.stop()
        _cache_refresh_timer.start(350)
    else:
        _run()



# ── Icon editor (pixel canvas + image import) ────────────────────────────
class PixelCanvas(QFrame):
    """Simple pixel grid editor for designing icons."""
    changed = pyqtSignal()
    history_changed = pyqtSignal()  # undo/redo availability changed

    # Cap memory: each 512² ARGB snapshot ≈ 1 MiB
    MAX_HISTORY = 40

    def __init__(self, grid_size=64, parent=None):
        super().__init__(parent)
        self.grid_size = grid_size
        self.tool = "pen"  # pen | eraser | fill | picker
        self.color = QColor(0, 120, 215, 255)
        self.show_grid = True
        self._drawing = False
        self._stroke_undo_pushed = False  # one undo entry per pen/eraser stroke
        self._dirty = False
        self._image = QImage(grid_size, grid_size, QImage.Format.Format_ARGB32)
        self._image.fill(Qt.GlobalColor.transparent)
        self._undo_stack = []  # list[QImage]
        self._redo_stack = []
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def image(self):
        return self._image

    def is_dirty(self):
        """True if the canvas changed since last save/mark_clean."""
        return self._dirty

    def mark_clean(self):
        self._dirty = False

    def is_blank(self):
        """True if every pixel is fully transparent."""
        blank = QImage(self._image.size(), self._image.format())
        blank.fill(Qt.GlobalColor.transparent)
        return self._image == blank

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def clear_history(self):
        """Drop undo/redo (e.g. after opening a library icon as a fresh base)."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.history_changed.emit()

    def _snapshot(self):
        return self._image.copy()

    def _push_undo(self):
        """Save current canvas so the next mutation can be undone."""
        self._undo_stack.append(self._snapshot())
        while len(self._undo_stack) > self.MAX_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self.history_changed.emit()

    def undo(self):
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self._image = self._undo_stack.pop()
        self.grid_size = self._image.width()
        self._drawing = False
        self._stroke_undo_pushed = False
        self.update()
        self._touch()
        self.history_changed.emit()
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        while len(self._undo_stack) > self.MAX_HISTORY:
            self._undo_stack.pop(0)
        self._image = self._redo_stack.pop()
        self.grid_size = self._image.width()
        self._drawing = False
        self._stroke_undo_pushed = False
        self.update()
        self._touch()
        self.history_changed.emit()
        return True

    def _touch(self):
        self._dirty = True
        self.changed.emit()

    def set_image(self, img: QImage, *, record_undo=True):
        if img.isNull():
            return
        if record_undo:
            self._push_undo()
        self._image = img.convertToFormat(QImage.Format.Format_ARGB32)
        self.grid_size = self._image.width()
        self.update()
        self._touch()

    def clear(self, color=None, *, record_undo=True):
        if record_undo:
            self._push_undo()
        if color is None:
            self._image.fill(Qt.GlobalColor.transparent)
        else:
            self._image.fill(color)
        self.update()
        self._touch()

    def resize_grid(self, size, *, record_undo=True):
        size = max(8, min(512, int(size)))
        if size == self.grid_size:
            return
        if record_undo:
            self._push_undo()
        scaled = self._image.scaled(
            size, size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.grid_size = size
        self._image = scaled.convertToFormat(QImage.Format.Format_ARGB32)
        self.update()
        self._touch()

    def load_from_file(self, path, fit=True, size=None, *, record_undo=True):
        """Load an image onto the canvas.

        If *size* is set, the grid is resized first (imports use STANDARD_ICON_SIZE
        so every imported file lands on the same dimensions).
        """
        img = QImage(path)
        if img.isNull():
            return False
        img = img.convertToFormat(QImage.Format.Format_ARGB32)
        if record_undo:
            self._push_undo()
        if size is not None:
            size = max(8, min(512, int(size)))
            self.grid_size = size
        g = self.grid_size
        if fit:
            # Letterbox into square grid, preserving aspect, transparent pad
            canvas = QImage(g, g, QImage.Format.Format_ARGB32)
            canvas.fill(Qt.GlobalColor.transparent)
            scaled = img.scaled(
                g, g,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (g - scaled.width()) // 2
            y = (g - scaled.height()) // 2
            p = QPainter(canvas)
            p.drawImage(x, y, scaled)
            p.end()
            self._image = canvas
        else:
            self._image = img.scaled(
                g, g,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ).convertToFormat(QImage.Format.Format_ARGB32)
        self.update()
        self._touch()
        return True

    def _cell_size(self):
        side = min(self.width(), self.height())
        return max(1, side / self.grid_size), side

    def _pos_to_cell(self, pos):
        cell, side = self._cell_size()
        ox = (self.width() - side) / 2
        oy = (self.height() - side) / 2
        x = int((pos.x() - ox) / cell)
        y = int((pos.y() - oy) / cell)
        if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
            return x, y
        return None

    def _apply_tool(self, x, y, *, begin_stroke=False):
        if self.tool == "picker":
            self.color = self._image.pixelColor(x, y)
            self.changed.emit()  # color swatch only — not a canvas edit
            return
        # One history entry per stroke (press) or fill click
        if begin_stroke or self.tool == "fill":
            if self.tool == "fill":
                target = self._image.pixelColor(x, y)
                if target == self.color:
                    return  # no-op fill — don't pollute history
                self._push_undo()
            elif begin_stroke and not self._stroke_undo_pushed:
                self._push_undo()
                self._stroke_undo_pushed = True
        if self.tool == "pen":
            self._image.setPixelColor(x, y, self.color)
        elif self.tool == "eraser":
            self._image.setPixelColor(x, y, QColor(0, 0, 0, 0))
        elif self.tool == "fill":
            self._flood_fill(x, y, self.color)
        self.update()
        self._touch()

    def _flood_fill(self, sx, sy, new_color):
        target = self._image.pixelColor(sx, sy)
        if target == new_color:
            return
        stack = [(sx, sy)]
        seen = set()
        w = self.grid_size
        while stack:
            x, y = stack.pop()
            if (x, y) in seen:
                continue
            if not (0 <= x < w and 0 <= y < w):
                continue
            if self._image.pixelColor(x, y) != target:
                continue
            seen.add((x, y))
            self._image.setPixelColor(x, y, new_color)
            stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cell, side = self._cell_size()
        ox = (self.width() - side) / 2
        oy = (self.height() - side) / 2

        # Clip all drawing strictly within the canvas area
        p.setClipRect(int(ox), int(oy), int(side), int(side))

        # Checkerboard for transparency
        p.fillRect(self.rect(), QColor(40, 40, 42) if self.palette().color(
            self.palette().ColorRole.Window).lightness() < 128 else QColor(220, 220, 224))
        check = max(4, int(cell))
        c1, c2 = QColor(180, 180, 185), QColor(210, 210, 215)
        if self.palette().color(self.palette().ColorRole.Window).lightness() < 128:
            c1, c2 = QColor(50, 50, 54), QColor(62, 62, 68)
        for row in range(int(side // check) + 1):
            for col in range(int(side // check) + 1):
                p.fillRect(
                    int(ox + col * check), int(oy + row * check),
                    check, check, c1 if (row + col) % 2 == 0 else c2,
                )

        # Pixel art (nearest neighbor)
        scaled = QPixmap.fromImage(self._image).scaled(
            int(side), int(side),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        p.drawPixmap(int(ox), int(oy), scaled)

        if self.show_grid and cell >= 4:
            p.setPen(QPen(QColor(0, 0, 0, 40), 1))
            for i in range(self.grid_size + 1):
                x = ox + i * cell
                y = oy + i * cell
                p.drawLine(int(x), int(oy), int(x), int(oy + side))
                p.drawLine(int(ox), int(y), int(ox + side), int(y))

        # Outer border
        p.setPen(QPen(QColor(0, 0, 0, 80), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(int(ox), int(oy), int(side) - 1, int(side) - 1)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        cell = self._pos_to_cell(event.position())
        if not cell:
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._drawing = self.tool in ("pen", "eraser")
        self._stroke_undo_pushed = False
        self._apply_tool(*cell, begin_stroke=True)

    def mouseMoveEvent(self, event):
        if not self._drawing:
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        cell = self._pos_to_cell(event.position())
        if cell:
            self._apply_tool(*cell, begin_stroke=False)

    def mouseReleaseEvent(self, event):
        self._drawing = False
        self._stroke_undo_pushed = False

    def keyPressEvent(self, event):
        # Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y when the canvas has focus
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            event.accept()
            return
        super().keyPressEvent(event)


class ImportPositionView(QWidget):
    """Pan/zoom a source image under a fixed square crop (the icon canvas)."""

    changed = pyqtSignal()

    def __init__(self, source: QImage, canvas_size=STANDARD_ICON_SIZE, parent=None):
        super().__init__(parent)
        self._src = source.convertToFormat(QImage.Format.Format_ARGB32)
        self._canvas = max(8, int(canvas_size))
        self._scale = 1.0  # source pixels → canvas pixels
        self._dx = 0.0     # image top-left X in canvas space
        self._dy = 0.0
        self._drag_origin = None
        self._drag_dx0 = 0.0
        self._drag_dy0 = 0.0
        # Background: None = keep transparency; else solid square under the image.
        # Rounded/circle masks are Settings → applied only on Map Apply.
        self._bg_color = None  # QColor | None
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.fit()

    def set_background(self, color=None):
        """Set solid square background color, or None to keep transparency."""
        self._bg_color = QColor(color) if color is not None else None
        if self._bg_color is not None and not self._bg_color.isValid():
            self._bg_color = QColor(255, 255, 255)
        self.update()
        self.changed.emit()

    def scale(self):
        return self._scale

    def set_scale_factor(self, factor, anchor_canvas=None):
        """Set absolute scale; optional anchor in canvas coords (default center)."""
        factor = max(0.02, min(32.0, float(factor)))
        if abs(factor - self._scale) < 1e-9:
            return
        if anchor_canvas is None:
            ax = ay = self._canvas / 2.0
        else:
            ax, ay = anchor_canvas
        # Keep the image point under the anchor fixed
        # canvas = dx + sx * scale  →  sx = (canvas - dx) / scale
        sx = (ax - self._dx) / self._scale
        sy = (ay - self._dy) / self._scale
        self._scale = factor
        self._dx = ax - sx * self._scale
        self._dy = ay - sy * self._scale
        self.update()
        self.changed.emit()

    def zoom_by(self, mult, anchor_canvas=None):
        self.set_scale_factor(self._scale * mult, anchor_canvas)

    def fit(self):
        """Whole image visible (letterbox), centered."""
        w, h = self._src.width(), self._src.height()
        if w < 1 or h < 1:
            return
        self._scale = min(self._canvas / w, self._canvas / h)
        self._dx = (self._canvas - w * self._scale) / 2.0
        self._dy = (self._canvas - h * self._scale) / 2.0
        self.update()
        self.changed.emit()

    def fill(self):
        """Cover the whole square (may crop edges), centered."""
        w, h = self._src.width(), self._src.height()
        if w < 1 or h < 1:
            return
        self._scale = max(self._canvas / w, self._canvas / h)
        self._dx = (self._canvas - w * self._scale) / 2.0
        self._dy = (self._canvas - h * self._scale) / 2.0
        self.update()
        self.changed.emit()

    def render_canvas(self) -> QImage:
        """Rasterize current view into a canvas_size² icon."""
        out = QImage(self._canvas, self._canvas, QImage.Format.Format_ARGB32)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        full = QRectF(0, 0, self._canvas, self._canvas)
        if self._bg_color is not None:
            p.fillRect(full, self._bg_color)
        target = QRectF(
            self._dx, self._dy,
            self._src.width() * self._scale,
            self._src.height() * self._scale,
        )
        p.drawImage(target, self._src)
        p.end()
        return out

    def _view_metrics(self):
        side = min(self.width(), self.height()) - 24
        side = max(64, side)
        ox = (self.width() - side) / 2
        oy = (self.height() - side) / 2
        return ox, oy, side

    def _widget_to_canvas(self, pos):
        ox, oy, side = self._view_metrics()
        x = (pos.x() - ox) / side * self._canvas
        y = (pos.y() - oy) / side * self._canvas
        return x, y

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Base))

        ox, oy, side = self._view_metrics()
        # Dim area outside crop
        p.fillRect(self.rect(), QColor(0, 0, 0, 40))

        # Clip to square crop frame
        p.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(ox, oy, side, side), 6, 6)
        p.setClipPath(path)
        crop = QRectF(ox, oy, side, side)
        p.fillRect(crop, QColor(30, 30, 30))

        # Checkerboard for transparency (under plate / image)
        chk = 12
        c1, c2 = QColor(50, 50, 50), QColor(40, 40, 40)
        for row in range(int(side // chk) + 1):
            for col in range(int(side // chk) + 1):
                p.fillRect(
                    int(ox + col * chk), int(oy + row * chk), chk, chk,
                    c1 if (row + col) % 2 == 0 else c2,
                )

        # Optional solid square under the image (shape masks happen on Map Apply)
        if self._bg_color is not None:
            p.fillRect(crop, self._bg_color)

        # Map canvas coords → widget
        def c2w(cx, cy):
            return ox + cx / self._canvas * side, oy + cy / self._canvas * side

        x0, y0 = c2w(self._dx, self._dy)
        x1, y1 = c2w(
            self._dx + self._src.width() * self._scale,
            self._dy + self._src.height() * self._scale,
        )
        p.drawImage(QRectF(x0, y0, x1 - x0, y1 - y0), self._src)
        p.restore()

        # Crop border
        pen = QPen(QColor(70, 150, 255), 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(ox, oy, side, side), 6, 6)

        # Corner labels
        p.setPen(QColor(180, 190, 200))
        p.drawText(
            int(ox), int(oy + side + 16),
            f"Drag to move · scroll to zoom · {self._canvas}×{self._canvas} crop",
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position()
            self._drag_dx0 = self._dx
            self._drag_dy0 = self._dy
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            ox, oy, side = self._view_metrics()
            # widget delta → canvas delta
            ddx = (event.position().x() - self._drag_origin.x()) / side * self._canvas
            ddy = (event.position().y() - self._drag_origin.y()) / side * self._canvas
            self._dx = self._drag_dx0 + ddx
            self._dy = self._drag_dy0 + ddy
            self.update()
            self.changed.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        mult = 1.1 if delta > 0 else 1 / 1.1
        anchor = self._widget_to_canvas(event.position())
        self.zoom_by(mult, anchor)
        event.accept()


class ImportPositionDialog(QDialog):
    """Position a (possibly large) image into the icon square before placing it on the canvas."""

    def __init__(self, source: QImage, canvas_size=STANDARD_ICON_SIZE, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Position import")
        self.resize(560, 700)
        self.setMinimumSize(420, 520)
        self._settings = QSettings("KAppIcon", "KAppIcon")

        layout = QVBoxLayout(self)
        layout.addWidget(make_hint_label(
            "Drag the picture to move it. Zoom so the part you want fills the square — "
            "that square becomes your icon. Transparent PNGs can stay transparent or "
            "sit on a solid color plate. Icon shape (rounded / circle) is applied later "
            "from Settings when you Map the icon."
        ))

        self.view = ImportPositionView(source, canvas_size=canvas_size, parent=self)
        layout.addWidget(self.view, stretch=1)

        zoom_row = QHBoxLayout()
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedWidth(36)
        self.zoom_out_btn.setToolTip("Zoom out")
        self.zoom_out_btn.clicked.connect(lambda: self.view.zoom_by(1 / 1.15))
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(36)
        self.zoom_in_btn.setToolTip("Zoom in")
        self.zoom_in_btn.clicked.connect(lambda: self.view.zoom_by(1.15))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(5, 800)  # percent of “fit” scale, relative stored below
        self.zoom_slider.setToolTip("Zoom")
        self._fit_scale = max(self.view.scale(), 1e-6)
        self._updating_slider = False
        self.zoom_slider.valueChanged.connect(self._on_slider)
        self.view.changed.connect(self._sync_slider)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(48)
        zoom_row.addWidget(self.zoom_out_btn)
        zoom_row.addWidget(self.zoom_slider, stretch=1)
        zoom_row.addWidget(self.zoom_in_btn)
        zoom_row.addWidget(self.zoom_label)
        layout.addLayout(zoom_row)

        preset_row = QHBoxLayout()
        fit_btn = QPushButton("Fit")
        fit_btn.setToolTip("Show the whole image inside the square")
        fit_btn.clicked.connect(self._do_fit)
        fill_btn = QPushButton("Fill")
        fill_btn.setToolTip("Cover the whole square (crop edges if needed)")
        fill_btn.clicked.connect(self._do_fill)
        preset_row.addWidget(fit_btn)
        preset_row.addWidget(fill_btn)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)

        # ── Background: keep transparency or solid square plate ──────────
        # Shape masks (rounded / circle) live in Settings → Applied icon shape
        # and run at Map Apply — Create always works on a square canvas.
        bg_box = QGroupBox("Background")
        bg_l = QVBoxLayout(bg_box)
        bg_l.addWidget(make_hint_label(
            "Keep transparency, or fill the square with a solid color under the image. "
            "Rounded or circular icon masks are chosen in Settings and applied on Map."
        ))
        mode_row = QHBoxLayout()
        self.bg_keep = QRadioButton("Keep transparency")
        self.bg_solid = QRadioButton("Solid color")
        self.bg_mode_group = QButtonGroup(self)
        self.bg_mode_group.addButton(self.bg_keep)
        self.bg_mode_group.addButton(self.bg_solid)
        mode_row.addWidget(self.bg_keep)
        mode_row.addWidget(self.bg_solid)
        mode_row.addSpacing(12)
        mode_row.addWidget(QLabel("Color:"))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(36, 28)
        self.bg_color_btn.setToolTip("Choose background color")
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        mode_row.addWidget(self.bg_color_btn)
        mode_row.addStretch(1)
        bg_l.addLayout(mode_row)
        layout.addWidget(bg_box)

        # Restore last choices (default: keep transparency)
        saved_mode = self._settings.value("create/import_bg_mode", "transparent", type=str)
        saved_color = self._settings.value("create/import_bg_color", "#ffffff", type=str)
        self._bg_color = QColor(saved_color if saved_color else "#ffffff")
        if not self._bg_color.isValid():
            self._bg_color = QColor(255, 255, 255)
        if saved_mode == "solid":
            self.bg_solid.setChecked(True)
        else:
            self.bg_keep.setChecked(True)

        self.bg_keep.toggled.connect(self._on_bg_mode)
        self.bg_solid.toggled.connect(self._on_bg_mode)
        self._update_color_btn()
        self._on_bg_mode()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use this crop")
        buttons.accepted.connect(self._accept_save_prefs)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._sync_slider()

    def _update_color_btn(self):
        c = self._bg_color
        # Show true color; ignore alpha in button face for readability
        face = QColor(c.red(), c.green(), c.blue())
        self.bg_color_btn.setStyleSheet(
            f"QPushButton {{ background-color: {face.name()}; border: 1px solid #666; "
            f"border-radius: 4px; }}"
        )

    def _pick_bg_color(self):
        c = QColorDialog.getColor(
            self._bg_color, self, "Background color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if c.isValid():
            self._bg_color = c
            self._update_color_btn()
            if self.bg_solid.isChecked():
                self._apply_bg_to_view()

    def _on_bg_mode(self, _on=None):
        solid = self.bg_solid.isChecked()
        self.bg_color_btn.setEnabled(solid)
        self._apply_bg_to_view()

    def _apply_bg_to_view(self):
        # Always square in Create — Map Apply applies rounded/circle from Settings
        if self.bg_solid.isChecked():
            self.view.set_background(self._bg_color)
        else:
            self.view.set_background(None)

    def _accept_save_prefs(self):
        mode = "solid" if self.bg_solid.isChecked() else "transparent"
        self._settings.setValue("create/import_bg_mode", mode)
        if self._bg_color.alpha() < 255:
            self._settings.setValue(
                "create/import_bg_color",
                self._bg_color.name(QColor.NameFormat.HexArgb),
            )
        else:
            self._settings.setValue("create/import_bg_color", self._bg_color.name())
        self.accept()

    def _do_fit(self):
        self.view.fit()
        self._fit_scale = max(self.view.scale(), 1e-6)
        self._sync_slider()

    def _do_fill(self):
        self.view.fill()
        self._sync_slider()

    def _on_slider(self, value):
        if self._updating_slider:
            return
        # Slider 100 = current fit scale
        factor = (value / 100.0) * self._fit_scale
        self.view.set_scale_factor(factor)
        self.zoom_label.setText(f"{value}%")

    def _sync_slider(self):
        self._updating_slider = True
        pct = int(round((self.view.scale() / self._fit_scale) * 100))
        pct = max(5, min(800, pct))
        self.zoom_slider.setValue(pct)
        self.zoom_label.setText(f"{pct}%")
        self._updating_slider = False

    def result_image(self) -> QImage:
        return self.view.render_canvas()


# ── KDE / Breeze helpers ─────────────────────────────────────────────────
def apply_breeze_style(app: QApplication):
    """Prefer Breeze so Plasma users get native KDE look & feel."""
    keys = {k.lower(): k for k in QStyleFactory.keys()}
    for name in ("breeze", "oxygen", "fusion"):
        if name in keys:
            app.setStyle(QStyleFactory.create(keys[name]))
            break
    # Remember Plasma/system palette so Appearance → System can restore it
    app._kappicon_system_palette = QPalette(app.palette())
    # Desktop file / Wayland app id
    app.setDesktopFileName("kappicon")
    app.setApplicationName("kAppIcon")
    app.setOrganizationName("KAppIcon")  # QSettings → $XDG_CONFIG_HOME/KAppIcon/
    app.setApplicationDisplayName("kAppIcon")


def make_light_palette():
    """Readable light scheme (Breeze-like) when user forces Light."""
    p = QPalette()
    window = QColor(239, 240, 241)
    base = QColor(252, 252, 252)
    text = QColor(35, 38, 41)
    disabled = QColor(120, 120, 120)
    highlight = QColor(61, 174, 233)
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 246, 247))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Highlight, highlight)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(100, 104, 109))
    p.setColor(QPalette.ColorRole.Link, QColor(41, 128, 185))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    return p


def make_dark_palette():
    """Readable dark scheme (Breeze Dark–like) when user forces Dark."""
    p = QPalette()
    window = QColor(35, 38, 41)
    base = QColor(27, 30, 32)
    text = QColor(239, 240, 241)
    disabled = QColor(120, 120, 120)
    highlight = QColor(61, 174, 233)
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(42, 46, 50))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Highlight, highlight)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 154, 158))
    p.setColor(QPalette.ColorRole.Link, QColor(61, 174, 233))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    return p


def apply_appearance_mode(mode: str):
    """Apply system / light / dark color scheme to the whole app."""
    app = QApplication.instance()
    if app is None:
        return
    mode = (mode or "system").lower()
    if mode == "light":
        app.setPalette(make_light_palette())
    elif mode == "dark":
        app.setPalette(make_dark_palette())
    else:
        sys_pal = getattr(app, "_kappicon_system_palette", None)
        app.setPalette(QPalette(sys_pal) if sys_pal is not None else app.style().standardPalette())


def layout_margins(widget=None):
    """Standard layout margins from the active QStyle (KDE HIG–friendly)."""
    style = QApplication.style()
    m = style.pixelMetric(QStyle.PixelMetric.PM_LayoutLeftMargin)
    # Breeze typically reports 6–9; keep a sensible floor for readability
    m = max(9, m)
    return m, m, m, m


def layout_spacing():
    style = QApplication.style()
    s = style.pixelMetric(QStyle.PixelMetric.PM_LayoutVerticalSpacing)
    return max(6, s)


def theme_icon(*names, fallback=None):
    for n in names:
        ic = QIcon.fromTheme(n)
        if not ic.isNull():
            return ic
    return fallback or QIcon()


def make_hint_label(text):
    """Secondary/helper text; color tracks the active palette (system/light/dark)."""
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    # palette() resolves after Appearance changes without re-creating labels
    lab.setStyleSheet("QLabel { color: palette(placeholder-text); }")
    return lab


def equalize_widths(widgets):
    if not widgets:
        return
    max_w = max(w.sizeHint().width() for w in widgets)
    for w in widgets:
        w.setFixedWidth(max_w)



# ── Main Window ──────────────────────────────────────────────────────────
class CombinedWindow(QMainWindow):
    def __init__(self, icon_files, app_data):
        super().__init__()
        self.settings = QSettings("KAppIcon", "KAppIcon")
        self.icon_files = icon_files
        # app_data: list of (desktop_basename, icon_name, display_name, desktop_path)
        self.app_data = app_data
        self.desktop_paths = {d[0]: d[3] for d in app_data}
        self.desktop_labels = {d[0]: d[2] for d in app_data}
        # theme icons already referenced by installed .desktop files
        self.system_icons = collect_system_icons([(d[0], d[1]) for d in app_data])
        from kappicon.timing import span as _timing_span

        with _timing_span("discover_icon_themes"):
            self.installed_themes = discover_icon_themes()
        # theme path -> (mtime or None, [(name, file_path), ...])
        # mtime invalidation: re-scan when theme dir mtime changes (PERF-02 light win)
        self._theme_icons_cache = {}
        self.icon_source = "files"  # "files" | "system" | "icontheme"
        self.selected_file = None   # path or "theme:<name>" (legacy exit protocol unused for Apply)
        self.selected_app = None
        self._preview_tmpdir = None
        self._apply_busy = False
        self._undo_stack = []  # list of {desktop_id, display, previous_bytes}
        self._map_icon_size = int(self.settings.value("map/icon_size", 32) or 32)
        if self._map_icon_size not in MAP_ICON_SIZES:
            self._map_icon_size = 32
        self._app_filter_mode = self.settings.value("map/app_filter_mode", "all", type=str) or "all"
        if self._app_filter_mode not in ("all", "customized"):
            self._app_filter_mode = "all"
        self._missing_kind = self.settings.value("missing/kind", "all", type=str) or "all"
        if self._missing_kind not in ("all", "empty", "unresolved"):
            self._missing_kind = "all"
        self.initUI()

    def initUI(self):
        self.setWindowTitle("kAppIcon")
        # Restore window size when available (KDE: remember geometry lightly)
        w = int(self.settings.value("window/width", 960) or 960)
        h = int(self.settings.value("window/height", 680) or 680)
        self.resize(max(720, w), max(520, h))
        self.setMinimumSize(720, 520)
        self.setAcceptDrops(True)

        # Window icon (Breeze / hicolor / installed asset)
        wicon = theme_icon("preferences-desktop-icons", "applications-graphics", "kappicon")
        for path in (
            os.path.join(USER_ICONS_DIR, "kappicon.png"),
            os.path.join(USER_ICONS_DIR, "hicolor", "256x256", "apps", "kappicon.png"),
        ):
            if os.path.isfile(path):
                wicon = QIcon(path)
                break
        self.setWindowIcon(wicon)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        m = layout_margins()
        root.setContentsMargins(*m)
        root.setSpacing(layout_spacing())

        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        tabs.setMovable(False)
        self.main_tabs = tabs
        tabs.currentChanged.connect(self._on_tab_changed)

        map_w = QWidget()
        self._build_map_tab(map_w)
        tabs.addTab(map_w, theme_icon("preferences-desktop-icons", "folder-images"), "Map")

        editor_w = QWidget()
        self._build_editor_tab(editor_w)
        tabs.addTab(editor_w, theme_icon("draw-brush", "document-edit", "applications-graphics"), "Create")

        settings_w = QWidget()
        self._build_settings_tab(settings_w)
        tabs.addTab(settings_w, theme_icon("configure", "settings-configure", "preferences-system"), "Settings")

        # 4) Overrides · 5) Missing icons
        overrides_w = QWidget()
        self._build_overrides_tab(overrides_w)
        tabs.addTab(
            overrides_w,
            theme_icon("document-edit", "edit-entry", "preferences-desktop-default-applications"),
            "Overrides",
        )

        missing_w = QWidget()
        self._build_missing_tab(missing_w)
        tabs.addTab(
            missing_w,
            theme_icon("dialog-warning", "emblem-important", "image-missing"),
            "Missing",
        )

        root.addWidget(tabs)

        sb = QStatusBar()
        self.setStatusBar(sb)
        # No sticky Map-mode hints here — those are cleared on tab change.
        sb.clearMessage()

        # Apply saved light/dark/system preference
        apply_appearance_mode(self.settings.value("appearance/theme", "system", type=str))

        # ── Menu Bar ──────────────────────────────────────────────────────────
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")
        
        open_action = file_menu.addAction("&Open Icon File...")
        open_action.setIcon(theme_icon("document-open", "file-open"))
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("Open a file browser to select an icon file")
        open_action.triggered.connect(self._browse_for_icon_file)

        import_action = file_menu.addAction("&Import Image...")
        import_action.setIcon(theme_icon("document-import", "image-x-generic"))
        import_action.setShortcut("Ctrl+I")
        import_action.setStatusTip("Import an image into the icon creator canvas")
        import_action.triggered.connect(self._editor_import)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("&Exit")
        exit_action.setIcon(theme_icon("application-exit", "exit"))
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit kAppIcon")
        exit_action.triggered.connect(self.close)

        # Edit Menu — contextual Undo (Map apply stack vs Create canvas)
        edit_menu = menubar.addMenu("&Edit")
        self.undo_action = edit_menu.addAction("&Undo")
        self.undo_action.setIcon(theme_icon("edit-undo", "edit-undo"))
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setStatusTip("Undo the last icon apply (Map) or canvas edit (Create)")
        self.undo_action.setEnabled(False)
        self.undo_action.triggered.connect(self._contextual_undo)

        self.redo_action = edit_menu.addAction("&Redo")
        self.redo_action.setIcon(theme_icon("edit-redo", "edit-redo"))
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setStatusTip("Redo the last undone Create-tab change")
        self.redo_action.setEnabled(False)
        self.redo_action.triggered.connect(self._editor_redo)

        self.undo_apply_action = edit_menu.addAction("Undo last &icon apply")
        self.undo_apply_action.setIcon(theme_icon("edit-undo", "document-revert"))
        self.undo_apply_action.setStatusTip("Restore the previous launcher icon from this session")
        self.undo_apply_action.setEnabled(False)
        self.undo_apply_action.triggered.connect(self._undo_last_apply)

        # Options Menu
        options_menu = menubar.addMenu("&Options")

        # Theme Sub-menu
        theme_menu = options_menu.addMenu("&Theme")
        theme_menu.setIcon(theme_icon("preferences-desktop-theme", "preferences-color"))
        self.theme_actions = QButtonGroup(self)
        theme_defs = (
            ("System", "system", self.theme_system, theme_icon("preferences-desktop-theme-global", "system")),
            ("Light", "light", self.theme_light, theme_icon("weather-clear", "clear")),
            ("Dark", "dark", self.theme_dark, theme_icon("weather-clear-night", "night")),
        )
        for name, key, button, icon in theme_defs:
            act = theme_menu.addAction(name)
            act.setIcon(icon)
            act.setCheckable(True)
            cur = self.settings.value("appearance/theme", "system", type=str)
            act.setChecked(cur == key)
            act.triggered.connect(lambda checked, btn=button: btn.setChecked(True))
            button.toggled.connect(lambda checked, a=act: a.setChecked(checked))

        backup_action = options_menu.addAction("&Enable Auto Backups")
        backup_action.setIcon(theme_icon("document-save", "save"))
        backup_action.setCheckable(True)
        backup_action.setChecked(self.backup_check.isChecked())
        backup_action.triggered.connect(self.backup_check.setChecked)
        self.backup_check.toggled.connect(backup_action.setChecked)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        help_action = help_menu.addAction("&Help / Documentation")
        help_action.setIcon(theme_icon("help-contents", "dialog-question"))
        help_action.setShortcut("F1")
        help_action.triggered.connect(self._show_help_dialog)

        help_menu.addSeparator()

        about_action = help_menu.addAction("&About kAppIcon")
        about_action.setIcon(theme_icon("help-about", "help-hint"))
        about_action.triggered.connect(self._show_about_dialog)

        about_qt_action = help_menu.addAction("About &Qt")
        about_qt_action.setIcon(theme_icon("qtlogo", "qt-logo"))
        about_qt_action.triggered.connect(QApplication.aboutQt)

        # Session restore after widgets exist (source, filters, selection)
        QTimer.singleShot(0, self._restore_map_session)
        self._sync_undo_actions()

    def _on_tab_changed(self, index):
        """Refresh management tabs when shown; clear stale status tips."""
        if self.statusBar():
            self.statusBar().clearMessage()
        # Tab order: 0 Map, 1 Create, 2 Settings, 3 Overrides, 4 Missing
        if index == 3 and hasattr(self, "_refresh_overrides_list"):
            self._refresh_overrides_list()
        elif index == 4 and hasattr(self, "_refresh_missing_list"):
            self._refresh_missing_list()
        self._sync_undo_actions()

    def _show_about_dialog(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About kAppIcon",
            "<h3>kAppIcon</h3>"
            "<p>Version 3.1.1</p>"
            "<p>A Linux utility to change application icons, reuse theme icons from other apps, "
            "and design your own custom icons. Review overrides and find apps missing icons.</p>"
            "<p>Designed for Plasma / Breeze, following freedesktop.org desktop entry specifications "
            "and KDE Human Interface Guidelines for clear primary actions and safe bulk changes.</p>"
            "<p>License: MIT</p>"
        )

    def _focus_is_text_editor(self):
        """True when Ctrl+Z should edit text, not mutate launchers."""
        w = QApplication.focusWidget()
        while w is not None:
            if isinstance(w, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)):
                return True
            if isinstance(w, QComboBox) and w.isEditable():
                return True
            w = w.parentWidget() if hasattr(w, "parentWidget") else None
        return False

    def _contextual_undo(self):
        """Ctrl+Z: text field → Create canvas → Map apply only (never other tabs)."""
        # Never steal text editing undos (Settings search, filters, names…)
        if self._focus_is_text_editor():
            w = QApplication.focusWidget()
            if w is not None and hasattr(w, "undo"):
                try:
                    w.undo()
                except Exception:
                    pass
            return
        tab = self.main_tabs.currentIndex() if hasattr(self, "main_tabs") else -1
        # Create: canvas history
        if (
            tab == 1
            and hasattr(self, "pixel_canvas")
            and self.pixel_canvas.can_undo()
        ):
            self._editor_undo()
            return
        # Map only: launcher apply undo (HIG: no surprise mutations on other tabs)
        if tab == 0:
            self._undo_last_apply()
            return
        # Settings / Overrides / Missing: do nothing

    def _sync_undo_actions(self):
        canvas_undo = (
            hasattr(self, "pixel_canvas") and self.pixel_canvas.can_undo()
        )
        apply_undo = bool(self._undo_stack) and not self._apply_busy
        tab = self.main_tabs.currentIndex() if hasattr(self, "main_tabs") else -1
        on_create = tab == 1
        on_map = tab == 0
        if hasattr(self, "undo_action"):
            if on_create:
                self.undo_action.setEnabled(canvas_undo)
                self.undo_action.setStatusTip("Undo the last Create-tab canvas change")
            elif on_map:
                self.undo_action.setEnabled(apply_undo)
                self.undo_action.setStatusTip("Undo the last icon apply in this session")
            else:
                self.undo_action.setEnabled(False)
                self.undo_action.setStatusTip("Undo is available on Map (icon apply) or Create (canvas)")
        if hasattr(self, "undo_apply_action"):
            # Explicit menu item always undoes apply when stack non-empty (user intent)
            self.undo_apply_action.setEnabled(apply_undo)
        if hasattr(self, "redo_action"):
            self.redo_action.setEnabled(
                on_create and hasattr(self, "pixel_canvas") and self.pixel_canvas.can_redo()
            )

    # ── Map tab ──────────────────────────────────────────────────────────
    def _build_map_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, layout_spacing(), 0, 0)
        layout.setSpacing(layout_spacing())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: pick icon + pick app ───────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(layout_spacing())

        icon_box = QGroupBox("1. Icon to use")
        ib = QVBoxLayout(icon_box)
        ib.addWidget(make_hint_label(
            "Choose the icon that will be applied — not the application you are changing."
        ))

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source:"))
        self.src_combo = QComboBox()
        self.src_combo.addItem(theme_icon("folder-images", "document-open"), "From file", "files")
        self.src_combo.addItem(
            theme_icon("preferences-desktop-theme", "applications-other"),
            "From another app",
            "system",
        )
        self.src_combo.addItem(
            theme_icon("preferences-desktop-icons", "games-card", "folder-image"),
            "From icon theme",
            "icontheme",
        )
        self.src_combo.currentIndexChanged.connect(self._on_src_combo)
        src_row.addWidget(self.src_combo, stretch=1)
        # List density (KDE: comfortable viewing without a separate “mode”)
        src_row.addWidget(QLabel("Size:"))
        self.map_size_combo = QComboBox()
        self.map_size_combo.addItem("Compact", 32)
        self.map_size_combo.addItem("Comfortable", 48)
        self.map_size_combo.addItem("Large", 64)
        idx_sz = self.map_size_combo.findData(self._map_icon_size)
        self.map_size_combo.setCurrentIndex(idx_sz if idx_sz >= 0 else 0)
        self.map_size_combo.setToolTip("Icon size in the Map lists")
        self.map_size_combo.currentIndexChanged.connect(self._on_map_icon_size_changed)
        src_row.addWidget(self.map_size_combo)
        ib.addLayout(src_row)

        # Theme pack picker (only when source = From icon theme)
        self.theme_row_w = QWidget()
        theme_row = QHBoxLayout(self.theme_row_w)
        theme_row.setContentsMargins(0, 0, 0, 0)
        theme_row.addWidget(QLabel("Theme set:"))
        self.theme_combo = QComboBox()
        self.theme_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.theme_combo.setMinimumContentsLength(18)
        for t in self.installed_themes:
            label = t["name"]
            if t["is_user"]:
                label = f"{label}  (user)"
            self.theme_combo.addItem(
                theme_icon("preferences-desktop-icons", "folder"),
                label,
                t["path"],
            )
        if self.theme_combo.count() == 0:
            self.theme_combo.addItem("(no icon themes found)", "")
        # Prefer last-used theme or first user theme
        saved_theme = self.settings.value("map/icon_theme_path", "", type=str)
        if saved_theme:
            idx = self.theme_combo.findData(saved_theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_pack_changed)
        theme_row.addWidget(self.theme_combo, stretch=1)
        self.theme_row_w.setVisible(False)
        ib.addWidget(self.theme_row_w)

        # Keep button aliases for older call sites
        self.src_files_btn = self.src_combo  # duck-typed via _set_icon_source
        self.src_system_btn = self.src_combo

        self.file_search = QLineEdit()
        self.file_search.setClearButtonEnabled(True)
        self.file_search.setPlaceholderText("Filter icons…")
        self.file_search.setProperty("setClearButtonEnabled", True)
        self.file_search.textChanged.connect(self._on_file_search_changed)
        ib.addWidget(self.file_search)

        self.file_list = QListWidget()
        self.file_list.setIconSize(QSize(self._map_icon_size, self._map_icon_size))
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setUniformItemSizes(True)
        self.file_list.setAcceptDrops(True)
        self.file_list.viewport().setAcceptDrops(True)
        self.file_list.currentItemChanged.connect(self._on_file_select)
        self.file_list.itemClicked.connect(self._on_file_item_clicked)
        self._fill_file_list(self.icon_files)
        ib.addWidget(self.file_list, stretch=1)
        ll.addWidget(icon_box, stretch=1)

        app_box = QGroupBox("2. Application to change")
        ab = QVBoxLayout(app_box)
        ab.addWidget(make_hint_label(
            "This application’s launcher icon will be replaced. "
            "Ctrl/Shift-click to select several apps, then Apply once."
        ))

        app_filt_row = QHBoxLayout()
        self.app_search = QLineEdit()
        self.app_search.setClearButtonEnabled(True)
        self.app_search.setPlaceholderText("Filter applications…")
        self.app_search.textChanged.connect(self._on_app_search_changed)
        app_filt_row.addWidget(self.app_search, stretch=1)
        self.app_scope_combo = QComboBox()
        self.app_scope_combo.addItem("All apps", "all")
        self.app_scope_combo.addItem("Customized only", "customized")
        sc_idx = self.app_scope_combo.findData(self._app_filter_mode)
        self.app_scope_combo.setCurrentIndex(sc_idx if sc_idx >= 0 else 0)
        self.app_scope_combo.setToolTip(
            "Customized only: apps that already have a user .desktop override"
        )
        self.app_scope_combo.currentIndexChanged.connect(self._on_app_scope_changed)
        app_filt_row.addWidget(self.app_scope_combo)
        ab.addLayout(app_filt_row)

        self.app_list = QListWidget()
        self.app_list.setIconSize(QSize(self._map_icon_size, self._map_icon_size))
        self.app_list.setAlternatingRowColors(True)
        self.app_list.setUniformItemSizes(True)
        # ExtendedSelection: single click still selects one; Ctrl/Shift for batch (HIG)
        self.app_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.app_list.currentItemChanged.connect(lambda *_: self._update_mapping_summary())
        self.app_list.itemSelectionChanged.connect(self._update_mapping_summary)
        for desktop_name, icon_name, display_name, _path in self.app_data:
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, desktop_name)
            item.setData(Qt.ItemDataRole.UserRole + 1, display_name)
            item.setData(Qt.ItemDataRole.UserRole + 2, icon_name)
            item.setToolTip(f"Will modify: {display_name}\nDesktop file: {desktop_name}")
            pix = resolve_icon(icon_name, size=self._map_icon_size)
            if pix:
                item.setIcon(QIcon(pix))
            self.app_list.addItem(item)
        ab.addWidget(self.app_list, stretch=1)
        ll.addWidget(app_box, stretch=1)

        splitter.addWidget(left)

        # ── Right: summary (KDE-style group boxes + dialog buttons) ─────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(layout_spacing())

        src_card = QGroupBox("Icon to use")
        sc = QVBoxLayout(src_card)
        self.preview_label = QLabel("Select an icon")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(128, 128)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setFrameShadow(QFrame.Shadow.Sunken)
        self.preview_label.mousePressEvent = self._on_empty_icon_click
        sc.addWidget(self.preview_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        font = self.info_label.font()
        font.setBold(True)
        self.info_label.setFont(font)
        self.info_label.mousePressEvent = self._on_empty_icon_click
        sc.addWidget(self.info_label)

        self.meta_label = make_hint_label("")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc.addWidget(self.meta_label)
        rl.addWidget(src_card)

        arrow = QLabel("↓  applies to")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(arrow)

        tgt_card = QGroupBox("Application to change")
        tc = QHBoxLayout(tgt_card)
        self.target_icon_label = QLabel()
        self.target_icon_label.setFixedSize(48, 48)
        self.target_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_icon_label.setFrameShape(QFrame.Shape.StyledPanel)
        tc.addWidget(self.target_icon_label)
        tgt_text = QVBoxLayout()
        self.target_name_label = QLabel("Select an application")
        font2 = self.target_name_label.font()
        font2.setBold(True)
        self.target_name_label.setFont(font2)
        self.target_name_label.setWordWrap(True)
        tgt_text.addWidget(self.target_name_label)
        self.target_meta_label = make_hint_label("")
        self.target_meta_label.setWordWrap(True)
        tgt_text.addWidget(self.target_meta_label)
        tgt_text.addStretch(1)
        tc.addLayout(tgt_text, stretch=1)
        rl.addWidget(tgt_card)

        self.plan_label = make_hint_label("")
        self.plan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(self.plan_label)

        rl.addStretch(1)

        # KDE-style dialog buttons (Apply is the primary action)
        # Keep short fixed labels so long app names never clip the Apply button.
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        self.select_btn = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        self.select_btn.setText("Apply")
        self.select_btn.setEnabled(False)
        self.select_btn.setIcon(theme_icon("dialog-ok-apply", "dialog-ok"))
        self.select_btn.setToolTip(
            "Apply the selected icon without closing the window"
        )

        self.reset_btn = self.button_box.addButton("Reset to system icon", QDialogButtonBox.ButtonRole.ActionRole)
        self.reset_btn.setIcon(theme_icon("edit-clear-all", "edit-undo", "document-revert"))
        self.reset_btn.setEnabled(False)
        self.reset_btn.setToolTip(
            "Restore the package/system icon when a system .desktop exists "
            "(same as Overrides → Reset to system icon)"
        )
        self.reset_btn.clicked.connect(self._reset_app_icon)

        close_btn = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        close_btn.setText("Close")

        # Do not force Apply to the same width as long labels — that clips “Apply to …”.
        equalize_widths([self.reset_btn, close_btn])
        self.button_box.rejected.connect(self.close)
        self.button_box.clicked.connect(self._on_dialog_button)
        rl.addWidget(self.button_box)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([520, 360])

        layout.addWidget(splitter)

        if self.file_list.count() > 0 and self.file_list.item(0).data(Qt.ItemDataRole.UserRole) != BROWSE_FOR_ICON:
            self.file_list.setCurrentRow(0)
        else:
            self._show_empty_icon_state()
        self._update_mapping_summary()
        self.file_search.setFocus()

    def _on_src_combo(self, _idx=None):
        data = self.src_combo.currentData()
        if data:
            self._set_icon_source(data)
            self.settings.setValue("map/icon_source", data)

    def _on_map_icon_size_changed(self, _idx=None):
        if not hasattr(self, "map_size_combo"):
            return
        size = self.map_size_combo.currentData()
        if size is None:
            return
        self._map_icon_size = int(size)
        self.settings.setValue("map/icon_size", self._map_icon_size)
        if hasattr(self, "file_list"):
            self.file_list.setIconSize(QSize(self._map_icon_size, self._map_icon_size))
        if hasattr(self, "app_list"):
            self.app_list.setIconSize(QSize(self._map_icon_size, self._map_icon_size))
            # Refresh app row icons at new size
            for i in range(self.app_list.count()):
                item = self.app_list.item(i)
                icon_name = item.data(Qt.ItemDataRole.UserRole + 2)
                pix = resolve_icon(icon_name, size=self._map_icon_size) if icon_name else None
                if pix:
                    item.setIcon(QIcon(pix))
        # Re-fill current icon source so file list icons match
        if self.icon_source == "files":
            self._fill_file_list(self.icon_files)
        elif self.icon_source == "system":
            self._fill_system_list()
        else:
            self._fill_icontheme_list()

    def _on_app_scope_changed(self, _idx=None):
        if not hasattr(self, "app_scope_combo"):
            return
        mode = self.app_scope_combo.currentData() or "all"
        self._app_filter_mode = mode
        self.settings.setValue("map/app_filter_mode", mode)
        self._filter_apps(self.app_search.text() if hasattr(self, "app_search") else "")

    def _on_file_search_changed(self, text):
        self.settings.setValue("map/icon_filter", text)
        self._filter_files(text)

    def _on_app_search_changed(self, text):
        self.settings.setValue("map/app_filter", text)
        self._filter_apps(text)

    def _on_dialog_button(self, button):
        if self.button_box.buttonRole(button) == QDialogButtonBox.ButtonRole.ApplyRole:
            self._accept()

    # ── Icon editor / creator tab ────────────────────────────────────────
    def _build_editor_tab(self, parent):
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(0, layout_spacing(), 0, 0)
        layout.setSpacing(layout_spacing())

        # Left: tools (QGroupBox + QToolButtons with theme icons)
        tools = QGroupBox("Tools")
        tools.setFixedWidth(180)
        tl = QVBoxLayout(tools)

        self.editor_tool_group = QButtonGroup(self)
        self.editor_tool_group.setExclusive(True)
        self._tool_btns = {}
        tool_defs = (
            ("pen", "Pen", ("draw-brush", "edit-draw")),
            ("eraser", "Eraser", ("draw-eraser", "edit-delete")),
            ("fill", "Fill", ("fill-color", "color-fill")),
            ("picker", "Picker", ("color-picker", "gtk-color-picker")),
        )
        for key, label, icons in tool_defs:
            b = QToolButton()
            b.setText(label)
            b.setIcon(theme_icon(*icons))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda checked, k=key: self._editor_set_tool(k))
            self.editor_tool_group.addButton(b)
            self._tool_btns[key] = b
            tl.addWidget(b)
        self._tool_btns["pen"].setChecked(True)

        tl.addWidget(QLabel("Color"))
        self.color_btn = QPushButton("Choose…")
        self.color_btn.setIcon(theme_icon("color-management", "fill-color"))
        self.color_btn.clicked.connect(self._editor_pick_color)
        tl.addWidget(self.color_btn)

        tl.addWidget(QLabel("Canvas size"))
        self.size_combo = QComboBox()
        for s in (16, 32, 48, 64, 128, 256, 512):
            self.size_combo.addItem(f"{s} × {s}", s)
        self.size_combo.setCurrentIndex(3)  # 64
        self.size_combo.currentIndexChanged.connect(self._editor_resize)
        tl.addWidget(self.size_combo)

        self.grid_check = QCheckBox("Show pixel grid")
        self.grid_check.setChecked(True)
        self.grid_check.toggled.connect(self._editor_toggle_grid)
        tl.addWidget(self.grid_check)

        tl.addStretch(1)

        # History: undo / redo / clear
        hist_row = QHBoxLayout()
        hist_row.setSpacing(6)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setIcon(theme_icon("edit-undo", "edit-undo"))
        self.undo_btn.setToolTip("Undo last change (Ctrl+Z)")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._editor_undo)
        hist_row.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setIcon(theme_icon("edit-redo", "edit-redo"))
        self.redo_btn.setToolTip("Redo (Ctrl+Shift+Z or Ctrl+Y)")
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._editor_redo)
        hist_row.addWidget(self.redo_btn)
        tl.addLayout(hist_row)

        clear_btn = QPushButton("Clear canvas")
        clear_btn.setIcon(theme_icon("edit-clear", "edit-delete"))
        clear_btn.setToolTip("Erase everything (can be undone)")
        clear_btn.clicked.connect(lambda: self.pixel_canvas.clear())
        tl.addWidget(clear_btn)

        layout.addWidget(tools)

        # Center: canvas
        canvas_box = QGroupBox("Canvas")
        center = QVBoxLayout(canvas_box)
        center.addWidget(make_hint_label(
            "Draw with the pen, or import a photo or logo. "
            f"Imports are always fitted into a {STANDARD_ICON_SIZE}×{STANDARD_ICON_SIZE} canvas. "
            "Undo last step with Ctrl+Z."
        ))
        self.pixel_canvas = PixelCanvas(64)
        self.pixel_canvas.changed.connect(self._editor_on_change)
        self.pixel_canvas.history_changed.connect(self._editor_update_history_buttons)
        center.addWidget(self.pixel_canvas, stretch=1)
        layout.addWidget(canvas_box, stretch=1)

        # Extra Redo for Ctrl+Y (menu already has Ctrl+Shift+Z via StandardKey.Redo)
        self._redo_sc_y = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._redo_sc_y.setContext(Qt.ShortcutContext.WindowShortcut)
        self._redo_sc_y.activated.connect(self._editor_redo)

        # Right: actions + library
        right = QGroupBox("Library")
        right.setFixedWidth(260)
        rl = QVBoxLayout(right)

        import_btn = QPushButton("Import image…")
        import_btn.setIcon(theme_icon("document-open", "document-import"))
        import_btn.clicked.connect(self._editor_import)
        rl.addWidget(import_btn)
        rl.addWidget(make_hint_label(
            f"PNG, JPG, WEBP, BMP, GIF — scaled to {STANDARD_ICON_SIZE}×{STANDARD_ICON_SIZE}"
        ))

        rl.addWidget(QLabel("Name"))
        self.editor_name = QLineEdit()
        self.editor_name.setPlaceholderText("e.g. My custom icon")
        self.editor_name.setClearButtonEnabled(True)
        self.editor_name.setToolTip(
            "File name used when saving. You can also set or change this in the save dialog."
        )
        rl.addWidget(self.editor_name)

        # Neither Save is setDefault — they are peer actions in a side panel.
        # Accenting only the first made “Save and use in Map” look secondary by mistake.
        save_btn = QPushButton("Save icon")
        save_btn.setIcon(theme_icon("document-save", "document-save-as"))
        save_btn.setAutoDefault(False)
        save_btn.setDefault(False)
        save_btn.setToolTip(
            "Save the canvas as a PNG in your icon library.\n"
            "Does not change any application."
        )
        save_btn.clicked.connect(self._editor_save)
        rl.addWidget(save_btn)

        use_row = QHBoxLayout()
        use_row.setSpacing(4)
        use_btn = QPushButton("Save and use in Map")
        use_btn.setIcon(theme_icon("go-next", "dialog-ok-apply"))
        use_btn.setAutoDefault(False)
        use_btn.setDefault(False)
        use_btn.setToolTip(
            "Save the icon, switch to Map, and select it so you can assign it to an app."
        )
        use_btn.clicked.connect(self._editor_save_and_use)
        use_row.addWidget(use_btn, stretch=1)

        use_help = QToolButton()
        use_help.setText("?")
        use_help.setToolTip("What does this do?")
        use_help.setAutoRaise(True)
        use_help.setFixedSize(28, 28)
        help_icon = theme_icon("help-about", "help-hint", "dialog-question")
        if not help_icon.isNull():
            use_help.setIcon(help_icon)
            use_help.setText("")
        use_help.clicked.connect(self._show_help_dialog)
        use_row.addWidget(use_help)
        rl.addLayout(use_row)

        self.editor_status = QLabel("")
        self.editor_status.setWordWrap(True)
        rl.addWidget(self.editor_status)

        rl.addWidget(make_hint_label(f"Stored in {LIBRARY_DIR}"))

        self.library_list = QListWidget()
        self.library_list.setIconSize(QSize(32, 32))
        self.library_list.setAlternatingRowColors(True)
        self.library_list.itemDoubleClicked.connect(self._editor_open_library_item)
        rl.addWidget(self.library_list, stretch=1)

        lib_btn_row = QHBoxLayout()
        lib_btn_row.setSpacing(6)

        open_lib = QPushButton("Open in Map")
        open_lib.setIcon(theme_icon("go-jump", "go-next"))
        open_lib.setToolTip(
            "Take the selected library icon to Map without re-saving the canvas."
        )
        open_lib.clicked.connect(self._editor_library_to_map)
        lib_btn_row.addWidget(open_lib, stretch=1)

        delete_lib = QPushButton("Delete")
        delete_lib.setIcon(theme_icon("edit-delete", "edit-clear"))
        delete_lib.setToolTip("Delete the selected custom icon permanently from your library.")
        delete_lib.clicked.connect(self._editor_library_delete)
        lib_btn_row.addWidget(delete_lib)

        equalize_widths([open_lib, delete_lib])
        rl.addLayout(lib_btn_row)

        layout.addWidget(right)

        self._editor_update_color_btn()
        self._refresh_library_list()

    def _editor_set_tool(self, tool):
        self.pixel_canvas.tool = tool
        for k, b in self._tool_btns.items():
            b.setChecked(k == tool)

    def _editor_pick_color(self):
        col = QColorDialog.getColor(
            self.pixel_canvas.color, self, "Pen color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if col.isValid():
            self.pixel_canvas.color = col
            self._editor_update_color_btn()
            if self.pixel_canvas.tool == "picker":
                self._editor_set_tool("pen")

    def _editor_update_color_btn(self):
        c = self.pixel_canvas.color
        # Small color swatch icon so we stay on Breeze chrome, not custom button skins
        pix = QPixmap(18, 18)
        pix.fill(c)
        self.color_btn.setIcon(QIcon(pix))
        label = c.name(QColor.NameFormat.HexArgb) if c.alpha() < 255 else c.name()
        self.color_btn.setText(label)

    def _editor_update_history_buttons(self):
        can_u = self.pixel_canvas.can_undo()
        can_r = self.pixel_canvas.can_redo()
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(can_u)
        if hasattr(self, "redo_btn"):
            self.redo_btn.setEnabled(can_r)
        # Menu Undo is contextual (Create canvas vs Map apply stack)
        self._sync_undo_actions()

    def _editor_undo(self):
        # Only act when Create tab is visible (avoid surprising Map)
        if hasattr(self, "main_tabs") and self.main_tabs.currentIndex() != 1:
            return
        if self.pixel_canvas.undo():
            self._editor_sync_size_combo(self.pixel_canvas.grid_size)
            self.editor_status.setText("Undid last change")
            QTimer.singleShot(1500, lambda: self.editor_status.setText(""))

    def _editor_redo(self):
        if hasattr(self, "main_tabs") and self.main_tabs.currentIndex() != 1:
            return
        if self.pixel_canvas.redo():
            self._editor_sync_size_combo(self.pixel_canvas.grid_size)
            self.editor_status.setText("Redid change")
            QTimer.singleShot(1500, lambda: self.editor_status.setText(""))

    def _editor_resize(self):
        size = self.size_combo.currentData()
        if size:
            self.pixel_canvas.resize_grid(size)

    def _editor_toggle_grid(self, on):
        self.pixel_canvas.show_grid = on
        self.pixel_canvas.update()

    def _editor_on_change(self):
        # If picker grabbed a color, refresh swatch
        if self.pixel_canvas.tool == "picker":
            self._editor_update_color_btn()

    def _editor_sync_size_combo(self, size):
        """Keep the canvas-size dropdown in sync without re-triggering resize."""
        if not hasattr(self, "size_combo"):
            return
        idx = self.size_combo.findData(int(size))
        if idx < 0:
            return
        self.size_combo.blockSignals(True)
        self.size_combo.setCurrentIndex(idx)
        self.size_combo.blockSignals(False)

    def _editor_export_image(self, img):
        """Normalize canvas to STANDARD_ICON_SIZE square for the library.

        Pixel art (smaller grids) is enlarged with nearest-neighbor so edges
        stay crisp; larger images are reduced smoothly.
        """
        target = STANDARD_ICON_SIZE
        if img.isNull():
            return img
        if img.width() == target and img.height() == target:
            return img.convertToFormat(QImage.Format.Format_ARGB32)
        # Non-square → letterbox into square first
        if img.width() != img.height():
            square = QImage(max(img.width(), img.height()),
                            max(img.width(), img.height()),
                            QImage.Format.Format_ARGB32)
            square.fill(Qt.GlobalColor.transparent)
            p = QPainter(square)
            p.drawImage(
                (square.width() - img.width()) // 2,
                (square.height() - img.height()) // 2,
                img,
            )
            p.end()
            img = square
        mode = (
            Qt.TransformationMode.FastTransformation
            if img.width() <= target
            else Qt.TransformationMode.SmoothTransformation
        )
        return img.scaled(
            target, target,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            mode,
        ).convertToFormat(QImage.Format.Format_ARGB32)

    def _editor_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import image for icon",
            DOWNLOADS_DIR_DEFAULT,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.svg *.svgz "
            "*.PNG *.JPG *.JPEG *.WEBP *.SVG);;All files (*)",
        )
        if not path:
            return
        src = QImage(path)
        if src.isNull():
            QMessageBox.warning(self, "Import failed", f"Could not load:\n{path}")
            return
        src = src.convertToFormat(QImage.Format.Format_ARGB32)
        # Position / zoom so a region of a larger image can become the icon
        dlg = ImportPositionDialog(src, canvas_size=STANDARD_ICON_SIZE, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cropped = dlg.result_image()
        if cropped.isNull():
            QMessageBox.warning(self, "Import failed", "Could not create crop.")
            return
        self.pixel_canvas.set_image(cropped, record_undo=True)
        self._editor_sync_size_combo(STANDARD_ICON_SIZE)
        base = os.path.splitext(os.path.basename(path))[0]
        if not self.editor_name.text().strip():
            self.editor_name.setText(base)
        self.editor_status.setText(
            f"Imported {os.path.basename(path)} → {STANDARD_ICON_SIZE}×{STANDARD_ICON_SIZE} (positioned)"
        )
        QTimer.singleShot(2500, lambda: self.editor_status.setText(""))

    def _editor_sanitize_name(self, name):
        name = (name or "").strip()
        if not name:
            name = f"icon-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        # Drop path separators / traversal before char filter
        name = name.replace("\\", "/").split("/")[-1]
        name = name.replace("..", ".")
        safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip(".-") or "icon"
        # Collapse ".." remnants and force basename
        safe = os.path.basename(safe)
        if not safe or safe in (".", ".."):
            safe = "icon"
        if not safe.lower().endswith(".png"):
            safe += ".png"
        return safe

    def _editor_save_path(self, name=None):
        if name is None:
            name = self.editor_name.text()
        safe = self._editor_sanitize_name(name)
        path = os.path.join(LIBRARY_DIR, safe)
        # Hard guard: never write outside the icon library
        if not path_is_under(path, LIBRARY_DIR):
            path = os.path.join(LIBRARY_DIR, "icon.png")
        return path

    def _editor_canvas_has_content_to_save(self):
        """False when the canvas is blank or has not been edited since last save."""
        if not self.pixel_canvas.is_dirty():
            return False
        if self.pixel_canvas.is_blank():
            return False
        return True

    def _editor_confirm_save_canvas(self):
        """Ask before writing; let the user set the icon name.

        Returns (True, name) on Yes, or (False, None) on No/cancel.
        name may be '' → auto timestamped filename.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Save icon")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(layout_spacing())

        title = QLabel("Do you want the current canvas saved as an icon?")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        title.setWordWrap(True)
        lay.addWidget(title)
        lay.addWidget(make_hint_label(
            "Choose a name for the file in your icon library. "
            "Leave empty to use an automatic name."
        ))

        form = QFormLayout()
        name_edit = QLineEdit(self.editor_name.text().strip())
        name_edit.setPlaceholderText("e.g. My custom icon")
        name_edit.setClearButtonEnabled(True)
        form.addRow("Name:", name_edit)
        lay.addLayout(form)

        preview = make_hint_label("")
        lay.addWidget(preview)

        def update_preview(_text=None):
            safe = self._editor_sanitize_name(name_edit.text())
            preview.setText(f"Will save as: {safe}")

        name_edit.textChanged.connect(update_preview)
        update_preview()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        buttons.button(QDialogButtonBox.StandardButton.Yes).setText("Yes")
        buttons.button(QDialogButtonBox.StandardButton.No).setText("No")
        buttons.button(QDialogButtonBox.StandardButton.Yes).clicked.connect(dlg.accept)
        buttons.button(QDialogButtonBox.StandardButton.No).clicked.connect(dlg.reject)
        lay.addWidget(buttons)

        name_edit.setFocus()
        name_edit.selectAll()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False, None
        name = name_edit.text().strip()
        self.editor_name.setText(name)
        return True, name

    def _editor_save(self, silent=False, ask_confirm=True):
        if not self._editor_canvas_has_content_to_save():
            if not silent:
                if not self.pixel_canvas.is_dirty():
                    msg = "Nothing to save — the canvas is unchanged."
                else:
                    msg = "Nothing to save — the canvas is empty."
                self.editor_status.setText(msg)
                QTimer.singleShot(3000, lambda: self.editor_status.setText(""))
            return None

        chosen_name = self.editor_name.text().strip()
        if ask_confirm:
            ok, name = self._editor_confirm_save_canvas()
            if not ok:
                return None
            chosen_name = name  # may be ""

        path = self._editor_save_path(chosen_name)
        # Avoid silently overwriting without notice
        if os.path.isfile(path):
            overwrite = QMessageBox.question(
                self,
                "Replace file?",
                f"“{os.path.basename(path)}” already exists.\nDo you want to replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if overwrite != QMessageBox.StandardButton.Yes:
                return None

        os.makedirs(LIBRARY_DIR, exist_ok=True)
        if not path_is_under(path, LIBRARY_DIR):
            QMessageBox.warning(self, "Save failed", "Refusing to write outside the icon library.")
            return None
        # Always write STANDARD_ICON_SIZE² so Map / apply / library stay uniform
        export = self._editor_export_image(self.pixel_canvas.image())
        # Atomic save: write temp sibling then os.replace (no half-written PNG)
        try:
            fd, tmp = tempfile.mkstemp(prefix=".kappicon-", suffix=".png", dir=LIBRARY_DIR)
            os.close(fd)
        except OSError as e:
            QMessageBox.warning(self, "Save failed", f"Could not create temp file:\n{e}")
            return None
        try:
            if not export.save(tmp, "PNG"):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                QMessageBox.warning(self, "Save failed", f"Could not write:\n{path}")
                return None
            os.replace(tmp, path)
        except Exception as e:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            QMessageBox.warning(self, "Save failed", f"Could not write:\n{e}")
            return None
        self.pixel_canvas.mark_clean()
        self._refresh_library_list()
        # Also ensure Map source can see it
        if path not in self.icon_files:
            self.icon_files.append(path)
        if not silent:
            self.editor_status.setText(f"Saved {os.path.basename(path)}")
            QTimer.singleShot(2500, lambda: self.editor_status.setText(""))
        return path

    def _show_help_dialog(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "kAppIcon Help & Workflow",
            "<h2>kAppIcon Documentation</h2>"
            "<p>kAppIcon is a Linux utility to customize launcher icons for your installed applications "
            "following the freedesktop.org desktop entry specifications.</p>"
            
            "<h3>🔄 Workflow 1: Map an Icon to an Application</h3>"
            "<ol>"
            "<li><b>Select Icon Source</b> (Step 1): "
            "<i>From file</i> (downloaded PNGs/ICNS), "
            "<i>From another app</i> (icons used by installed launchers), or "
            "<i>From icon theme</i> (browse an installed pack such as Tela or WhiteSur). "
            "Select the icon in the list.</li>"
            "<li><b>Select Target Application</b> (Step 2): Select the application whose launcher you want to customize.</li>"
            "<li><b>Apply</b>: Click <i>Apply icon</i> to copy the launcher into your local user directory and change the Icon field.</li>"
            "</ol>"
            
            "<h3>🎨 Workflow 2: Create Custom Icons</h3>"
            "<ol>"
            "<li>Open the <b>Create</b> tab.</li>"
            f"<li>Set a canvas size for pixel art (16×16 … 512×512), or click <i>Import image…</i> — "
            f"imports are always fitted to <b>{STANDARD_ICON_SIZE}×{STANDARD_ICON_SIZE}</b>.</li>"
            "<li>Draw pixel art using the <b>Pen</b>, <b>Eraser</b>, <b>Fill</b>, and <b>Color Picker</b> tools.</li>"
            "<li><b>Undo</b> / <b>Redo</b> (Ctrl+Z / Ctrl+Shift+Z) reverse mistakes without clearing the canvas.</li>"
            f"<li>Save writes a <b>{STANDARD_ICON_SIZE}×{STANDARD_ICON_SIZE}</b> PNG to your icon library "
            "(same size for every icon).</li>"
            "<li>Click <i>Save icon</i> or <i>Save and use in Map</i>.</li>"
            "</ol>"
            
            "<h3>🛠️ Resetting & Library Maintenance</h3>"
            "<ul>"
            "<li><b>Reset launcher icon</b>: Select any application in the Map tab and click <b>Reset to system icon</b>. "
            "This restores the package icon when a system .desktop exists; other custom desktop sections are preserved.</li>"
            "<li><b>Delete custom designs</b>: In the Create tab under <i>Your Icons</i>, select any icon and click <b>Delete</b> "
            "to permanently delete the file from your local icon library.</li>"
            "<li><b>Backups</b>: In the Settings tab, you can enable auto-backups or revert overrides using the backup restorer.</li>"
            "</ul>",
        )

    def _editor_save_and_use(self):
        path = self._editor_save_path()
        if not self.pixel_canvas.is_dirty() and os.path.isfile(path):
            self._add_icon_file(path)
            self._set_icon_source("files")
            self.main_tabs.setCurrentIndex(0)  # Map tab
            self.plan_label.setText(
                f"Icon ready: {os.path.basename(path)}. Now choose the app to change."
            )
            return

        if not self._editor_canvas_has_content_to_save():
            if not self.pixel_canvas.is_dirty():
                msg = "Nothing to save — the canvas is unchanged."
            else:
                msg = "Nothing to save — the canvas is empty."
            self.editor_status.setText(msg)
            QTimer.singleShot(3000, lambda: self.editor_status.setText(""))
            QMessageBox.information(self, "Save and use in Map", msg)
            return

        # Confirm + name, then save (no second prompt)
        path = self._editor_save(silent=True, ask_confirm=True)
        if not path:
            return
        self._add_icon_file(path)
        self._set_icon_source("files")
        self.main_tabs.setCurrentIndex(0)  # Map tab
        self.editor_status.setText("Saved — pick an app on Map, then Apply")
        self.plan_label.setText(
            f"Icon ready: {os.path.basename(path)}. Now choose the app to change."
        )

    def _refresh_library_list(self):
        self.library_list.clear()
        if not os.path.isdir(LIBRARY_DIR):
            return
        files = []
        for f in os.listdir(LIBRARY_DIR):
            path = os.path.join(LIBRARY_DIR, f)
            if os.path.isfile(path) and os.path.splitext(f)[1].lower() in ICON_EXTENSIONS:
                files.append(path)
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for path in files:
            display_name = os.path.splitext(os.path.basename(path))[0]
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            pix = QPixmap(path)
            if not pix.isNull():
                item.setIcon(QIcon(pix.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)))
            self.library_list.addItem(item)

    def _editor_open_library_item(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            # Re-open at the standard size so re-edits stay uniform with imports
            self.pixel_canvas.load_from_file(
                path, fit=True, size=STANDARD_ICON_SIZE
            )
            self._editor_sync_size_combo(STANDARD_ICON_SIZE)
            # Matches disk until the user draws again
            self.pixel_canvas.mark_clean()
            self.editor_name.setText(os.path.splitext(os.path.basename(path))[0])

    def _editor_library_to_map(self):
        item = self.library_list.currentItem()
        if not item:
            self.editor_status.setText("Select an icon in Your Icons first")
            QTimer.singleShot(2000, lambda: self.editor_status.setText(""))
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self._add_icon_file(path)
            self._set_icon_source("files")
            self.main_tabs.setCurrentIndex(0)

    def _editor_library_delete(self):
        item = self.library_list.currentItem()
        if not item:
            self.editor_status.setText("Select an icon to delete first")
            QTimer.singleShot(2000, lambda: self.editor_status.setText(""))
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            from PyQt6.QtWidgets import QMessageBox
            # Only allow deleting files that live inside the icon library
            if not path_is_under(path, LIBRARY_DIR):
                QMessageBox.warning(
                    self, "Error",
                    "Refusing to delete a file outside the icon library.",
                )
                return
            filename = os.path.basename(path)
            confirm = QMessageBox.question(
                self,
                "Delete Icon?",
                f"Are you sure you want to permanently delete “{filename}” from your icon library?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(path)
                    self._refresh_library_list()
                    if path in self.icon_files:
                        self.icon_files.remove(path)
                        self._fill_file_list(self.icon_files)
                    self.editor_status.setText(f"Deleted {filename}")
                    QTimer.singleShot(2500, lambda: self.editor_status.setText(""))
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not delete file:\n{e}")

    # ── Settings tab (KDE form / group box layout) ───────────────────────
    def _build_settings_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, layout_spacing(), 0, 0)
        layout.setSpacing(layout_spacing())

        look = QGroupBox("Appearance")
        look_l = QVBoxLayout(look)
        look_l.addWidget(make_hint_label(
            "Widget style stays Breeze. Colors can follow the system or be forced light/dark."
        ))
        theme_row = QHBoxLayout()
        self.theme_group = QButtonGroup(self)
        self.theme_system = QRadioButton("System")
        self.theme_light = QRadioButton("Light")
        self.theme_dark = QRadioButton("Dark")
        self.theme_group.addButton(self.theme_system)
        self.theme_group.addButton(self.theme_light)
        self.theme_group.addButton(self.theme_dark)
        cur = self.settings.value("appearance/theme", "system", type=str)
        {"light": self.theme_light, "dark": self.theme_dark}.get(cur, self.theme_system).setChecked(True)
        self.theme_system.toggled.connect(lambda on: on and self._on_theme("system"))
        self.theme_light.toggled.connect(lambda on: on and self._on_theme("light"))
        self.theme_dark.toggled.connect(lambda on: on and self._on_theme("dark"))
        theme_row.addWidget(self.theme_system)
        theme_row.addWidget(self.theme_light)
        theme_row.addWidget(self.theme_dark)
        theme_row.addStretch(1)
        look_l.addLayout(theme_row)
        layout.addWidget(look)

        shape_box = QGroupBox("Applied icon shape")
        shape_l = QVBoxLayout(shape_box)
        shape_l.addWidget(make_hint_label(
            "How icons are shaped when you Apply them. "
            "No guessing — pick the look you want."
        ))
        self.shape_group = QButtonGroup(self)
        self.shape_as_is = QRadioButton("As designed")
        self.shape_square = QRadioButton("Square")
        self.shape_rounded = QRadioButton("Rounded corners")
        self.shape_circle = QRadioButton("Circle")
        self.shape_group.addButton(self.shape_as_is)
        self.shape_group.addButton(self.shape_square)
        self.shape_group.addButton(self.shape_rounded)
        self.shape_group.addButton(self.shape_circle)
        cur_shape = self.settings.value("icons/shape", "as-is", type=str)
        {
            "square": self.shape_square,
            "rounded": self.shape_rounded,
            "circle": self.shape_circle,
        }.get(cur_shape, self.shape_as_is).setChecked(True)
        self.shape_as_is.toggled.connect(lambda on: on and self._on_icon_shape("as-is"))
        self.shape_square.toggled.connect(lambda on: on and self._on_icon_shape("square"))
        self.shape_rounded.toggled.connect(lambda on: on and self._on_icon_shape("rounded"))
        self.shape_circle.toggled.connect(lambda on: on and self._on_icon_shape("circle"))
        shape_row = QHBoxLayout()
        shape_row.addWidget(self.shape_as_is)
        shape_row.addWidget(self.shape_square)
        shape_row.addWidget(self.shape_rounded)
        shape_row.addWidget(self.shape_circle)
        shape_row.addStretch(1)
        shape_l.addLayout(shape_row)
        shape_l.addWidget(make_hint_label(
            "As designed: keep the file’s own shape (best for themed SVGs). "
            "Square / Rounded / Circle: re-export a PNG with that mask."
        ))
        layout.addWidget(shape_box)

        backups = QGroupBox("Backups")
        bl = QVBoxLayout(backups)
        self.backup_check = QCheckBox("Create a backup of .desktop files before changing them")
        self.backup_check.setChecked(self.settings.value("backups/enabled", False, type=bool))
        self.backup_check.toggled.connect(lambda v: self.settings.setValue("backups/enabled", v))
        bl.addWidget(self.backup_check)
        bl.addWidget(make_hint_label(
            f"Backups are stored in {BACKUP_DIR}/"
        ))
        layout.addWidget(backups)

        source = QGroupBox("Icon files")
        sf = QVBoxLayout(source)
        default_src = DOWNLOADS_DIR_DEFAULT
        sf.addWidget(QLabel("Source folder"))
        self.source_input = QLineEdit(self.settings.value("source/folder", default_src, type=str))
        self.source_input.setClearButtonEnabled(True)
        self.source_input.editingFinished.connect(self._on_source_change)
        browse = QPushButton("Browse…")
        browse.setIcon(theme_icon("folder-open", "document-open"))
        browse.clicked.connect(self._browse_source)
        src_row = QHBoxLayout()
        src_row.addWidget(self.source_input, stretch=1)
        src_row.addWidget(browse)
        sf.addLayout(src_row)
        # Full-width hint (FormLayout was wrapping this awkwardly in a narrow field column)
        sf.addWidget(make_hint_label(
            "Used by Map → From file. Icons you create are kept in the library automatically."
        ))
        layout.addWidget(source)

        maint = QGroupBox("Maintenance")
        ml = QHBoxLayout(maint)
        restore_btn = QPushButton("Restore backup…")
        restore_btn.setIcon(theme_icon("edit-undo", "document-revert"))
        restore_btn.clicked.connect(self._restore_backup)
        ml.addWidget(restore_btn)
        self._restore_status = QLabel("")
        ml.addWidget(self._restore_status)

        refresh_btn = QPushButton("Refresh icon cache")
        refresh_btn.setIcon(theme_icon("view-refresh", "system-reboot"))
        refresh_btn.clicked.connect(self._force_refresh)
        ml.addWidget(refresh_btn)
        self._refresh_status = QLabel("")
        ml.addWidget(self._refresh_status)
        equalize_widths([restore_btn, refresh_btn])
        ml.addStretch(1)
        layout.addWidget(maint)

        about = QGroupBox("About")
        al = QVBoxLayout(about)
        al.addWidget(QLabel("kAppIcon — change, create, and map application icons."))
        al.addWidget(make_hint_label(
            "Designed for Plasma / Breeze. Icons follow the freedesktop.org desktop entry standard."
        ))
        layout.addWidget(about)

        layout.addStretch(1)

    # ── Overrides tab (user launcher overrides) ──────────────────────────
    def _build_overrides_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, layout_spacing(), 0, 0)
        layout.setSpacing(layout_spacing())

        layout.addWidget(make_hint_label(
            "System apps whose icons you changed (user .desktop with a different Icon=). "
            "Steam/game shortcuts and other user-only launchers are hidden. "
            "The right panel shows your current icon and the original system icon "
            "that Reset will restore."
        ))

        filt_row = QHBoxLayout()
        self.overrides_search = QLineEdit()
        self.overrides_search.setClearButtonEnabled(True)
        self.overrides_search.setPlaceholderText("Filter overrides…")
        self.overrides_search.textChanged.connect(self._filter_overrides_list)
        filt_row.addWidget(self.overrides_search, stretch=1)
        refresh = QPushButton("Refresh")
        refresh.setIcon(theme_icon("view-refresh", "system-reboot"))
        refresh.clicked.connect(self._refresh_overrides_list)
        filt_row.addWidget(refresh)
        layout.addLayout(filt_row)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)

        # Left: override list
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(layout_spacing())
        self.overrides_list = QListWidget()
        self.overrides_list.setIconSize(QSize(32, 32))
        self.overrides_list.setAlternatingRowColors(True)
        self.overrides_list.itemDoubleClicked.connect(
            lambda _i: self._overrides_open_in_map()
        )
        left_l.addWidget(self.overrides_list, stretch=1)
        body.addWidget(left)

        # Right: current vs original (system) icon preview
        right = QWidget()
        right.setMinimumWidth(220)
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(layout_spacing())

        self.overrides_title = QLabel("Select an override")
        title_font = self.overrides_title.font()
        title_font.setBold(True)
        self.overrides_title.setFont(title_font)
        self.overrides_title.setWordWrap(True)
        right_l.addWidget(self.overrides_title)

        compare = QHBoxLayout()
        compare.setSpacing(layout_spacing())

        cur_box = QGroupBox("Current (yours)")
        cur_l = QVBoxLayout(cur_box)
        self.overrides_current_icon = QLabel("—")
        self.overrides_current_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overrides_current_icon.setMinimumSize(96, 96)
        self.overrides_current_icon.setFrameShape(QFrame.Shape.StyledPanel)
        self.overrides_current_icon.setFrameShadow(QFrame.Shadow.Sunken)
        cur_l.addWidget(self.overrides_current_icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.overrides_current_meta = make_hint_label("")
        self.overrides_current_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overrides_current_meta.setWordWrap(True)
        cur_l.addWidget(self.overrides_current_meta)
        compare.addWidget(cur_box, stretch=1)

        orig_box = QGroupBox("Original (system)")
        orig_l = QVBoxLayout(orig_box)
        self.overrides_original_icon = QLabel("—")
        self.overrides_original_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overrides_original_icon.setMinimumSize(96, 96)
        self.overrides_original_icon.setFrameShape(QFrame.Shape.StyledPanel)
        self.overrides_original_icon.setFrameShadow(QFrame.Shadow.Sunken)
        self.overrides_original_icon.setToolTip(
            "This is the icon restored when you click Reset to system icon"
        )
        orig_l.addWidget(self.overrides_original_icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.overrides_original_meta = make_hint_label("")
        self.overrides_original_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overrides_original_meta.setWordWrap(True)
        orig_l.addWidget(self.overrides_original_meta)
        compare.addWidget(orig_box, stretch=1)

        right_l.addLayout(compare)

        self.overrides_detail = QLabel("")
        self.overrides_detail.setWordWrap(True)
        self.overrides_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        right_l.addWidget(self.overrides_detail)
        right_l.addStretch(1)
        body.addWidget(right)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        layout.addWidget(body, stretch=1)

        self.overrides_list.currentItemChanged.connect(
            lambda cur, _prev: self._overrides_show_detail(cur)
        )

        btn_row = QHBoxLayout()
        open_map = QPushButton("Open in Map")
        open_map.setIcon(theme_icon("preferences-desktop-icons", "go-next"))
        open_map.setToolTip("Select this app on the Map tab to change its icon")
        open_map.clicked.connect(self._overrides_open_in_map)
        reset_btn = QPushButton("Reset to system icon")
        reset_btn.setIcon(theme_icon("edit-clear-all", "edit-undo", "document-revert"))
        reset_btn.setToolTip(
            "Remove your custom icon and restore the original system icon (shown on the right)"
        )
        reset_btn.clicked.connect(self._overrides_reset_selected)
        btn_row.addWidget(open_map)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        equalize_widths([open_map, reset_btn])
        layout.addLayout(btn_row)

        self.overrides_status = QLabel("")
        layout.addWidget(self.overrides_status)
        self._refresh_overrides_list()

    def _set_override_preview_label(self, label, icon_name, empty_text="—"):
        """Paint a resolved icon into a preview QLabel (or a placeholder)."""
        label.clear()
        label.setText("")
        label.setPixmap(QPixmap())
        if not icon_name:
            label.setText(empty_text)
            return
        pix = resolve_icon(icon_name, size=96)
        if pix and not pix.isNull():
            label.setPixmap(pix)
        else:
            label.setText("?")

    def _refresh_overrides_list(self):
        if not hasattr(self, "overrides_list"):
            return
        self.overrides_list.clear()
        rows = scan_user_launcher_overrides()
        for row in rows:
            label = row["display"]
            icon_val = row["icon"] or "(no Icon=)"
            sys_icon = row.get("system_icon") or "(empty)"
            item = QListWidgetItem(f"{label}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(
                f"{row['desktop_id']}\n"
                f"Current Icon={icon_val}\n"
                f"Original Icon={sys_icon}\n"
                f"{row['path']}"
            )
            # List row shows the current (custom) icon
            pix = resolve_icon(row["icon"]) if row["icon"] else None
            if pix:
                item.setIcon(QIcon(pix))
            elif not row["icon_ok"]:
                item.setIcon(theme_icon("image-missing", "dialog-warning"))
            self.overrides_list.addItem(item)
        n = self.overrides_list.count()
        self.overrides_status.setText(
            f"{n} icon override(s) (customized system apps)"
            if n else "No icon overrides yet — change an app on Map to see it here"
        )
        self._filter_overrides_list(
            self.overrides_search.text() if hasattr(self, "overrides_search") else ""
        )
        # Clear right panel when list is rebuilt
        self._overrides_show_detail(self.overrides_list.currentItem())

    def _filter_overrides_list(self, text=""):
        if not hasattr(self, "overrides_list"):
            return
        q = (text or "").lower().strip()
        for i in range(self.overrides_list.count()):
            item = self.overrides_list.item(i)
            row = item.data(Qt.ItemDataRole.UserRole) or {}
            hay = " ".join([
                row.get("display", ""),
                row.get("desktop_id", ""),
                row.get("icon", ""),
                row.get("system_icon", ""),
                row.get("path", ""),
            ]).lower()
            item.setHidden(bool(q) and q not in hay)

    def _overrides_show_detail(self, item):
        if not hasattr(self, "overrides_detail"):
            return
        if not item:
            if hasattr(self, "overrides_title"):
                self.overrides_title.setText("Select an override")
            self._set_override_preview_label(self.overrides_current_icon, None)
            self._set_override_preview_label(self.overrides_original_icon, None)
            if hasattr(self, "overrides_current_meta"):
                self.overrides_current_meta.setText("")
            if hasattr(self, "overrides_original_meta"):
                self.overrides_original_meta.setText("")
            self.overrides_detail.setText("")
            return

        row = item.data(Qt.ItemDataRole.UserRole) or {}
        display = row.get("display", "") or row.get("desktop_id", "")
        self.overrides_title.setText(display)

        cur_icon = row.get("icon") or ""
        sys_icon = row.get("system_icon") or ""
        self._set_override_preview_label(
            self.overrides_current_icon, cur_icon or None, empty_text="(none)"
        )
        self.overrides_current_meta.setText(
            f"<code>{cur_icon or '(empty)'}</code>"
            + ("" if row.get("icon_ok") else " · unresolved")
        )

        if row.get("system_path"):
            self._set_override_preview_label(
                self.overrides_original_icon, sys_icon or None, empty_text="(none)"
            )
            self.overrides_original_meta.setText(
                f"<code>{sys_icon or '(empty)'}</code><br/>Restored on Reset"
            )
        else:
            self._set_override_preview_label(
                self.overrides_original_icon, None, empty_text="n/a"
            )
            self.overrides_original_meta.setText("No system .desktop")

        lines = [
            f"<code>{row.get('desktop_id', '')}</code>",
            f"User: <code>{row.get('path', '')}</code>",
        ]
        if row.get("system_path"):
            lines.append(f"System: <code>{row['system_path']}</code>")
        else:
            lines.append("No matching system .desktop (user-only launcher).")
        self.overrides_detail.setText("<br/>".join(lines))

    def _overrides_selected_row(self):
        item = self.overrides_list.currentItem() if hasattr(self, "overrides_list") else None
        if not item or item.isHidden():
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _overrides_open_in_map(self):
        row = self._overrides_selected_row()
        if not row:
            QMessageBox.information(self, "Overrides", "Select an override first.")
            return
        self._jump_to_map_app(row["desktop_id"])

    def _overrides_reset_selected(self):
        row = self._overrides_selected_row()
        if not row:
            QMessageBox.information(self, "Overrides", "Select an override first.")
            return
        if not row.get("system_path"):
            QMessageBox.warning(
                self,
                "Cannot reset",
                "No system .desktop was found for this launcher.\n"
                "You can delete the user file manually if you no longer need it.",
            )
            return
        display = row.get("display") or row["desktop_id"]
        confirm = QMessageBox.question(
            self,
            "Reset Icon?",
            f"Reset “{display}” to the system icon?\n\n"
            f"System Icon={row.get('system_icon') or '(empty)'}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        # In-process reset — keep window open (same engine as Map)
        desktop = row["desktop_id"]
        display = row.get("display") or desktop
        try:
            self._set_apply_busy(True)
            with apply_lock():
                result = apply_icon_to_desktop(
                    desktop, "RESET",
                    shape=self._shape_pref(),
                    backup=self._backup_pref(),
                )
            if not result.get("noop"):
                self._push_undo(desktop, display, result.get("previous_bytes"))
            self._update_app_list_icon(desktop, result.get("icon_value") or "")
            schedule_icon_cache_refresh(self)
            self._refresh_overrides_list()
            if self.statusBar():
                self.statusBar().showMessage(
                    f"Reset {display} to the system icon", 6000
                )
        except ApplyError as e:
            QMessageBox.warning(self, "Reset failed", str(e))
        except Exception as e:
            QMessageBox.warning(self, "Reset failed", str(e))
        finally:
            self._set_apply_busy(False)

    # ── Missing icons tab ────────────────────────────────────────────────
    def _build_missing_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, layout_spacing(), 0, 0)
        layout.setSpacing(layout_spacing())

        layout.addWidget(make_hint_label(
            "Visible, runnable apps (shown in menus) whose Icon= is empty or does not "
            "resolve. Hidden helpers and system services are omitted — empty icons there "
            "are usually intentional. Use Open in Map to assign a working icon."
        ))

        filt_row = QHBoxLayout()
        self.missing_search = QLineEdit()
        self.missing_search.setClearButtonEnabled(True)
        self.missing_search.setPlaceholderText("Filter apps…")
        self.missing_search.textChanged.connect(self._filter_missing_list)
        filt_row.addWidget(self.missing_search, stretch=1)
        self.missing_kind_combo = QComboBox()
        self.missing_kind_combo.addItem("All problems", "all")
        self.missing_kind_combo.addItem("Empty Icon= only", "empty")
        self.missing_kind_combo.addItem("Unresolved name only", "unresolved")
        mk = self.missing_kind_combo.findData(self._missing_kind)
        self.missing_kind_combo.setCurrentIndex(mk if mk >= 0 else 0)
        self.missing_kind_combo.setToolTip(
            "Empty: no Icon= line value. Unresolved: name set but not found in themes."
        )
        self.missing_kind_combo.currentIndexChanged.connect(self._on_missing_kind_changed)
        filt_row.addWidget(self.missing_kind_combo)
        refresh = QPushButton("Refresh")
        refresh.setIcon(theme_icon("view-refresh", "system-reboot"))
        refresh.clicked.connect(self._refresh_missing_list)
        filt_row.addWidget(refresh)
        layout.addLayout(filt_row)

        self.missing_list = QListWidget()
        self.missing_list.setIconSize(QSize(32, 32))
        self.missing_list.setAlternatingRowColors(True)
        self.missing_list.itemDoubleClicked.connect(
            lambda _i: self._missing_open_in_map()
        )
        layout.addWidget(self.missing_list, stretch=1)

        self.missing_detail = QLabel("")
        self.missing_detail.setWordWrap(True)
        self.missing_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.missing_detail)
        self.missing_list.currentItemChanged.connect(
            lambda cur, _prev: self._missing_show_detail(cur)
        )

        btn_row = QHBoxLayout()
        open_map = QPushButton("Open in Map")
        open_map.setIcon(theme_icon("preferences-desktop-icons", "go-next"))
        open_map.clicked.connect(self._missing_open_in_map)
        btn_row.addWidget(open_map)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.missing_status = QLabel("")
        layout.addWidget(self.missing_status)
        self._refresh_missing_list()

    def _on_missing_kind_changed(self, _idx=None):
        if not hasattr(self, "missing_kind_combo"):
            return
        kind = self.missing_kind_combo.currentData() or "all"
        self._missing_kind = kind
        self.settings.setValue("missing/kind", kind)
        self._filter_missing_list(
            self.missing_search.text() if hasattr(self, "missing_search") else ""
        )

    def _refresh_missing_list(self):
        if not hasattr(self, "missing_list"):
            return
        self.missing_list.clear()
        rows = scan_apps_missing_icons(self.app_data)
        warn_icon = theme_icon("image-missing", "dialog-warning", "emblem-important")
        for row in rows:
            item = QListWidgetItem(row["display"])
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(
                f"{row['desktop_id']}\n{row['reason']}\nIcon={row['icon'] or '(empty)'}\n{row['path']}"
            )
            item.setIcon(warn_icon)
            self.missing_list.addItem(item)
        self._filter_missing_list(
            self.missing_search.text() if hasattr(self, "missing_search") else ""
        )

    def _filter_missing_list(self, text=""):
        if not hasattr(self, "missing_list"):
            return
        q = (text or "").lower().strip()
        kind = getattr(self, "_missing_kind", "all")
        visible = 0
        for i in range(self.missing_list.count()):
            item = self.missing_list.item(i)
            row = item.data(Qt.ItemDataRole.UserRole) or {}
            hay = " ".join([
                row.get("display", ""),
                row.get("desktop_id", ""),
                row.get("icon", ""),
                row.get("reason", ""),
            ]).lower()
            reason = row.get("reason") or ""
            kind_ok = True
            if kind == "empty":
                kind_ok = reason.startswith("No Icon")
            elif kind == "unresolved":
                kind_ok = "not found" in reason.lower() or reason == "Icon not found"
            text_ok = (not q) or (q in hay)
            hide = not (kind_ok and text_ok)
            item.setHidden(hide)
            if not hide:
                visible += 1
        if hasattr(self, "missing_status"):
            self.missing_status.setText(
                f"{visible} visible app(s) with missing or unresolved icons"
                if visible
                else "No matching apps — try another filter or Refresh"
            )

    def _missing_show_detail(self, item):
        if not item:
            self.missing_detail.setText("")
            return
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        self.missing_detail.setText(
            f"<b>{row.get('display', '')}</b> — <code>{row.get('desktop_id', '')}</code><br/>"
            f"{row.get('reason', '')}<br/>"
            f"Icon=: <code>{row.get('icon') or '(empty)'}</code><br/>"
            f"<code>{row.get('path', '')}</code>"
        )

    def _missing_open_in_map(self):
        item = self.missing_list.currentItem() if hasattr(self, "missing_list") else None
        if not item or item.isHidden():
            QMessageBox.information(self, "Missing icons", "Select an app first.")
            return
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        self._jump_to_map_app(row.get("desktop_id"))

    def _jump_to_map_app(self, desktop_id):
        """Switch to Map and select the given application in step 2.

        Selection is deferred until after the Map tab is shown. Selecting a
        QListWidget item while its parent tab is still hidden often fails to
        apply current-item highlight and scroll, which made Open in Map look
        like a no-op.
        """
        if not desktop_id or not hasattr(self, "app_list"):
            return
        self.main_tabs.setCurrentIndex(0)

        def _select():
            if not hasattr(self, "app_list"):
                return
            # Clear filter so the target row is not left hidden
            if hasattr(self, "app_search"):
                # Block signals while clearing so we control visibility below
                self.app_search.blockSignals(True)
                self.app_search.clear()
                self.app_search.blockSignals(False)
            for i in range(self.app_list.count()):
                self.app_list.item(i).setHidden(False)

            found = None
            for i in range(self.app_list.count()):
                item = self.app_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == desktop_id:
                    found = item
                    break

            if not found:
                QMessageBox.information(
                    self,
                    "App not in Map list",
                    f"Could not find {desktop_id} in the Map application list.\n"
                    "It may be hidden or not loaded at startup.",
                )
                return

            self.app_list.setCurrentItem(found)
            self.app_list.setCurrentRow(self.app_list.row(found))
            self.app_list.scrollToItem(
                found, QListWidget.ScrollHint.PositionAtCenter
            )
            self.app_list.setFocus(Qt.FocusReason.OtherFocusReason)
            # Keep only this app (and name-collisions) visible so selection is obvious
            if hasattr(self, "app_search"):
                stem = desktop_id[:-8] if desktop_id.endswith(".desktop") else desktop_id
                self.app_search.setText(stem)
            self._update_mapping_summary()
            label = found.text() or desktop_id
            if self.statusBar():
                self.statusBar().showMessage(
                    f"Map step 2: selected {label} ({desktop_id}) — pick an icon in step 1, then Apply",
                    10000,
                )
            if hasattr(self, "plan_label") and self.plan_label is not None:
                self.plan_label.setText(
                    f"Application selected: <b>{label}</b> "
                    f"(<code>{desktop_id}</code>). Choose an icon in step 1, then Apply."
                )

        # After tab switch / layout so highlight + scroll actually take effect
        QTimer.singleShot(0, _select)

    # ── Settings callbacks ───────────────────────────────────────────────
    def _on_theme(self, theme):
        self.settings.setValue("appearance/theme", theme)
        apply_appearance_mode(theme)
        # Repolish so palette()-based styles (hint text, etc.) pick up new colors
        app = QApplication.instance()
        if app:
            for w in app.allWidgets():
                w.style().unpolish(w)
                w.style().polish(w)
                w.update()

    def _on_icon_shape(self, shape):
        self.settings.setValue("icons/shape", shape)
        if self.statusBar():
            labels = {
                "as-is": "As designed — keep original shape",
                "square": "Square — no rounded mask",
                "rounded": "Rounded corners",
                "circle": "Circle",
            }
            self.statusBar().showMessage(
                f"Applied icon shape: {labels.get(shape, shape)}",
                4000,
            )

    def _browse_source(self):
        d = QFileDialog.getExistingDirectory(self, "Select Source Folder", self.source_input.text())
        if d:
            self.source_input.setText(d)
            self.settings.setValue("source/folder", d)
            self._rescan_source()

    def _on_source_change(self):
        path = self.source_input.text()
        self.settings.setValue("source/folder", path)
        self._rescan_source()

    def _icon_start_dir(self):
        if hasattr(self, "source_input"):
            folder = self.source_input.text().strip()
            if folder and os.path.isdir(folder):
                return folder
        folder = self.settings.value(
            "source/folder",
            DOWNLOADS_DIR_DEFAULT,
            type=str,
        )
        if folder and os.path.isdir(folder):
            return folder
        return os.path.expanduser("~")

    def _set_icon_source(self, source):
        """Switch between files / app icons / installed icon theme packs."""
        self.icon_source = source
        # Keep combo in sync without re-entrancy
        if hasattr(self, "src_combo"):
            idx = self.src_combo.findData(source)
            if idx >= 0 and self.src_combo.currentIndex() != idx:
                self.src_combo.blockSignals(True)
                self.src_combo.setCurrentIndex(idx)
                self.src_combo.blockSignals(False)

        if hasattr(self, "theme_row_w"):
            self.theme_row_w.setVisible(source == "icontheme")

        if source == "system":
            self.file_search.setPlaceholderText("Filter by application name…")
            self.file_search.clear()
            self._fill_system_list()
            self._clear_empty_icon_state()
            if self.file_list.count() > 0:
                self.file_list.setCurrentRow(0)
            else:
                self.preview_label.setText("No system icons")
                self.info_label.setText("No theme icons found from installed apps.")
                self.meta_label.setText("")
            self._update_mapping_summary()
            if self.statusBar() and self.main_tabs.currentIndex() == 0:
                self.statusBar().showMessage(
                    "Showing icons already used by installed applications.",
                    5000,
                )
        elif source == "icontheme":
            self.file_search.setPlaceholderText("Filter theme icons (e.g. firefox)…")
            self.file_search.clear()
            self._fill_icon_theme_list()
            self._clear_empty_icon_state()
            if self.file_list.count() > 0:
                self.file_list.setCurrentRow(0)
            else:
                self.preview_label.setText("No icons in theme")
                self.info_label.setText("This theme set has no app icons, or none were found.")
                self.meta_label.setText("")
            self._update_mapping_summary()
            if self.statusBar() and self.main_tabs.currentIndex() == 0:
                tname = self.theme_combo.currentText() if hasattr(self, "theme_combo") else "theme"
                self.statusBar().showMessage(
                    f"Browsing icons from theme set: {tname}",
                    5000,
                )
        else:
            self.file_search.setPlaceholderText("Filter icons…")
            self.file_search.clear()
            self._fill_file_list(self.icon_files)
            if self.icon_files:
                self._clear_empty_icon_state()
                self.file_list.setCurrentRow(0)
            else:
                self._show_empty_icon_state()
            self._update_mapping_summary()
            if self.statusBar() and self.main_tabs.currentIndex() == 0:
                self.statusBar().showMessage(
                    "Showing icon files from your source folder and library.",
                    5000,
                )

    def _on_theme_pack_changed(self, _idx=None):
        if self.icon_source != "icontheme":
            return
        path = self.theme_combo.currentData() if hasattr(self, "theme_combo") else None
        if path:
            self.settings.setValue("map/icon_theme_path", path)
        self.file_search.clear()
        self._fill_icon_theme_list()
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
            self._clear_empty_icon_state()
        else:
            self.preview_label.setText("No icons in theme")
            self.info_label.setText("This theme set has no app icons, or none were found.")
            self.meta_label.setText("")
        self._update_mapping_summary()

    def _fill_file_list(self, files):
        """Populate the icon list, or a single clickable browse row when empty."""
        self.file_list.clear()
        if not files:
            item = QListWidgetItem("No icons found — click to browse…")
            item.setData(Qt.ItemDataRole.UserRole, BROWSE_FOR_ICON)
            folder_icon = QIcon.fromTheme("folder-open")
            if folder_icon.isNull():
                folder_icon = QIcon.fromTheme("document-open")
            if not folder_icon.isNull():
                item.setIcon(folder_icon)
            item.setToolTip("Open a file browser to choose an .icns or .png icon")
            self.file_list.addItem(item)
            return
        for fp in files:
            item = QListWidgetItem(os.path.basename(fp))
            item.setData(Qt.ItemDataRole.UserRole, fp)
            ext = os.path.splitext(fp)[1].lower()
            sz = getattr(self, "_map_icon_size", 32)
            if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg", ".svgz"):
                pix = QPixmap(fp)
                if not pix.isNull():
                    item.setIcon(QIcon(pix.scaled(
                        sz, sz,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )))
            else:
                ti = QIcon.fromTheme("image-x-generic")
                if not ti.isNull():
                    item.setIcon(QIcon(ti.pixmap(sz, sz)))
            self.file_list.addItem(item)

    def _fill_system_list(self):
        """List theme icons already used by installed applications."""
        self.file_list.clear()
        for icon_name, desktops in self.system_icons:
            if not desktops:
                continue
            primary = pick_primary_provider(desktops)
            if not primary:
                continue
            provider_label = self.desktop_labels.get(
                primary, os.path.splitext(primary)[0]
            )
            # Clear: this is the *source* of the icon, not the target app
            label = f"{provider_label}'s icon"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, THEME_ICON_PREFIX + icon_name)
            item.setData(Qt.ItemDataRole.UserRole + 1, provider_label)
            item.setData(Qt.ItemDataRole.UserRole + 2, icon_name)
            other = [self.desktop_labels.get(d, d) for d in desktops if d != primary]
            tip = (
                f"Use the same icon as: {provider_label}\n"
                f"Theme name: {icon_name}\n"
                f"Desktop: {primary}"
            )
            if other:
                tip += "\nAlso used by: " + ", ".join(other[:8])
                if len(other) > 8:
                    tip += f" (+{len(other) - 8} more)"
            item.setToolTip(tip)
            theme_icon = QIcon.fromTheme(icon_name)
            if not theme_icon.isNull():
                item.setIcon(theme_icon)
            else:
                fallback = QIcon.fromTheme("image-x-generic")
                if not fallback.isNull():
                    item.setIcon(fallback)
            self.file_list.addItem(item)

        # Sort by friendly provider name for scannability
        self.file_list.sortItems()

    def _fill_icon_theme_list(self):
        """List app icons from the selected installed icon theme pack."""
        self.file_list.clear()
        theme_path = self.theme_combo.currentData() if hasattr(self, "theme_combo") else None
        if not theme_path or not os.path.isdir(theme_path):
            item = QListWidgetItem("No icon themes found")
            item.setData(Qt.ItemDataRole.UserRole, BROWSE_FOR_ICON)
            self.file_list.addItem(item)
            return

        # Re-scan if uncached, mtime changed, or previous scan found nothing
        try:
            theme_mtime = os.path.getmtime(theme_path)
        except OSError:
            theme_mtime = None
        cached = self._theme_icons_cache.get(theme_path)
        need_scan = (
            cached is None
            or not cached[1]
            or (theme_mtime is not None and cached[0] is not None and theme_mtime != cached[0])
        )
        if need_scan:
            if self.statusBar():
                self.statusBar().showMessage("Scanning theme icons…")
            QApplication.processEvents()
            from kappicon.timing import span as _timing_span

            short = os.path.basename(theme_path.rstrip(os.sep)) or theme_path
            with _timing_span(f"scan_theme_icons:{short}"):
                icons_list = scan_theme_icons(theme_path)
            self._theme_icons_cache[theme_path] = (theme_mtime, icons_list)
            if self.statusBar():
                n = len(icons_list)
                self.statusBar().showMessage(f"Found {n} icons in theme.", 4000)

        icons = self._theme_icons_cache[theme_path][1]
        theme_label = self.theme_combo.currentText()
        # List icons without embedding thousands of pixmaps (keeps UI snappy);
        # the right-hand preview still loads the selected file.
        show_list_icons = len(icons) <= 400
        for name, path in icons:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)  # absolute file → applied as custom PNG path
            item.setData(Qt.ItemDataRole.UserRole + 1, theme_label)
            item.setData(Qt.ItemDataRole.UserRole + 2, name)
            item.setToolTip(
                f"Icon: {name}\n"
                f"Theme set: {theme_label}\n"
                f"File: {path}\n\n"
                "Applied as this file (independent of the active Plasma icon theme)."
            )
            if show_list_icons:
                ic = QIcon(path)
                if not ic.isNull():
                    item.setIcon(ic)
            self.file_list.addItem(item)

        if not icons:
            item = QListWidgetItem("No app icons in this theme")
            item.setData(Qt.ItemDataRole.UserRole, BROWSE_FOR_ICON)
            self.file_list.addItem(item)

    def _show_empty_icon_state(self):
        self.preview_label.clear()
        self.preview_label.setText("No icon files\nClick to browse")
        self.preview_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.preview_label.setToolTip("Click to browse for an icon file")
        self.info_label.setText("No custom icon selected")
        self.info_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.info_label.setToolTip("Click to browse for an icon file")
        self.meta_label.setText(
            "Or switch to “From another app” / “From icon theme” above"
        )
        self._update_mapping_summary()

    def _clear_empty_icon_state(self):
        self.preview_label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.preview_label.setToolTip("")
        self.info_label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.info_label.setToolTip("")

    def _on_empty_icon_click(self, event):
        # Only treat as browse when we're in the files empty state
        if self.icon_source != "files":
            return
        cur = self.file_list.currentItem()
        data = cur.data(Qt.ItemDataRole.UserRole) if cur else BROWSE_FOR_ICON
        if data == BROWSE_FOR_ICON or not self.icon_files:
            self._browse_for_icon_file()

    def _on_file_item_clicked(self, item):
        if item and item.data(Qt.ItemDataRole.UserRole) == BROWSE_FOR_ICON:
            self._browse_for_icon_file()

    def _browse_for_icon_file(self):
        """Open a file browser for any supported icon/image format.

        Prefers kdialog on KDE (native open dialog — same stack as Dolphin),
        then Qt's dialog. The selected file is added to the list so it can be
        mapped immediately, even if it lives outside the source folder.
        """
        start = self._icon_start_dir()
        path = None
        # Keep kdialog filter in sync with ICON_EXTENSIONS / Qt dialog
        kdialog_filter = (
            "*.png *.jpg *.jpeg *.webp *.svg *.svgz *.icns *.bmp *.gif *.xpm "
            "*.PNG *.JPG *.JPEG *.WEBP *.SVG *.ICNS|Icons and images\n*|All files"
        )

        if shutil.which("kdialog"):
            try:
                proc = subprocess.run(
                    [
                        "kdialog",
                        "--title", "Select icon file",
                        "--getopenfilename", start,
                        kdialog_filter,
                    ],
                    capture_output=True, text=True, timeout=600,
                )
                if proc.returncode == 0:
                    candidate = proc.stdout.strip()
                    if candidate and os.path.isfile(candidate):
                        path = candidate
            except Exception:
                path = None
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "Select icon file",
                start,
                "Icons and images (*.png *.jpg *.jpeg *.webp *.svg *.svgz *.icns "
                "*.bmp *.gif *.xpm *.PNG *.JPG *.JPEG *.WEBP *.SVG *.ICNS);;"
                "All files (*)",
            )
            if chosen and os.path.isfile(chosen):
                path = chosen

        if path:
            self._add_icon_file(path)

    def _add_icon_file(self, path):
        path = os.path.abspath(path)
        ext = os.path.splitext(path)[1].lower()
        if ext not in ICON_EXTENSIONS:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Unsupported file",
                "Please choose a supported icon/image file.\n"
                "PNG, JPG, WEBP, SVG, ICNS, BMP, GIF, XPM.\n\n"
                f"Got: {ext or '(no extension)'}",
            )
            return

        if path not in self.icon_files:
            self.icon_files.append(path)
            # Prefer showing the file's directory as source when list was empty
            parent = os.path.dirname(path)
            if hasattr(self, "source_input") and parent and os.path.isdir(parent):
                # Don't overwrite a populated source folder unless it was empty of icons
                if self.file_list.count() == 0 or (
                    self.file_list.count() == 1
                    and self.file_list.item(0).data(Qt.ItemDataRole.UserRole) == BROWSE_FOR_ICON
                ):
                    self.source_input.setText(parent)
                    self.settings.setValue("source/folder", parent)

        self._fill_file_list(self.icon_files)
        self._clear_empty_icon_state()
        # Select the newly added file
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self.file_list.setCurrentItem(item)
                break
        self._update_mapping_summary()

    def _rescan_source(self):
        folder = self.source_input.text()
        new_files = []
        if os.path.isdir(folder):
            try:
                names = os.listdir(folder)
            except OSError:
                names = []
            for f in sorted(names):
                path = os.path.join(folder, f)
                if os.path.isfile(path) and os.path.splitext(f)[1].lower() in ICON_EXTENSIONS:
                    new_files.append(path)
        # Keep any icons the user browsed to that live outside the source folder
        for fp in self.icon_files:
            if fp not in new_files and os.path.isfile(fp):
                if os.path.dirname(fp) != os.path.abspath(folder):
                    new_files.append(fp)
        self.icon_files = new_files
        self._fill_file_list(self.icon_files)
        if self.icon_files:
            self._clear_empty_icon_state()
            self.file_list.setCurrentRow(0)
            self.preview_label.setText("Select an icon")
            self.info_label.setText("")
            self.meta_label.setText("")
        else:
            self._show_empty_icon_state()

    def _restore_backup(self):
        backup_dir = BACKUP_DIR
        if not os.path.isdir(backup_dir):
            self._restore_status.setText("No backups found")
            QTimer.singleShot(2000, lambda: self._restore_status.setText(""))
            return
        try:
            names = os.listdir(backup_dir)
        except OSError:
            names = []
        backups = sorted(
            [
                f for f in names
                if ".backup." in f
                and os.path.sep not in f
                and ".." not in f
            ],
            key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
            reverse=True,
        )
        if not backups:
            self._restore_status.setText("No backups found")
            QTimer.singleShot(2000, lambda: self._restore_status.setText(""))
            return
        from PyQt6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(
            self, "Restore Backup", "Select backup to restore:", backups, 0, False
        )
        if not (ok and choice):
            return
        # Choice is a basename only — never trust path components
        if os.path.sep in choice or ".." in choice or choice in (".", ".."):
            self._restore_status.setText("Invalid backup name")
            QTimer.singleShot(3000, lambda: self._restore_status.setText(""))
            return
        src = os.path.join(backup_dir, choice)
        desktop_name = parse_backup_desktop_id(choice)
        if not desktop_name:
            self._restore_status.setText("Invalid desktop id in backup name")
            QTimer.singleShot(3000, lambda: self._restore_status.setText(""))
            return
        dest_dir = USER_APPS_DIR
        dest = os.path.join(dest_dir, desktop_name)
        try:
            if not os.path.isfile(src) or not path_is_under(src, backup_dir):
                raise OSError("backup path escaped backup directory")
            if self._apply_busy:
                raise ApplyError("Another icon operation is in progress.")
            display = self.desktop_labels.get(desktop_name, desktop_name)
            self._set_apply_busy(True)
            try:
                with apply_lock():
                    # Snapshot under the lock so Undo matches the pre-replace state
                    prev = snapshot_user_desktop(desktop_name)
                    os.makedirs(dest_dir, exist_ok=True)
                    # Atomic restore: copy to temp sibling then replace
                    fd, tmp = tempfile.mkstemp(prefix=".kappicon-restore-", dir=dest_dir)
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
                self._push_undo(desktop_name, display, prev)
                icon_now = read_desktop_icon_value(dest) or ""
                self._update_app_list_icon(desktop_name, icon_now)
                schedule_icon_cache_refresh(self)
                if hasattr(self, "_refresh_overrides_list"):
                    QTimer.singleShot(0, self._refresh_overrides_list)
            finally:
                self._set_apply_busy(False)
            self._restore_status.setText("Restored!")
            QTimer.singleShot(2000, lambda: self._restore_status.setText(""))
            if self.statusBar():
                self.statusBar().showMessage(
                    f"Restored {desktop_name} from backup (Undo reverses this)",
                    6000,
                )
        except ApplyError as e:
            self._set_apply_busy(False)
            self._restore_status.setText(f"Failed: {e}")
            QTimer.singleShot(3000, lambda: self._restore_status.setText(""))
        except Exception as e:
            self._set_apply_busy(False)
            self._restore_status.setText(f"Failed: {e}")
            QTimer.singleShot(3000, lambda: self._restore_status.setText(""))

    def _force_refresh(self):
        cmds = [
            ["kbuildsycoca6"],
            ["kbuildsycoca5"],
        ]
        for cmd in cmds:
            try:
                _run_host(cmd, capture_output=True, timeout=10)
                break
            except Exception:
                continue
        icon_roots = [USER_ICONS_DIR, os.path.expanduser("~/.icons")]
        hicolor = os.path.join(USER_ICONS_DIR, "hicolor")
        if hicolor not in icon_roots:
            icon_roots.append(hicolor)
        for ep in icon_roots:
            if os.path.isdir(ep):
                try:
                    _run_host(
                        ["gtk-update-icon-cache", "-f", "-t", ep],
                        capture_output=True, timeout=10,
                    )
                except Exception:
                    pass
        try:
            _run_host(
                ["update-desktop-database", USER_APPS_DIR],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass
        self._refresh_status.setText("Refreshed!")
        QTimer.singleShot(2000, lambda: self._refresh_status.setText(""))

    # ── Map tab callbacks ────────────────────────────────────────────────
    def _on_file_select(self, current, previous):
        if not current:
            self._update_mapping_summary()
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data or data == BROWSE_FOR_ICON:
            self._update_mapping_summary()
            return

        if self._preview_tmpdir:
            shutil.rmtree(self._preview_tmpdir, ignore_errors=True)
            self._preview_tmpdir = None

        # System / freedesktop theme icon
        if isinstance(data, str) and data.startswith(THEME_ICON_PREFIX):
            name = data[len(THEME_ICON_PREFIX):]
            provider = current.data(Qt.ItemDataRole.UserRole + 1) or name
            self._clear_empty_icon_state()
            self.info_label.setText(f"{provider}'s icon")
            self.meta_label.setText(
                f"Copying the icon that “{provider}” uses\n"
                f"(theme name: {name})"
            )
            theme_icon = QIcon.fromTheme(name)
            if not theme_icon.isNull():
                pix = theme_icon.pixmap(160, 160)
                if not pix.isNull():
                    self.preview_label.setPixmap(pix)
                    self._update_mapping_summary()
                    return
            self.preview_label.setText("No preview")
            self._update_mapping_summary()
            return

        # Custom file on disk (also: icons picked from an icon theme pack)
        fp = data
        if not os.path.isfile(fp):
            self._update_mapping_summary()
            return
        self._clear_empty_icon_state()
        icon_name = current.data(Qt.ItemDataRole.UserRole + 2)
        theme_label = current.data(Qt.ItemDataRole.UserRole + 1)
        if icon_name and self.icon_source == "icontheme":
            self.info_label.setText(str(icon_name))
            self.meta_label.setText(f"From icon theme · {theme_label}")
        else:
            self.info_label.setText(os.path.basename(fp))
            size = os.path.getsize(fp)
            size_s = f"{size / 1024:.0f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"
            self.meta_label.setText(f"Custom icon file · {size_s}")
        preview = extract_preview(fp)
        pix = QPixmap()
        if preview:
            pix = QPixmap(preview)
            if pix.isNull():
                # SVG / theme assets often resolve better via QIcon
                pix = QIcon(preview).pixmap(128, 128)
        if not pix.isNull():
            scaled = pix.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
            self._preview_tmpdir = os.path.dirname(preview) if preview else None
            if self._preview_tmpdir == os.path.dirname(fp):
                self._preview_tmpdir = None
        else:
            self.preview_label.setText("No preview")
        self._update_mapping_summary()

    def _update_mapping_summary(self):
        """Keep the right-hand “icon → app” story in sync with both lists."""
        if self._apply_busy:
            return
        selected_apps = self._selected_map_apps() if hasattr(self, "app_list") else []
        ai = None
        if selected_apps:
            ai = selected_apps[0]
        elif hasattr(self, "app_list"):
            ai = self.app_list.currentItem()
            if ai and ai.isHidden():
                ai = None
        fi = self.file_list.currentItem() if hasattr(self, "file_list") else None
        n_apps = len(selected_apps) if selected_apps else (1 if ai else 0)

        # Target app card
        if n_apps > 1:
            self.target_name_label.setText(f"{n_apps} applications selected")
            self.target_meta_label.setText(
                "Ctrl/Shift-click to change the selection. Apply updates all of them."
            )
            self.target_icon_label.clear()
            self.target_icon_label.setText(str(n_apps))
        elif ai:
            desktop = ai.data(Qt.ItemDataRole.UserRole)
            display = ai.data(Qt.ItemDataRole.UserRole + 1) or ai.text()
            cur_icon = ai.data(Qt.ItemDataRole.UserRole + 2)
            self.target_name_label.setText(display)
            self.target_meta_label.setText(f"Desktop file: {desktop}")
            pix = resolve_icon(cur_icon, size=48)
            if pix:
                self.target_icon_label.setPixmap(
                    pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                )
            else:
                self.target_icon_label.setText("?")
                self.target_icon_label.setPixmap(QPixmap())
        else:
            self.target_name_label.setText("Pick an app on the left")
            self.target_meta_label.setText("This is the program whose icon will change.")
            self.target_icon_label.clear()
            self.target_icon_label.setText("")

        # Plan sentence + apply button
        icon_ok = False
        icon_desc = None
        if fi:
            data = fi.data(Qt.ItemDataRole.UserRole)
            if data and data != BROWSE_FOR_ICON:
                icon_ok = True
                if isinstance(data, str) and data.startswith(THEME_ICON_PREFIX):
                    provider = fi.data(Qt.ItemDataRole.UserRole + 1) or data
                    icon_desc = f"{provider}'s icon"
                else:
                    icon_desc = os.path.basename(str(data))

        # Short caption; details in plan + tooltip (HIG)
        if n_apps > 1:
            self.select_btn.setText(f"Apply to {n_apps} apps")
        else:
            self.select_btn.setText("Apply")
        if icon_ok and n_apps:
            if n_apps > 1:
                self.plan_label.setText(
                    f"Will set {n_apps} launcher icons to {icon_desc}."
                )
                self.select_btn.setToolTip(f"Apply {icon_desc} to {n_apps} apps")
            else:
                display = ai.data(Qt.ItemDataRole.UserRole + 1) or ai.text()
                self.plan_label.setText(
                    f"Will set {display}'s launcher icon to {icon_desc}."
                )
                self.select_btn.setToolTip(f"Apply to {display} (window stays open)")
            self.select_btn.setEnabled(True)
            self.select_btn.setDefault(True)
        elif icon_ok:
            self.plan_label.setText("Now select the application to change (step 2).")
            self.select_btn.setEnabled(False)
            self.select_btn.setToolTip("Select an application first")
        elif n_apps:
            self.plan_label.setText("Now select the icon to use (step 1).")
            self.select_btn.setEnabled(False)
            self.select_btn.setToolTip("Select an icon first")
        else:
            self.plan_label.setText("Select an icon (step 1) and an application (step 2).")
            self.select_btn.setEnabled(False)
            self.select_btn.setToolTip("Select an icon and an application")
        # Reset only when at least one selected app has a system .desktop to restore
        can_reset = False
        if n_apps and not self._apply_busy:
            for it in (selected_apps if selected_apps else ([ai] if ai else [])):
                desk = it.data(Qt.ItemDataRole.UserRole) if it else None
                if desk and find_system_desktop_path(desk):
                    can_reset = True
                    break
        self.reset_btn.setEnabled(can_reset)
        if n_apps and not can_reset and not self._apply_busy:
            self.reset_btn.setToolTip(
                "No system .desktop for the selected app(s) — cannot reset a user-only launcher"
            )
        elif can_reset:
            self.reset_btn.setToolTip(
                "Restore the package/system icon when a system .desktop exists "
                "(same as Overrides → Reset to system icon)"
            )

    def _filter_files(self, text):
        q = text.lower()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) or ""
            hay = item.text().lower()
            if isinstance(data, str):
                hay += " " + data.lower()
                tip = item.toolTip() or ""
                hay += " " + tip.lower()
            # include provider / theme name roles
            for role in (Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 2):
                extra = item.data(role)
                if extra:
                    hay += " " + str(extra).lower()
            item.setHidden(q not in hay if q else False)

    def _filter_apps(self, text):
        q = (text or "").lower()
        mode = getattr(self, "_app_filter_mode", "all")
        recents = set(self._load_recent_list("map/recent_apps"))
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            hay = item.text().lower()
            desktop = item.data(Qt.ItemDataRole.UserRole) or ""
            hay += " " + str(desktop).lower()
            tip = item.toolTip() or ""
            hay += " " + tip.lower()
            text_ok = (not q) or (q in hay)
            scope_ok = True
            if mode == "customized":
                user_path = os.path.join(USER_APPS_DIR, str(desktop))
                scope_ok = os.path.isfile(user_path)
            # Recents stay visible when searching empty + all (sorted by paint order later not needed)
            item.setHidden(not (text_ok and scope_ok))
            # Soft boost: prefix recent marker in tooltip only
            if desktop in recents and not (item.toolTip() or "").startswith("Recent:"):
                item.setToolTip(f"Recent · {item.toolTip() or desktop}")

    def _selected_map_apps(self):
        """Visible selected app items (batch-safe)."""
        if not hasattr(self, "app_list"):
            return []
        out = []
        for item in self.app_list.selectedItems():
            if item.isHidden():
                continue
            desktop = item.data(Qt.ItemDataRole.UserRole)
            if desktop and is_valid_desktop_id(desktop):
                out.append(item)
        return out

    def _current_icon_spec(self):
        """Return icon selection string (theme:… or path), or None / BROWSE_FOR_ICON."""
        fi = self.file_list.currentItem() if hasattr(self, "file_list") else None
        if not fi:
            return None
        data = fi.data(Qt.ItemDataRole.UserRole)
        if data == BROWSE_FOR_ICON or not data:
            return BROWSE_FOR_ICON
        if isinstance(data, str) and data.startswith(THEME_ICON_PREFIX):
            theme_name = data[len(THEME_ICON_PREFIX):]
            if not theme_name or any(c in theme_name for c in "/\\\n\r"):
                return None
            return data
        if isinstance(data, str) and os.path.isfile(data):
            return data
        return None

    def _shape_pref(self):
        return self.settings.value("icons/shape", "as-is", type=str) or "as-is"

    def _backup_pref(self):
        return bool(self.settings.value("backups/enabled", False, type=bool))

    def _set_apply_busy(self, busy):
        self._apply_busy = bool(busy)
        for name in ("select_btn", "reset_btn"):
            w = getattr(self, name, None)
            if w is not None and not busy:
                pass  # re-enabled via summary
            elif w is not None and busy:
                w.setEnabled(False)
        self._sync_undo_actions()
        if not busy:
            self._update_mapping_summary()

    def _push_undo(self, desktop_id, display, previous_bytes):
        self._undo_stack.append({
            "desktop_id": desktop_id,
            "display": display or desktop_id,
            "previous_bytes": previous_bytes,
        })
        if len(self._undo_stack) > APPLY_UNDO_MAX:
            self._undo_stack = self._undo_stack[-APPLY_UNDO_MAX:]
        self._sync_undo_actions()

    def _undo_last_apply(self):
        if self._apply_busy or not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        self._sync_undo_actions()
        desktop_id = entry["desktop_id"]
        display = entry.get("display") or desktop_id
        try:
            with apply_lock():
                restore_user_desktop_snapshot(desktop_id, entry.get("previous_bytes"))
                # Prune under the same lock (no concurrent apply can race the keep-set)
                try:
                    prune_unreferenced_kappicon_assets(
                        extra_keep=undo_keep_icon_names(self._undo_stack)
                    )
                except Exception:
                    pass
            schedule_icon_cache_refresh(self)
            # Refresh list icon from desktop
            icon_now = read_desktop_icon_value(
                find_any_desktop_path(desktop_id) or ""
            )
            self._update_app_list_icon(desktop_id, icon_now)
            if self.statusBar():
                self.statusBar().showMessage(
                    f"Undid icon change for {display}", 6000
                )
            if hasattr(self, "plan_label"):
                self.plan_label.setText(f"Undid last apply for <b>{display}</b>.")
            if hasattr(self, "_refresh_overrides_list"):
                self._refresh_overrides_list()
        except ApplyError as e:
            QMessageBox.warning(self, "Undo failed", str(e))
            # put back so user can retry
            self._undo_stack.append(entry)
            self._sync_undo_actions()
        except Exception as e:
            QMessageBox.warning(self, "Undo failed", str(e))
            self._undo_stack.append(entry)
            self._sync_undo_actions()

    def _update_app_list_icon(self, desktop_id, icon_name):
        if not hasattr(self, "app_list"):
            return
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == desktop_id:
                item.setData(Qt.ItemDataRole.UserRole + 2, icon_name or "")
                pix = resolve_icon(icon_name, size=self._map_icon_size) if icon_name else None
                if pix:
                    item.setIcon(QIcon(pix))
                else:
                    item.setIcon(theme_icon("image-missing", "dialog-warning"))
                break
        # Keep app_data in sync for Missing scan
        for idx, row in enumerate(self.app_data):
            if row[0] == desktop_id:
                self.app_data[idx] = (row[0], icon_name or "", row[2], row[3])
                break
        self.desktop_paths[desktop_id] = os.path.join(USER_APPS_DIR, desktop_id)

    def _remember_recent_icon(self, icon_spec):
        if not icon_spec or icon_spec == BROWSE_FOR_ICON:
            return
        key = "map/recent_icons"
        items = self._load_recent_list(key)
        s = str(icon_spec)
        items = [x for x in items if x != s]
        items.insert(0, s)
        self._save_recent_list(key, items[:RECENT_MAX])

    def _remember_recent_app(self, desktop_id):
        if not desktop_id:
            return
        key = "map/recent_apps"
        items = self._load_recent_list(key)
        items = [x for x in items if x != desktop_id]
        items.insert(0, desktop_id)
        self._save_recent_list(key, items[:RECENT_MAX])

    def _load_recent_list(self, key):
        raw = self.settings.value(key, [])
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = [raw] if raw else []
        if not isinstance(raw, (list, tuple)):
            return []
        return [str(x) for x in raw if x]

    def _save_recent_list(self, key, items):
        # QSettings list of strings is portable enough
        self.settings.setValue(key, list(items))

    def _apply_icon_specs(self, icon_spec, app_items, *, confirm_batch=True):
        """In-process apply to one or more apps. Window stays open."""
        if self._apply_busy:
            return
        if not icon_spec or icon_spec == BROWSE_FOR_ICON:
            if self.icon_source == "files":
                self._browse_for_icon_file()
            return
        if not app_items:
            return

        n = len(app_items)
        if n > 1 and confirm_batch:
            names = ", ".join(
                (it.data(Qt.ItemDataRole.UserRole + 1) or it.text())
                for it in app_items[:5]
            )
            extra = f" and {n - 5} more" if n > 5 else ""
            confirm = QMessageBox.question(
                self,
                "Apply to multiple apps?",
                f"Apply this icon to <b>{n}</b> applications?\n\n{names}{extra}\n\n"
                "You can undo each change from Edit → Undo last icon apply.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        shape = self._shape_pref()
        backup = self._backup_pref()
        self._set_apply_busy(True)
        ok = 0
        errors = []
        try:
            for item in app_items:
                desktop = item.data(Qt.ItemDataRole.UserRole)
                display = item.data(Qt.ItemDataRole.UserRole + 1) or item.text()
                try:
                    with apply_lock():
                        result = apply_icon_to_desktop(
                            desktop, icon_spec, shape=shape, backup=backup
                        )
                        # Undo snapshot before prune so keep-set includes it
                        if not result.get("noop"):
                            self._push_undo(
                                desktop, display, result.get("previous_bytes")
                            )
                        try:
                            prune_unreferenced_kappicon_assets(
                                extra_keep=undo_keep_icon_names(self._undo_stack)
                            )
                        except Exception:
                            pass
                    self._update_app_list_icon(desktop, result.get("icon_value") or "")
                    self._remember_recent_app(desktop)
                    ok += 1
                except ApplyError as e:
                    errors.append(f"{display}: {e}")
                except Exception as e:
                    errors.append(f"{display}: {e}")
            self._remember_recent_icon(icon_spec)
            schedule_icon_cache_refresh(self)
            if hasattr(self, "_refresh_overrides_list"):
                # Defer so we don't rebuild mid-lock UI thrash
                QTimer.singleShot(0, self._refresh_overrides_list)
            if hasattr(self, "_refresh_missing_list"):
                QTimer.singleShot(0, self._refresh_missing_list)
        finally:
            self._set_apply_busy(False)

        if ok and self.statusBar():
            if n == 1:
                disp = app_items[0].data(Qt.ItemDataRole.UserRole + 1) or app_items[0].text()
                self.statusBar().showMessage(
                    f"Applied icon to {disp} — window stays open for more changes",
                    8000,
                )
            else:
                self.statusBar().showMessage(
                    f"Applied icon to {ok}/{n} applications", 8000
                )
        if ok and hasattr(self, "plan_label"):
            if n == 1:
                disp = app_items[0].data(Qt.ItemDataRole.UserRole + 1) or app_items[0].text()
                self.plan_label.setText(
                    f"Applied to <b>{disp}</b>. Pick another app or icon, or Undo."
                )
            else:
                self.plan_label.setText(
                    f"Applied to <b>{ok}</b> app(s). Edit → Undo last icon apply reverts one at a time."
                )
        if errors:
            QMessageBox.warning(
                self,
                "Some applies failed",
                "\n".join(errors[:12]) + ("\n…" if len(errors) > 12 else ""),
            )

    def _accept(self):
        """Apply without closing (in-process). Supports multi-select batch."""
        if self._apply_busy:
            return
        icon_spec = self._current_icon_spec()
        if icon_spec == BROWSE_FOR_ICON:
            if self.icon_source == "files":
                self._browse_for_icon_file()
            return
        if not icon_spec:
            return
        apps = self._selected_map_apps()
        if not apps:
            # Fall back to current item if selection empty but current exists
            ai = self.app_list.currentItem() if hasattr(self, "app_list") else None
            if ai and not ai.isHidden():
                apps = [ai]
        if not apps:
            return
        self._apply_icon_specs(icon_spec, apps)

    def _reset_app_icon(self):
        if self._apply_busy:
            return
        apps = self._selected_map_apps()
        if not apps:
            ai = self.app_list.currentItem() if hasattr(self, "app_list") else None
            if ai and not ai.isHidden():
                apps = [ai]
        if not apps:
            return
        # Pre-filter: only apps with a system desktop (match Overrides UX)
        resettable = []
        skipped = []
        for it in apps:
            desk = it.data(Qt.ItemDataRole.UserRole)
            disp = it.data(Qt.ItemDataRole.UserRole + 1) or it.text()
            if desk and find_system_desktop_path(desk):
                resettable.append(it)
            else:
                skipped.append(disp)
        if not resettable:
            QMessageBox.information(
                self,
                "Cannot reset",
                "No system .desktop was found for the selected application(s).\n"
                "Reset cannot invent an original icon for a user-only launcher.\n"
                "Use a backup restore if you saved one, or assign an icon on Map.",
            )
            return
        if len(resettable) == 1:
            display = resettable[0].data(Qt.ItemDataRole.UserRole + 1) or resettable[0].text()
            msg = f"Reset “{display}” to the system icon?"
        else:
            msg = f"Reset {len(resettable)} application(s) to their system icons?"
        if skipped:
            msg += (
                f"\n\nSkipped (no system .desktop): {', '.join(skipped[:5])}"
                + ("…" if len(skipped) > 5 else "")
            )
        confirm = QMessageBox.question(
            self,
            "Reset to system icon?",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._apply_icon_specs("RESET", resettable, confirm_batch=False)

    def _restore_map_session(self):
        """Restore source, theme, filters, last selection (silent, post-build)."""
        src = self.settings.value("map/icon_source", "", type=str) or ""
        if src in ("files", "system", "icontheme") and hasattr(self, "src_combo"):
            idx = self.src_combo.findData(src)
            if idx >= 0:
                self.src_combo.blockSignals(True)
                self.src_combo.setCurrentIndex(idx)
                self.src_combo.blockSignals(False)
                self._set_icon_source(src)
        theme_path = self.settings.value("map/icon_theme_path", "", type=str) or ""
        if theme_path and hasattr(self, "theme_combo"):
            tidx = self.theme_combo.findData(theme_path)
            if tidx >= 0:
                self.theme_combo.setCurrentIndex(tidx)
        icon_f = self.settings.value("map/icon_filter", "", type=str) or ""
        app_f = self.settings.value("map/app_filter", "", type=str) or ""
        if hasattr(self, "file_search") and icon_f:
            self.file_search.blockSignals(True)
            self.file_search.setText(icon_f)
            self.file_search.blockSignals(False)
            self._filter_files(icon_f)
        if hasattr(self, "app_search") and app_f:
            self.app_search.blockSignals(True)
            self.app_search.setText(app_f)
            self.app_search.blockSignals(False)
        self._filter_apps(app_f if hasattr(self, "app_search") else "")
        last_app = self.settings.value("map/last_app", "", type=str) or ""
        if last_app and hasattr(self, "app_list"):
            for i in range(self.app_list.count()):
                item = self.app_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == last_app and not item.isHidden():
                    self.app_list.setCurrentItem(item)
                    self.app_list.scrollToItem(item)
                    break
        last_icon = self.settings.value("map/last_icon", "", type=str) or ""
        if last_icon and hasattr(self, "file_list"):
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == last_icon and not item.isHidden():
                    self.file_list.setCurrentItem(item)
                    self.file_list.scrollToItem(item)
                    break
        self._update_mapping_summary()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData() and event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and os.path.splitext(path)[1].lower() in ICON_EXTENSIONS | IMAGE_IMPORT_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Drop image → select on Map (or load into Create). Never auto-applies."""
        paths = []
        if event.mimeData() and event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and os.path.isfile(path):
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ICON_EXTENSIONS | IMAGE_IMPORT_EXTENSIONS:
                        paths.append(path)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        path = paths[0]
        # Create tab focused → canvas; else Map icon selection
        if hasattr(self, "main_tabs") and self.main_tabs.currentIndex() == 1:
            if hasattr(self, "pixel_canvas"):
                self.pixel_canvas.load_from_file(path, fit=True, size=STANDARD_ICON_SIZE)
                self.pixel_canvas.mark_clean()
                if hasattr(self, "editor_name") and not self.editor_name.text().strip():
                    self.editor_name.setText(os.path.splitext(os.path.basename(path))[0])
                if self.statusBar():
                    self.statusBar().showMessage(
                        f"Imported {os.path.basename(path)} into Create", 5000
                    )
            return
        self.main_tabs.setCurrentIndex(0)
        self._set_icon_source("files")
        self._add_icon_file(path)
        if self.statusBar():
            self.statusBar().showMessage(
                f"Selected {os.path.basename(path)} — choose an app, then Apply",
                6000,
            )

    def closeEvent(self, event):
        # Persist light session state
        try:
            self.settings.setValue("window/width", self.width())
            self.settings.setValue("window/height", self.height())
            if hasattr(self, "app_list") and self.app_list.currentItem():
                self.settings.setValue(
                    "map/last_app",
                    self.app_list.currentItem().data(Qt.ItemDataRole.UserRole) or "",
                )
            if hasattr(self, "file_list") and self.file_list.currentItem():
                data = self.file_list.currentItem().data(Qt.ItemDataRole.UserRole)
                if data and data != BROWSE_FOR_ICON:
                    self.settings.setValue("map/last_icon", data)
        except Exception:
            pass
        if self._preview_tmpdir:
            shutil.rmtree(self._preview_tmpdir, ignore_errors=True)
        super().closeEvent(event)





def run_app(argv=None) -> int:
    """Build QApplication and CombinedWindow; return exit code."""
    from kappicon.timing import span as _timing_span

    if argv is None:
        argv = sys.argv
    app = QApplication(list(argv))
    apply_breeze_style(app)
    # Apply saved scheme before the window is built (so first paint is correct)
    _settings_early = QSettings("KAppIcon", "KAppIcon")
    apply_appearance_mode(_settings_early.value("appearance/theme", "system", type=str))

    settings = QSettings("KAppIcon", "KAppIcon")
    source_folder = settings.value("source/folder", DOWNLOADS_DIR_DEFAULT, type=str)

    def scan_icons(folder):
        files = []
        if os.path.isdir(folder):
            try:
                names = os.listdir(folder)
            except OSError:
                return files
            for f in sorted(names):
                path = os.path.join(folder, f)
                if os.path.isfile(path) and os.path.splitext(f)[1].lower() in ICON_EXTENSIONS:
                    files.append(path)
        return files

    with _timing_span("startup.build_icon_files"):
        icon_files = scan_icons(source_folder)
        # Always include icons created in the KAppIcon library
        for p in scan_icons(LIBRARY_DIR):
            if p not in icon_files:
                icon_files.append(p)

    def desktop_path_priority(path):
        """Higher = preferred when the same .desktop id exists in multiple places.

        User overrides ($XDG_DATA_HOME/applications) must win over /usr/share so we
        don't list Ark twice (system + customized copy).
        """
        path = os.path.normpath(path).replace("\\", "/")
        home_apps = os.path.normpath(USER_APPS_DIR).replace("\\", "/")
        if path.startswith(home_apps + "/") or path == home_apps:
            return 100
        # Also prefer legacy ~/.local/share/applications if XDG_DATA_HOME differs
        legacy_apps = os.path.normpath(
            os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
        ).replace("\\", "/")
        if legacy_apps != home_apps and (
            path.startswith(legacy_apps + "/") or path == legacy_apps
        ):
            return 90
        if "/flatpak/" in path and "/exports/share/applications" in path:
            return 50
        if "/flatpak/" in path:
            return 40
        if path.startswith("/usr/local/"):
            return 20
        return 10


    # One entry per desktop file id — prefer the user override when present
    _by_desktop_id = {}
    for dp in DESKTOP_LIST_RAW:
        if not dp or not os.path.isfile(dp):
            continue
        bid = os.path.basename(dp)
        pr = desktop_path_priority(dp)
        prev = _by_desktop_id.get(bid)
        if prev is None or pr > prev[0]:
            _by_desktop_id[bid] = (pr, dp)

    app_data = []
    for bid, (_pr, dp) in _by_desktop_id.items():
        display_name, icon_name = parse_desktop_fields(dp)
        app_data.append((bid, icon_name, display_name, dp))
    # Stable sort by friendly name
    app_data.sort(key=lambda t: (t[2] or t[0]).lower())

    # Always open the window — even with zero custom files. System theme icons
    # are available via the System source toggle.
    win = CombinedWindow(icon_files, app_data)
    win.show()
    # If there are no custom files but system icons exist, land on System so the
    # window is immediately useful (e.g. Shelly → Discover's icon).
    if not icon_files and win.system_icons:
        win._set_icon_source("system")
    elif not icon_files:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            win,
            "No icons found",
            f"No .icns or .png files found in:\n\n{source_folder}\n\n"
            "Click the empty list to browse for a file, switch to System for "
            "theme icons already used by installed apps, or set a different "
            "folder under Settings → Source Folder.",
        )

    # Apply / reset run in-process while the window is open (no close-to-apply).
    # Optional legacy RESULT lines kept for rare external drivers; normally empty.
    app.exec()

    if win.selected_file and win.selected_app:
        print(win.selected_file)
        print(win.selected_app)
        print("BACKUP=1" if settings.value("backups/enabled", False, type=bool) else "BACKUP=0")
    return int(app.exec())