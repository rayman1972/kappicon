"""Undo snapshot + sandboxed backup restore (SAFE-01)."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.support.fixtures import install_system_app, write_desktop, write_svg
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg

DESKTOP_ID = "kappicon-test-undoapp.desktop"


class TestUndoRestore(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_undo_restores_previous_override_bytes(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="UndoDemo", icon="system-icon"
            )
            # First apply creates override
            svg = write_svg(sandbox.target / "a.svg", fill="#111111")
            with eng.apply_lock(timeout=5):
                r1 = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(svg), shape="as-is", backup=False
                )
            self.assertIsNone(r1["previous_bytes"])
            user_path = Path(eng.USER_APPS_DIR) / DESKTOP_ID
            mid_bytes = user_path.read_bytes()
            # Second apply; previous_bytes is mid state
            svg2 = write_svg(sandbox.target / "b.svg", fill="#222222")
            with eng.apply_lock(timeout=5):
                r2 = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(svg2), shape="as-is", backup=False
                )
            self.assertEqual(r2["previous_bytes"], mid_bytes)
            with eng.apply_lock(timeout=5):
                eng.restore_user_desktop_snapshot(DESKTOP_ID, r2["previous_bytes"])
            self.assertEqual(user_path.read_bytes(), mid_bytes)

    def test_undo_removes_override_when_previous_was_absent(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="UndoDemo", icon="system-icon"
            )
            svg = write_svg(sandbox.target / "a.svg")
            with eng.apply_lock(timeout=5):
                r1 = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(svg), shape="as-is", backup=False
                )
            self.assertIsNone(r1["previous_bytes"])
            user_path = Path(eng.USER_APPS_DIR) / DESKTOP_ID
            self.assertTrue(user_path.is_file())
            with eng.apply_lock(timeout=5):
                eng.restore_user_desktop_snapshot(DESKTOP_ID, None)
            self.assertFalse(user_path.is_file())
            self.assertTrue((sandbox.system_apps / DESKTOP_ID).is_file())

    def test_backup_restore_reinstalls_launcher(self) -> None:
        """Sandbox simulation of CLI do_restore (parse + lock + atomic write)."""
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="RestoreDemo", icon="system-icon"
            )
            user_path = Path(eng.USER_APPS_DIR) / DESKTOP_ID
            write_desktop(
                user_path,
                name="RestoreDemo",
                icon="custom-before-restore",
                extra_desktop_entry_lines=["Comment=to-be-restored"],
            )
            backup_name = (
                f"{DESKTOP_ID}.backup.20260721120000.12345.ab12"
            )
            backup_path = Path(eng.BACKUP_DIR) / backup_name
            backup_body = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=RestoreDemo\n"
                "Exec=true\n"
                "Icon=from-backup\n"
                "Comment=from-backup\n"
            )
            backup_path.write_text(backup_body, encoding="utf-8")
            self.assertEqual(
                eng.parse_backup_desktop_id(backup_name), DESKTOP_ID
            )
            self.assertIsNone(eng.parse_backup_desktop_id("../evil.desktop.backup.1.1.a"))
            self.assertIsNone(eng.parse_backup_desktop_id("not-a-backup"))
            # Corrupt current user file
            user_path.write_text("[Desktop Entry]\nName=corrupt\n", encoding="utf-8")
            with eng.apply_lock(timeout=5):
                eng._atomic_copy_file(str(backup_path), str(user_path))
            self.assertEqual(user_path.read_text(encoding="utf-8"), backup_body)

    def test_parse_backup_desktop_id_rejects_bad_names(self) -> None:
        with temp_xdg():
            eng = load_engine()
            self.assertIsNone(eng.parse_backup_desktop_id(""))
            self.assertIsNone(eng.parse_backup_desktop_id("foo.desktop"))
            self.assertIsNone(
                eng.parse_backup_desktop_id("foo.desktop.backup.notdigits.1.ab")
            )


if __name__ == "__main__":
    unittest.main()
