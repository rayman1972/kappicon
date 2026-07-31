"""Desktop path roots: Flatpak/DESKTOP_LIST consistency for Apply/Reset."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from tests.support.fixtures import write_desktop
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg


class TestDesktopPaths(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_find_via_desktop_list_parent_not_on_xdg_data_dirs(self) -> None:
        with temp_xdg() as sb:
            # Flatpak-like export dir outside XDG_DATA_DIRS
            export_apps = sb.root / "flatpak-exports" / "share" / "applications"
            export_apps.mkdir(parents=True)
            desk = write_desktop(
                export_apps / "org.example.flatpak.desktop",
                name="Flatpak App",
                icon="utilities-terminal",
            )
            # Only via DESKTOP_LIST (shell always injects these paths)
            os.environ["DESKTOP_LIST"] = str(desk)
            # Keep XDG_DATA_DIRS as sandbox system_share only (default)
            eng = load_engine(force_reload=True)
            found = eng.find_any_desktop_path("org.example.flatpak.desktop")
            self.assertIsNotNone(found)
            self.assertTrue(os.path.isfile(found))
            self.assertEqual(os.path.basename(found), "org.example.flatpak.desktop")
            # System path should also see it (same roots)
            sys_p = eng.find_system_desktop_path("org.example.flatpak.desktop")
            self.assertIsNotNone(sys_p)

    def test_user_override_preferred(self) -> None:
        with temp_xdg() as sb:
            eng = load_engine()
            from kappicon.paths import USER_APPS_DIR

            write_desktop(
                sb.system_apps / "both.desktop",
                name="System Both",
                icon="system-icon",
            )
            user = write_desktop(
                Path(USER_APPS_DIR) / "both.desktop",
                name="User Both",
                icon="user-icon",
            )
            any_p = eng.find_any_desktop_path("both.desktop")
            self.assertEqual(os.path.realpath(any_p), os.path.realpath(user))
            sys_p = eng.find_system_desktop_path("both.desktop")
            self.assertIsNotNone(sys_p)
            self.assertNotEqual(os.path.realpath(sys_p), os.path.realpath(user))

    def test_system_desktop_roots_exports_shared(self) -> None:
        with temp_xdg():
            eng = load_engine()
            roots = eng.system_desktop_roots()
            self.assertIsInstance(roots, list)
            # All unique
            self.assertEqual(len(roots), len(set(roots)))


if __name__ == "__main__":
    unittest.main()
