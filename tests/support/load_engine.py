"""
Load the mutation engine from gui/kappicon without starting the GUI.

| Use | Source slice | Operation |
|-----|--------------|-----------|
| Mutation tests (`load_engine`) | Full PYEOF **then truncated** | `exec` into a module namespace |
| SAFE-06 `scripts/validate.sh` only | Full PYEOF body (no truncate) | `compile(..., "exec")` only — **never** `exec` full body in tests |

Do **not** exec the untruncated heredoc: it ends with Scan+run (`QApplication`, `app.exec()`, `sys.exit`).
Always enter `temp_xdg()` **before** `load_engine()` so module-level `os.makedirs` stay under the sandbox.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from typing import Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
GUI_KAPPICON = REPO_ROOT / "gui" / "kappicon"

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


def extract_gui_python_source(path: Path = GUI_KAPPICON) -> str:
    """Return the full PYEOF heredoc body from gui/kappicon (shell lines excluded)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Match python3 - <<'PYEOF' ... PYEOF
    m = re.search(
        r"python3\s+-\s+<<'PYEOF'\n(.*)\nPYEOF\s*$",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    if not m:
        # Fallback: first PYEOF heredoc in file
        m = re.search(r"<<'PYEOF'\n(.*)\nPYEOF\b", text, flags=re.DOTALL)
    if not m:
        raise RuntimeError(f"Could not locate PYEOF Python body in {path}")
    return m.group(1)


def _first_line_index(lines: List[str], predicate) -> Optional[int]:
    for i, line in enumerate(lines):
        if predicate(line):
            return i
    return None


def mutation_source_for_exec(full_source: str) -> str:
    """
    Truncate embedded GUI Python so mutation APIs load without Scan+run bootstrap.

    Preferred cut: before Icon editor / PixelCanvas (drops UI classes).
    Hard cut (mandatory floor): before Scan+run / module-level QApplication.
    Never returns a slice containing app.exec() or sys.exit(0).
    """
    lines = full_source.splitlines(keepends=True)

    def is_icon_editor(line: str) -> bool:
        s = line.strip()
        return (
            "Icon editor (pixel canvas" in line
            or s.startswith("class PixelCanvas")
        )

    def is_scan_run(line: str) -> bool:
        s = line.strip()
        if "Scan + run" in line:
            return True
        # Module-level bootstrap only (not indented)
        if line[:1] not in (" ", "\t") and (
            s.startswith("app = QApplication(") or s.startswith("QApplication([])")
        ):
            return True
        return False

    preferred = _first_line_index(lines, is_icon_editor)
    hard = _first_line_index(lines, is_scan_run)
    if hard is None:
        raise RuntimeError(
            "mutation_source_for_exec: could not find Scan+run / QApplication bootstrap cut"
        )

    cut = preferred if preferred is not None and preferred < hard else hard
    # If preferred cut drops required symbols, fall back to hard cut only
    for attempt_cut in (cut, hard):
        body = "".join(lines[:attempt_cut])
        if "apply_icon_to_desktop" in body and "is_valid_desktop_id" in body:
            if "app.exec" in body or "sys.exit" in body or "Scan + run" in body:
                # Strip any accidental tail markers (should not happen)
                body_lines = body.splitlines(keepends=True)
                hi = _first_line_index(body_lines, is_scan_run)
                if hi is not None:
                    body = "".join(body_lines[:hi])
            if "app.exec" in body or "sys.exit(0)" in body:
                continue
            return body

    raise RuntimeError(
        "mutation_source_for_exec: truncated slice missing required symbols"
    )


def install_pyqt_stubs() -> None:
    """Install lightweight PyQt6 stubs so top-level imports succeed without real Qt."""

    def make_qt_module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        # Provide common names as dummy classes/functions
        for attr in (
            "QApplication",
            "QWidget",
            "QVBoxLayout",
            "QHBoxLayout",
            "QLineEdit",
            "QListWidget",
            "QListWidgetItem",
            "QPushButton",
            "QLabel",
            "QSplitter",
            "QFrame",
            "QTabWidget",
            "QCheckBox",
            "QComboBox",
            "QFileDialog",
            "QButtonGroup",
            "QColorDialog",
            "QMessageBox",
            "QToolButton",
            "QSizePolicy",
            "QMainWindow",
            "QGroupBox",
            "QFormLayout",
            "QDialogButtonBox",
            "QStatusBar",
            "QStyle",
            "QStyleFactory",
            "QRadioButton",
            "QDialog",
            "QSlider",
            "QAbstractItemView",
            "QMenu",
            "QAbstractSpinBox",
            "QTextEdit",
            "QPlainTextEdit",
            "QPixmap",
            "QIcon",
            "QColor",
            "QPainter",
            "QPainterPath",
            "QPalette",
            "QCursor",
            "QImage",
            "QPen",
            "QKeySequence",
            "QShortcut",
            "QAction",
            "QDragEnterEvent",
            "QDropEvent",
            "Qt",
            "QSize",
            "QSettings",
            "QTimer",
            "pyqtSignal",
            "QPointF",
            "QRectF",
            "QUrl",
        ):
            if attr == "pyqtSignal":
                def pyqtSignal(*_a, **_k):  # type: ignore
                    return lambda *a, **k: None

                setattr(mod, attr, pyqtSignal)
            elif attr == "Qt":
                qt = types.SimpleNamespace()
                # Nested enums used in UI code (not executed after cut, but import-safe)
                item = types.SimpleNamespace(UserRole=0)
                qt.ItemDataRole = item
                qt.AlignmentFlag = types.SimpleNamespace(
                    AlignCenter=0, AlignLeft=0, AlignRight=0
                )
                qt.GlobalColor = types.SimpleNamespace(transparent=0, white=0, black=0)
                qt.PenStyle = types.SimpleNamespace(NoPen=0, SolidLine=1)
                qt.MouseButton = types.SimpleNamespace(LeftButton=1, RightButton=2)
                qt.Key = types.SimpleNamespace()
                setattr(mod, attr, qt)
            else:
                setattr(mod, attr, type(attr, (), {}))
        return mod

    # Mutation tests always install stubs first (no real Qt / display).
    pyqt6 = types.ModuleType("PyQt6")
    sys.modules["PyQt6"] = pyqt6
    for short in ("QtWidgets", "QtGui", "QtCore"):
        full = f"PyQt6.{short}"
        m = make_qt_module(full)
        sys.modules[full] = m
        setattr(pyqt6, short, m)


def load_engine(*, force_reload: bool = False) -> types.ModuleType:
    """
    Exec the truncated mutation slice into a module namespace.

    Requires path/XDG env already set by temp_xdg (module-level makedirs run at load).
    """
    global _engine_cache, _engine_cache_key

    data_dir = os_environ_data_dir()
    cache_key = data_dir
    if not force_reload and _engine_cache is not None and _engine_cache_key == cache_key:
        return _engine_cache

    install_pyqt_stubs()
    full = extract_gui_python_source()
    src = mutation_source_for_exec(full)

    if "app.exec" in src or "sys.exit(0)" in src or "Scan + run" in src:
        raise RuntimeError("load_engine refused to exec bootstrap-containing source")

    mod = types.ModuleType("kappicon_engine")
    mod.__file__ = str(GUI_KAPPICON)
    # Provide __name__ for any code that checks it
    g = mod.__dict__
    exec(compile(src, str(GUI_KAPPICON) + ":mutation", "exec"), g, g)

    missing = [name for name in _REQUIRED_SYMBOLS if name not in g]
    if missing:
        raise RuntimeError(f"load_engine: missing symbols after exec: {missing}")

    _engine_cache = mod
    _engine_cache_key = cache_key
    return mod


def os_environ_data_dir() -> str:
    import os

    return os.environ.get("DATA_DIR") or ""


def clear_engine_cache() -> None:
    global _engine_cache, _engine_cache_key
    _engine_cache = None
    _engine_cache_key = None
