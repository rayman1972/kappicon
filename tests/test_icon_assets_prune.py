"""Managed icon install + prune retention (SAFE-04)."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.support.fixtures import install_system_app, install_user_override, write_svg
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg

DESKTOP_ID = "kappicon-test-prune.desktop"


def _place_managed_svg(eng, sandbox, name: str) -> Path:
    """Write a managed scalable asset under user hicolor."""
    dest_dir = Path(eng.USER_ICONS_DIR) / "hicolor" / "scalable" / "apps"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}.svg"
    write_svg(dest, fill="#00aa00")
    return dest


class TestIconAssetsPrune(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_prune_keeps_icon_referenced_by_user_launcher(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            live = "kappicon-live-aaaaaaaaaa-bbbbbbbbbbbb"
            orphan = "kappicon-orphan-cccccccccc-dddddddddddd"
            self.assertTrue(eng.is_kappicon_icon_name(live))
            self.assertTrue(eng.is_kappicon_icon_name(orphan))
            live_path = _place_managed_svg(eng, sandbox, live)
            orphan_path = _place_managed_svg(eng, sandbox, orphan)
            install_user_override(
                sandbox, DESKTOP_ID, name="Prune", icon=live
            )
            with eng.apply_lock(timeout=5):
                removed = eng.prune_unreferenced_kappicon_assets()
            self.assertGreaterEqual(removed, 1)
            self.assertTrue(live_path.is_file())
            self.assertFalse(orphan_path.is_file())

    def test_prune_keeps_icon_referenced_by_backup(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            kept = "kappicon-backup-aaaaaaaaaa-bbbbbbbbbbbb"
            orphan = "kappicon-orphan2-cccccccccc-dddddddddddd"
            kept_path = _place_managed_svg(eng, sandbox, kept)
            orphan_path = _place_managed_svg(eng, sandbox, orphan)
            backup = (
                Path(eng.BACKUP_DIR)
                / f"{DESKTOP_ID}.backup.20260721120000.99.ab12"
            )
            backup.write_text(
                "[Desktop Entry]\nType=Application\n"
                f"Name=B\nExec=true\nIcon={kept}\n",
                encoding="utf-8",
            )
            with eng.apply_lock(timeout=5):
                eng.prune_unreferenced_kappicon_assets()
            self.assertTrue(kept_path.is_file())
            self.assertFalse(orphan_path.is_file())

    def test_prune_keeps_undo_extra_keep(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            name = "kappicon-undokeep-aaaaaaaaaa-bbbbbbbbbbbb"
            path = _place_managed_svg(eng, sandbox, name)
            stack = [
                {
                    "previous_bytes": (
                        b"[Desktop Entry]\nType=Application\n"
                        + f"Icon={name}\n".encode()
                    )
                }
            ]
            keep = eng.undo_keep_icon_names(stack)
            self.assertIn(name, keep)
            with eng.apply_lock(timeout=5):
                eng.prune_unreferenced_kappicon_assets(extra_keep=keep)
            self.assertTrue(path.is_file())
            with eng.apply_lock(timeout=5):
                eng.prune_unreferenced_kappicon_assets(extra_keep=None)
            self.assertFalse(path.is_file())

    def test_collect_referenced_includes_launchers_and_backups(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            a = "kappicon-col-aaaaaaaaaa-bbbbbbbbbbbb"
            b = "kappicon-col-cccccccccc-dddddddddddd"
            install_user_override(sandbox, DESKTOP_ID, name="C", icon=a)
            backup = (
                Path(eng.BACKUP_DIR)
                / f"{DESKTOP_ID}.backup.20260721120000.1.zz99"
            )
            backup.write_text(
                f"[Desktop Entry]\nIcon={b}\n", encoding="utf-8"
            )
            refs = eng.collect_referenced_kappicon_names()
            self.assertIn(a, refs)
            self.assertIn(b, refs)

    def test_content_address_two_applies_do_not_clobber(self) -> None:
        with temp_xdg() as sandbox:
            eng = load_engine()
            install_system_app(
                sandbox, DESKTOP_ID, name="Hash", icon="system-icon"
            )
            svg1 = write_svg(sandbox.target / "v1.svg", fill="#010101")
            svg2 = write_svg(sandbox.target / "v2.svg", fill="#020202")
            with eng.apply_lock(timeout=5):
                r1 = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(svg1), shape="as-is", backup=False
                )
            i1 = r1["icon_value"]
            p1 = (
                Path(eng.USER_ICONS_DIR)
                / "hicolor"
                / "scalable"
                / "apps"
                / f"{i1}.svg"
            )
            self.assertTrue(p1.is_file())
            with eng.apply_lock(timeout=5):
                r2 = eng.apply_icon_to_desktop(
                    DESKTOP_ID, str(svg2), shape="as-is", backup=False
                )
            i2 = r2["icon_value"]
            self.assertNotEqual(i1, i2)
            p2 = (
                Path(eng.USER_ICONS_DIR)
                / "hicolor"
                / "scalable"
                / "apps"
                / f"{i2}.svg"
            )
            self.assertTrue(p2.is_file())
            # Both may exist until prune; after prune only launcher ref (i2) remains
            with eng.apply_lock(timeout=5):
                eng.prune_unreferenced_kappicon_assets()
            self.assertTrue(p2.is_file())
            # i1 may be removed if not in backups/undo
            self.assertEqual(
                eng.read_desktop_icon_value(
                    str(Path(eng.USER_APPS_DIR) / DESKTOP_ID)
                ),
                i2,
            )


if __name__ == "__main__":
    unittest.main()
