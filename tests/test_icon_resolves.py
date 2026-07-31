"""icon_resolves: paths, file: URIs, remote rejection, theme probe."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from urllib.request import pathname2url

from tests.support.fixtures import write_png
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg


class TestIconResolves(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_empty_and_remote(self) -> None:
        with temp_xdg():
            load_engine()
            from kappicon.discovery import icon_resolves

            self.assertFalse(icon_resolves(""))
            self.assertFalse(icon_resolves(None))  # type: ignore[arg-type]
            self.assertFalse(icon_resolves("https://example.com/x.png"))
            self.assertFalse(icon_resolves("http://example.com/x.png"))
            self.assertFalse(icon_resolves("data:image/png;base64,aaa"))

    def test_absolute_and_file_uri(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon.discovery import icon_resolves

            png = write_png(sb.target / "ok.png", size=16)
            self.assertTrue(icon_resolves(str(png.resolve())))
            self.assertFalse(icon_resolves(str(sb.target / "missing.png")))
            uri = "file://" + pathname2url(str(png.resolve()))
            self.assertTrue(icon_resolves(uri))
            bad_uri = "file://" + pathname2url(str(sb.target / "nope.png"))
            self.assertFalse(icon_resolves(bad_uri))

    def test_theme_name_probe(self) -> None:
        with temp_xdg() as sb:
            eng = load_engine()
            from kappicon.discovery import icon_resolves
            from kappicon.paths import USER_ICONS_DIR

            # Plant hicolor file for a made-up theme name
            dest = (
                Path(USER_ICONS_DIR)
                / "hicolor"
                / "48x48"
                / "apps"
                / "kappicon-test-theme-xyz.png"
            )
            write_png(dest, size=48)
            self.assertTrue(icon_resolves("kappicon-test-theme-xyz"))
            self.assertFalse(icon_resolves("definitely-no-such-icon-name-zzzz"))


if __name__ == "__main__":
    unittest.main()
