"""Icon prepare / content-address naming (SAFE-05)."""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from tests.support.fixtures import write_png, write_svg
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg

DESKTOP_ID = "kappicon-test-proc.desktop"


class TestIconProcessing(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_kappicon_theme_name_stable_for_same_content(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            p = write_svg(sandbox.target / "same.svg", fill="#aabbcc")
            n1 = eng.kappicon_theme_name(DESKTOP_ID, str(p), shape="as-is")
            n2 = eng.kappicon_theme_name(DESKTOP_ID, str(p), shape="as-is")
            self.assertEqual(n1, n2)
            self.assertTrue(eng.is_kappicon_icon_name(n1))
            p.write_text(
                p.read_text(encoding="utf-8") + "<!-- changed -->\n",
                encoding="utf-8",
            )
            n3 = eng.kappicon_theme_name(DESKTOP_ID, str(p), shape="as-is")
            self.assertNotEqual(n1, n3)
            n_circle = eng.kappicon_theme_name(DESKTOP_ID, str(p), shape="circle")
            self.assertNotEqual(n3, n_circle)

    def test_kappicon_theme_name_rejects_invalid_id(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            p = write_svg(sandbox.target / "x.svg")
            with self.assertRaises(eng.ApplyError):
                eng.kappicon_theme_name("../bad.desktop", str(p))

    def test_prepare_theme_prefix_returns_plain_name(self) -> None:
        with temp_xdg():
            eng = load_engine()
            name = eng.prepare_icon_value(
                eng.THEME_ICON_PREFIX + "foo-bar", DESKTOP_ID
            )
            self.assertEqual(name, "foo-bar")
            with self.assertRaises(eng.ApplyError):
                eng.prepare_icon_value(
                    eng.THEME_ICON_PREFIX + "bad/name", DESKTOP_ID
                )
            with self.assertRaises(eng.ApplyError):
                eng.prepare_icon_value(
                    eng.THEME_ICON_PREFIX + "bad\nname", DESKTOP_ID
                )

    def test_prepare_svg_as_is_installs_hicolor(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            svg = write_svg(sandbox.target / "icon.svg")
            with eng.apply_lock(timeout=5):
                name = eng.prepare_icon_value(str(svg), DESKTOP_ID, shape="as-is")
            self.assertTrue(eng.is_kappicon_icon_name(name))
            dest = (
                Path(eng.USER_ICONS_DIR)
                / "hicolor"
                / "scalable"
                / "apps"
                / f"{name}.svg"
            )
            self.assertTrue(dest.is_file(), f"missing {dest}")

    @unittest.skipUnless(
        shutil.which("magick") or shutil.which("convert"),
        "ImageMagick required for non-SVG hicolor install",
    )
    def test_prepare_png_as_is_installs_hicolor(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            png = write_png(sandbox.target / "icon.png")
            with eng.apply_lock(timeout=5):
                name = eng.prepare_icon_value(str(png), DESKTOP_ID, shape="as-is")
            self.assertTrue(eng.is_kappicon_icon_name(name))
            dest = (
                Path(eng.USER_ICONS_DIR)
                / "hicolor"
                / "512x512"
                / "apps"
                / f"{name}.png"
            )
            self.assertTrue(dest.is_file(), f"missing {dest}")

    @unittest.skipUnless(
        shutil.which("magick") or shutil.which("convert"),
        "ImageMagick required for shape rendering",
    )
    def test_shape_circle_distinct_name(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            png = write_png(sandbox.target / "shape.png")
            with eng.apply_lock(timeout=5):
                n_as = eng.prepare_icon_value(str(png), DESKTOP_ID, shape="as-is")
                n_ci = eng.prepare_icon_value(str(png), DESKTOP_ID, shape="circle")
            self.assertNotEqual(n_as, n_ci)


if __name__ == "__main__":
    unittest.main()
