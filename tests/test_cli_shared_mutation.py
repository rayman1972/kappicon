"""ARCH-02: CLI apply/restore go through python/kappicon (source contracts + offline smoke)."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from tests.support.fixtures import install_system_app, write_svg
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "cli" / "kappicon-cli"
GUI = REPO / "gui" / "kappicon"


class TestCliSharedMutation(unittest.TestCase):
    def test_cli_source_uses_package_apply_restore(self) -> None:
        text = CLI.read_text(encoding="utf-8", errors="replace")
        self.assertIn("apply_icon_to_desktop", text)
        self.assertIn("apply_lock", text)
        self.assertIn("parse_backup_desktop_id", text)
        self.assertIn("KAPPICON_PYTHON_PATH", text)
        self.assertIn("_kappicon_resolve_python_path", text)
        self.assertIn("kappicon_cli_apply", text)
        self.assertIn("kappicon_cli_restore", text)
        # No parallel shell mutation engines
        self.assertNotIn("acquire_apply_lock", text)
        self.assertNotIn("set_desktop_icon()", text)
        self.assertNotRegex(text, r"^set_desktop_icon\(\)", msg="set_desktop_icon function must be gone")
        self.assertNotIn("for sz in 512 256 128 64 48", text)

    def test_gui_has_no_shell_mutation_helpers(self) -> None:
        text = GUI.read_text(encoding="utf-8", errors="replace")
        self.assertIn("exec python3 -m kappicon", text)
        for needle in (
            "acquire_apply_lock",
            "set_desktop_icon",
            "clear_desktop_icon",
            "backup_desktop_file",
            "atomic_replace",
        ):
            self.assertNotIn(needle, text, msg=f"GUI still has {needle}")

    def test_offline_package_apply_matches_cli_contract(self) -> None:
        """Same package call the CLI uses, without fzf."""
        clear_engine_cache()
        desktop_id = "kappicon-cli-shared.desktop"
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, desktop_id, name="Shared", icon="system-icon"
            )
            svg = write_svg(sandbox.target / "icon.svg")
            with eng.apply_lock(timeout=5):
                result = eng.apply_icon_to_desktop(
                    desktop_id, str(svg), shape="as-is", backup=False
                )
            self.assertTrue(eng.is_kappicon_icon_name(result["icon_value"]))
            user = Path(eng.USER_APPS_DIR) / desktop_id
            self.assertTrue(user.is_file())
            self.assertEqual(
                eng.read_desktop_icon_value(str(user)), result["icon_value"]
            )


if __name__ == "__main__":
    unittest.main()
