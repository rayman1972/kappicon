"""AppImage launcher discovery and create helpers."""
from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path

from tests.support.fixtures import write_desktop
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg


class TestAppImageLaunchers(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_exec_looks_like_appimage(self) -> None:
        with temp_xdg():
            load_engine()
            from kappicon.discovery import exec_looks_like_appimage, extract_exec_path

            self.assertTrue(exec_looks_like_appimage('"/home/u/App.AppImage"'))
            self.assertTrue(exec_looks_like_appimage("/home/u/foo.appimage %f"))
            self.assertFalse(exec_looks_like_appimage("firefox %u"))
            self.assertEqual(
                extract_exec_path('"/home/x/My App.AppImage" %f'),
                "/home/x/My App.AppImage",
            )

    def test_scan_finds_user_appimage_desktop(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon.discovery import scan_appimage_launchers
            from kappicon.paths import USER_APPS_DIR

            ai = sb.home / "Applications" / "Demo.AppImage"
            ai.parent.mkdir(parents=True, exist_ok=True)
            ai.write_bytes(b"#!/bin/sh\n")
            ai.chmod(ai.stat().st_mode | stat.S_IEXEC)
            write_desktop(
                Path(USER_APPS_DIR) / "demo-appimage.desktop",
                name="Demo AI",
                icon="application-x-executable",
                exec_cmd=f'"{ai}"',
            )
            rows = scan_appimage_launchers()
            ids = {r["desktop_id"] for r in rows}
            self.assertIn("demo-appimage.desktop", ids)
            row = next(r for r in rows if r["desktop_id"] == "demo-appimage.desktop")
            self.assertTrue(row["appimage_exists"])
            self.assertEqual(row["display"], "Demo AI")

    def test_create_appimage_launcher(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon.discovery import create_appimage_launcher, scan_appimage_launchers
            from kappicon.paths import USER_APPS_DIR
            from kappicon.desktop import read_desktop_icon_value

            ai = sb.home / "foo-bar.AppImage"
            ai.write_bytes(b"#!/bin/sh\n")
            ai.chmod(ai.stat().st_mode | stat.S_IEXEC)
            row = create_appimage_launcher(str(ai), display_name="Foo Bar")
            self.assertTrue(row["desktop_id"].endswith(".desktop"))
            dest = Path(USER_APPS_DIR) / row["desktop_id"]
            self.assertTrue(dest.is_file())
            text = dest.read_text(encoding="utf-8")
            self.assertIn("Type=Application", text)
            self.assertIn(str(ai.resolve()), text)
            self.assertEqual(read_desktop_icon_value(str(dest)), "application-x-executable")
            rows = scan_appimage_launchers()
            self.assertTrue(any(r["desktop_id"] == row["desktop_id"] for r in rows))


if __name__ == "__main__":
    unittest.main()
