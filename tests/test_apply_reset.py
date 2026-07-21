"""Apply + reset semantics under temp XDG (SAFE-01, SAFE-02)."""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from tests.support.fixtures import install_system_app, install_user_override, write_svg
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg

DESKTOP_ID = "kappicon-test-demoapp.desktop"


class TestApplyReset(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_apply_file_icon_creates_user_override(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="Demo", icon="system-icon", exec_cmd="true"
            )
            sys_text = (sandbox.system_apps / DESKTOP_ID).read_text(encoding="utf-8")
            svg = write_svg(sandbox.target / "icon.svg")
            with eng.apply_lock(timeout=5):
                result = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(svg), shape="as-is", backup=False
                )
            self.assertFalse(result.get("reset"))
            self.assertFalse(result.get("noop"))
            self.assertTrue(result["icon_value"])
            self.assertTrue(eng.is_kappicon_icon_name(result["icon_value"]))
            user_path = Path(eng.USER_APPS_DIR) / DESKTOP_ID
            self.assertTrue(user_path.is_file())
            self.assertEqual(
                eng.read_desktop_icon_value(str(user_path)), result["icon_value"]
            )
            self.assertEqual(
                (sandbox.system_apps / DESKTOP_ID).read_text(encoding="utf-8"), sys_text
            )

    def test_apply_theme_icon_name_no_hicolor_file_required(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="Demo", icon="system-icon"
            )
            theme = eng.THEME_ICON_PREFIX + "utilities-terminal"
            with eng.apply_lock(timeout=5):
                result = eng.apply_icon_to_desktop(
                    DESKTOP_ID, theme, shape="as-is", backup=False
                )
            self.assertEqual(result["icon_value"], "utilities-terminal")
            self.assertFalse(eng.is_kappicon_icon_name(result["icon_value"]))
            user_path = Path(eng.USER_APPS_DIR) / DESKTOP_ID
            self.assertEqual(
                eng.read_desktop_icon_value(str(user_path)), "utilities-terminal"
            )

    def test_reset_removes_icon_only_override(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="Demo", icon="system-icon"
            )
            install_user_override(
                sandbox,
                DESKTOP_ID,
                name="Demo",
                icon="custom-name",
                exec_cmd="true",
            )
            with eng.apply_lock(timeout=5):
                result = eng.apply_icon_to_desktop(
                    DESKTOP_ID, "RESET", backup=False
                )
            self.assertTrue(result.get("reset"))
            self.assertTrue(result.get("removed_override"))
            self.assertFalse((Path(eng.USER_APPS_DIR) / DESKTOP_ID).is_file())
            self.assertTrue((sandbox.system_apps / DESKTOP_ID).is_file())
            self.assertEqual(
                eng.read_desktop_icon_value(str(sandbox.system_apps / DESKTOP_ID)),
                "system-icon",
            )

    def test_reset_preserves_desktop_actions(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="Demo", icon="system-icon"
            )
            install_user_override(
                sandbox,
                DESKTOP_ID,
                name="Demo",
                icon="kappicon-custom",
                exec_cmd="true",
                extra_desktop_entry_lines=["Comment=user edit"],
                actions=[("Foo", "Foo", "true")],
            )
            user_before = (Path(eng.USER_APPS_DIR) / DESKTOP_ID).read_text(
                encoding="utf-8"
            )
            self.assertIn("[Desktop Action Foo]", user_before)
            with eng.apply_lock(timeout=5):
                result = eng.apply_icon_to_desktop(
                    DESKTOP_ID, "RESET", backup=False
                )
            self.assertTrue(result.get("reset"))
            self.assertFalse(result.get("removed_override"))
            user_path = Path(eng.USER_APPS_DIR) / DESKTOP_ID
            self.assertTrue(user_path.is_file())
            text = user_path.read_text(encoding="utf-8")
            self.assertIn("[Desktop Action Foo]", text)
            self.assertIn("Comment=user edit", text)
            self.assertEqual(
                eng.read_desktop_icon_value(str(user_path)), "system-icon"
            )

    def test_reset_user_only_launcher_errors(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_user_override(
                sandbox, DESKTOP_ID, name="UserOnly", icon="somewhere"
            )
            with eng.apply_lock(timeout=5):
                with self.assertRaises(eng.ApplyError):
                    eng.apply_icon_to_desktop(DESKTOP_ID, "RESET", backup=False)

    def test_apply_rejects_invalid_desktop_id(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(sandbox, DESKTOP_ID, name="Demo")
            with eng.apply_lock(timeout=5):
                with self.assertRaises(eng.ApplyError):
                    eng.apply_icon_to_desktop(
                        "../escape.desktop",
                        eng.THEME_ICON_PREFIX + "x",
                        backup=False,
                    )
                with self.assertRaises(eng.ApplyError):
                    eng.apply_icon_to_desktop(
                        "foo", eng.THEME_ICON_PREFIX + "x", backup=False
                    )

    @unittest.skipUnless(
        shutil.which("magick") or shutil.which("convert"),
        "ImageMagick required for non-SVG hicolor install",
    )
    def test_apply_png_with_magick(self) -> None:
        from tests.support.fixtures import write_png

        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(sandbox, DESKTOP_ID, name="Demo", icon="system-icon")
            png = write_png(sandbox.target / "icon.png", size=32)
            with eng.apply_lock(timeout=5):
                result = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(png), shape="as-is", backup=False
                )
            self.assertTrue(eng.is_kappicon_icon_name(result["icon_value"]))


if __name__ == "__main__":
    unittest.main()
