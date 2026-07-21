"""Smoke tests: temp XDG isolation + package engine load (no GUI)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg


class TestHarnessSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self._real_home = Path(os.path.expanduser("~")).resolve()
        clear_engine_cache()

    def test_package_exports_mutation_api(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            self.assertTrue(callable(eng.apply_icon_to_desktop))
            self.assertTrue(callable(eng.is_valid_desktop_id))
            # Implementation lives in package, not a heredoc exec
            self.assertTrue(
                str(getattr(eng.apply_icon_to_desktop, "__module__", "")).startswith(
                    "kappicon"
                )
                or eng.apply_icon_to_desktop.__module__ == "kappicon.mutation"
                or "kappicon" in eng.apply_icon_to_desktop.__module__,
            )

    def test_engine_loads_under_temp_xdg(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            self.assertTrue(eng.is_valid_desktop_id("demo.desktop"))
            self.assertFalse(eng.is_valid_desktop_id("../evil.desktop"))
            lock = Path(eng.LOCK_FILE).resolve()
            self.assertTrue(
                str(lock).startswith(str(sandbox.data_dir.resolve())),
                f"LOCK_FILE {lock} not under {sandbox.data_dir}",
            )
            self.assertTrue(
                str(Path(eng.DATA_DIR).resolve()).startswith(
                    str(sandbox.root.resolve())
                )
            )

    def test_paths_not_real_home(self) -> None:
        real_local = (self._real_home / ".local").resolve()
        real_config = (self._real_home / ".config").resolve()
        with temp_xdg() as sandbox:
            eng = load_engine()
            for attr in ("DATA_DIR", "USER_APPS_DIR", "USER_ICONS_DIR", "BACKUP_DIR"):
                p = Path(getattr(eng, attr)).resolve()
                self.assertTrue(
                    str(p).startswith(str(sandbox.root.resolve())),
                    f"{attr}={p} not under sandbox",
                )
                self.assertFalse(
                    str(p).startswith(str(real_local) + os.sep)
                    or p == real_local
                    or str(p).startswith(str(real_config) + os.sep)
                    or p == real_config,
                    f"{attr}={p} escaped into real home XDG",
                )


if __name__ == "__main__":
    unittest.main()
