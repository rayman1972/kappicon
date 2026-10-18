"""Offscreen GUI smoke: build CombinedWindow, visit tabs, check Apply.

Requires PyQt6 + QT_QPA_PLATFORM=offscreen. Skips cleanly if PyQt6 is absent.
Theme Apply runs inside the XDG sandbox and disarms the icon-cache timer so
host cache tools are not executed.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Must be set before any Qt platform init.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_pkg = Path(__file__).resolve().parents[1] / "python"
if str(_pkg) not in sys.path:
    sys.path.insert(0, str(_pkg))

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QImage
    from PyQt6.QtWidgets import QApplication, QListWidget

    _HAS_PYQT6 = True
except ImportError:  # pragma: no cover
    _HAS_PYQT6 = False

from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg


def _disarm_icon_cache_refresh() -> None:
    """Stop the debounced cache timer so tests never run kbuildsycoca."""
    try:
        from kappicon import ui as ui_mod
    except ImportError:
        return
    timer = getattr(ui_mod, "_cache_refresh_timer", None)
    if timer is not None:
        timer.stop()
        ui_mod._cache_refresh_timer = None

EXPECTED_TABS = ("Map", "Create", "Settings", "Overrides", "Missing", "AppImage")


def _write_demo_desktop(path: Path, *, name: str = "Demo Smoke", icon: str = "demo") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={name}",
                f"Icon={icon}",
                "Exec=true",
                "Terminal=false",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_png(path: Path, color: QColor | None = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(32, 32, QImage.Format.Format_ARGB32)
    img.fill(color or QColor(220, 40, 40, 255))
    if not img.save(str(path), "PNG"):
        raise RuntimeError(f"failed to write PNG fixture: {path}")
    return str(path)


def _clear_list_selection(widget: QListWidget) -> None:
    widget.clearSelection()
    widget.setCurrentItem(None)


@unittest.skipUnless(_HAS_PYQT6, "PyQt6 not installed")
class TestGuiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication(["kappicon-gui-smoke"])

    def setUp(self) -> None:
        clear_engine_cache()

    def tearDown(self) -> None:
        clear_engine_cache()

    def _build_window(self, sandbox):
        """Load engine under sandbox env, then construct CombinedWindow with fixtures."""
        load_engine(force_reload=True)

        png = _write_png(sandbox.library / "smoke-icon.png")
        desk = sandbox.system_apps / "demo.desktop"
        _write_demo_desktop(desk)

        from kappicon.ui import CombinedWindow

        app_data = [
            ("demo.desktop", "demo", "Demo Smoke", str(desk)),
        ]
        win = CombinedWindow(icon_files=[png], app_data=app_data)
        self.app.processEvents()
        return win, png

    def _close_window(self, win) -> None:
        win.close()
        win.deleteLater()
        self.app.processEvents()

    def test_six_tabs_build_and_switch(self) -> None:
        with temp_xdg() as sandbox:
            win, _png = self._build_window(sandbox)
            try:
                self.assertEqual(win.main_tabs.count(), 6)
                for i, name in enumerate(EXPECTED_TABS):
                    self.assertEqual(
                        win.main_tabs.tabText(i),
                        name,
                        f"tab {i} label",
                    )

                for i in range(6):
                    win.main_tabs.setCurrentIndex(i)
                    self.app.processEvents()
                    self.assertEqual(win.main_tabs.currentIndex(), i)

                # Management tabs refresh on show; ensure lists exist after visit.
                self.assertTrue(hasattr(win, "app_list"))
                self.assertTrue(hasattr(win, "file_list"))
                self.assertTrue(hasattr(win, "select_btn"))
                self.assertTrue(hasattr(win, "reset_btn"))
            finally:
                self._close_window(win)

    def test_apply_button_states(self) -> None:
        with temp_xdg() as sandbox:
            win, png = self._build_window(sandbox)
            try:
                win.main_tabs.setCurrentIndex(0)
                self.app.processEvents()

                # Construction auto-selects first icon when present; no app yet.
                self.assertGreaterEqual(win.file_list.count(), 1)
                self.assertEqual(win.app_list.count(), 1)

                # --- neither: clear both selections ---
                _clear_list_selection(win.file_list)
                _clear_list_selection(win.app_list)
                win._update_mapping_summary()
                self.app.processEvents()
                self.assertFalse(
                    win.select_btn.isEnabled(),
                    "Apply should be disabled with no icon and no app",
                )
                self.assertFalse(
                    win.reset_btn.isEnabled(),
                    "Reset should be disabled with no app selected",
                )

                # --- icon only ---
                icon_item = None
                for i in range(win.file_list.count()):
                    it = win.file_list.item(i)
                    data = it.data(Qt.ItemDataRole.UserRole)
                    if data and data != "__browse_for_icon__" and str(data) == png:
                        icon_item = it
                        break
                if icon_item is None:
                    # basename match fallback
                    for i in range(win.file_list.count()):
                        it = win.file_list.item(i)
                        data = it.data(Qt.ItemDataRole.UserRole)
                        if data and data != "__browse_for_icon__":
                            icon_item = it
                            break
                self.assertIsNotNone(icon_item, "expected a real icon row in file_list")
                win.file_list.setCurrentItem(icon_item)
                _clear_list_selection(win.app_list)
                win._update_mapping_summary()
                self.app.processEvents()
                self.assertFalse(
                    win.select_btn.isEnabled(),
                    "Apply should stay disabled with icon only",
                )

                # --- app only ---
                _clear_list_selection(win.file_list)
                app_item = win.app_list.item(0)
                win.app_list.setCurrentItem(app_item)
                app_item.setSelected(True)
                win._update_mapping_summary()
                self.app.processEvents()
                self.assertFalse(
                    win.select_btn.isEnabled(),
                    "Apply should stay disabled with app only",
                )
                # System desktop is under sandbox XDG_DATA_DIRS → Reset can enable.
                self.assertTrue(
                    win.reset_btn.isEnabled(),
                    "Reset should enable when selected app has a system .desktop",
                )

                # --- both: Apply enables ---
                win.file_list.setCurrentItem(icon_item)
                win.app_list.setCurrentItem(app_item)
                app_item.setSelected(True)
                win._update_mapping_summary()
                self.app.processEvents()
                self.assertTrue(
                    win.select_btn.isEnabled(),
                    "Apply should enable when both icon and app are selected",
                )
                self.assertEqual(win.select_btn.text(), "Apply")
            finally:
                self._close_window(win)

    def test_cache_refresh_timer_is_defined_while_qt_is_alive(self) -> None:
        """Apply schedules a refresh only when this module global exists."""
        with temp_xdg():
            load_engine(force_reload=True)
            from kappicon import ui as ui_mod

            ui_mod._cache_refresh_timer = None
            try:
                ui_mod.schedule_icon_cache_refresh()
                timer = ui_mod._cache_refresh_timer
                self.assertIsNotNone(timer)
                self.assertTrue(timer.isSingleShot())
                self.assertTrue(timer.isActive())
                # A second Apply in the same session reuses the timer.
                ui_mod.schedule_icon_cache_refresh()
                self.assertIs(ui_mod._cache_refresh_timer, timer)
                self.assertTrue(timer.isActive())
            finally:
                _disarm_icon_cache_refresh()

    def test_theme_apply_keeps_window_open(self) -> None:
        """Stay-open Apply: theme icon is written and the window survives."""
        with temp_xdg() as sandbox:
            win, _png = self._build_window(sandbox)
            try:
                from PyQt6.QtWidgets import QListWidgetItem

                from kappicon.paths import THEME_ICON_PREFIX

                win.show()
                self.app.processEvents()

                theme_item = QListWidgetItem("Terminal")
                theme_item.setData(
                    Qt.ItemDataRole.UserRole, THEME_ICON_PREFIX + "utilities-terminal"
                )
                theme_item.setData(Qt.ItemDataRole.UserRole + 1, "Breeze")
                win.file_list.addItem(theme_item)
                win.file_list.setCurrentItem(theme_item)

                app_item = win.app_list.item(0)
                win.app_list.setCurrentItem(app_item)
                app_item.setSelected(True)
                win._update_mapping_summary()
                self.app.processEvents()
                self.assertTrue(win.select_btn.isEnabled())

                win.select_btn.click()
                self.app.processEvents()

                self.assertTrue(win.isVisible())
                user_desktop = sandbox.user_apps / "demo.desktop"
                self.assertTrue(user_desktop.is_file(), "user override was not written")
                self.assertIn("Icon=utilities-terminal", user_desktop.read_text(encoding="utf-8"))
                message = win.statusBar().currentMessage()
                self.assertIn("stays open", message)

                # Second Apply in the same session must not raise.
                win.select_btn.click()
                self.app.processEvents()
                self.assertTrue(win.isVisible())
                self.assertFalse(win._apply_busy)
            finally:
                _disarm_icon_cache_refresh()
                self._close_window(win)


if __name__ == "__main__":
    unittest.main()
