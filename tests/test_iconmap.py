"""Icon map export/import (portable overrides)."""
from __future__ import annotations

import json
import os
import unittest
import zipfile
from pathlib import Path

from tests.support.fixtures import write_desktop, write_png
from tests.support.load_engine import clear_engine_cache, load_engine
from tests.support.xdg_sandbox import temp_xdg

DESKTOP_ID = "kappicon-map-test.desktop"


class TestIconMap(unittest.TestCase):
    def setUp(self) -> None:
        clear_engine_cache()

    def test_export_empty(self) -> None:
        with temp_xdg() as sb:
            eng = load_engine()
            from kappicon import iconmap

            out = sb.data_dir / "empty.zip"
            summary = iconmap.export_icon_map(str(out), overrides=[])
            self.assertEqual(summary["count"], 0)
            self.assertTrue(out.is_file())
            with zipfile.ZipFile(out) as zf:
                data = json.loads(zf.read("kappicon-map.json"))
            self.assertEqual(data["format"], "kappicon.iconmap")
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["entries"], [])

    def test_export_theme_and_asset(self) -> None:
        with temp_xdg() as sb:
            eng = load_engine()
            from kappicon import iconmap
            from kappicon.icons import install_named_hicolor_asset

            # Craft override rows manually for unit purity
            theme_row = {
                "desktop_id": "org.example.theme.desktop",
                "display": "Theme App",
                "icon": "system-file-manager",
                "system_icon": "utilities-terminal",
                "system_path": "/usr/share/applications/org.example.theme.desktop",
            }
            # Asset: install kappicon name then export
            png = write_png(sb.target / "src.png", size=64)
            icon_name = "kappicon-maptest-aabbccddee-112233445566"
            install_named_hicolor_asset(str(png), icon_name)
            asset_row = {
                "desktop_id": DESKTOP_ID,
                "display": "Map Test",
                "icon": icon_name,
                "system_icon": "old",
                "system_path": "/usr/share/applications/" + DESKTOP_ID,
            }
            out = sb.data_dir / "pack.zip"
            summary = iconmap.export_icon_map(
                str(out), overrides=[theme_row, asset_row]
            )
            self.assertEqual(summary["count"], 2)
            self.assertEqual(summary["theme_count"], 1)
            self.assertEqual(summary["asset_count"], 1)
            with zipfile.ZipFile(out) as zf:
                data = json.loads(zf.read("kappicon-map.json"))
                kinds = {e["kind"] for e in data["entries"]}
                self.assertEqual(kinds, {"theme", "asset"})
                asset_ents = [e for e in data["entries"] if e["kind"] == "asset"]
                self.assertTrue(asset_ents[0]["asset"] in zf.namelist())

    def test_export_skips_foreign_absolute(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon import iconmap

            row = {
                "desktop_id": "org.example.foreign.desktop",
                "display": "Foreign",
                "icon": "/tmp/not-ours/icon.png",
            }
            built = iconmap.build_export_entries([row])
            self.assertEqual(built["entries"], [])
            self.assertEqual(len(built["skipped"]), 1)

    def test_zip_slip_rejected(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon import iconmap

            evil = sb.data_dir / "evil.zip"
            with zipfile.ZipFile(evil, "w") as zf:
                zf.writestr(
                    "kappicon-map.json",
                    json.dumps({
                        "format": "kappicon.iconmap",
                        "version": 1,
                        "entries": [{
                            "desktop_id": DESKTOP_ID,
                            "display": "X",
                            "icon": "kappicon-x",
                            "kind": "asset",
                            "asset": "assets/../../etc/passwd",
                        }],
                    }),
                )
                zf.writestr("assets/../../etc/passwd", b"nope")
            with self.assertRaises(iconmap.IconMapError):
                iconmap.plan_import(str(evil))

    def test_import_skips_missing_app(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon import iconmap

            zpath = sb.data_dir / "theme-only.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr(
                    "kappicon-map.json",
                    json.dumps({
                        "format": "kappicon.iconmap",
                        "version": 1,
                        "entries": [{
                            "desktop_id": "org.missing.app.desktop",
                            "display": "Missing",
                            "icon": "folder",
                            "kind": "theme",
                        }],
                    }),
                )
            plan = iconmap.plan_import(str(zpath))
            self.assertEqual(plan["apply_count"], 0)
            self.assertEqual(len(plan["skip_missing"]), 1)

    def test_import_apply_asset_and_theme(self) -> None:
        with temp_xdg() as sb:
            eng = load_engine()
            from kappicon import iconmap
            from kappicon.lock import apply_lock
            from kappicon.paths import USER_APPS_DIR, USER_ICONS_DIR
            from kappicon.desktop import read_desktop_icon_value

            # System desktops so find_any_desktop_path works — write under user apps
            # and also make them discoverable: find_any checks USER then system
            write_desktop(
                Path(USER_APPS_DIR) / DESKTOP_ID,
                name="Map Test",
                icon="utilities-terminal",
            )
            write_desktop(
                Path(USER_APPS_DIR) / "org.example.theme.desktop",
                name="Theme App",
                icon="utilities-terminal",
            )
            png = write_png(sb.target / "pack.png", size=48)
            icon_name = "kappicon-roundtrip-aabbccdd-112233445566"
            zpath = sb.data_dir / "round.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr(
                    "kappicon-map.json",
                    json.dumps({
                        "format": "kappicon.iconmap",
                        "version": 1,
                        "entries": [
                            {
                                "desktop_id": DESKTOP_ID,
                                "display": "Map Test",
                                "icon": icon_name,
                                "kind": "asset",
                                "asset": f"assets/{icon_name}.png",
                            },
                            {
                                "desktop_id": "org.example.theme.desktop",
                                "display": "Theme App",
                                "icon": "system-file-manager",
                                "kind": "theme",
                            },
                        ],
                    }),
                )
                zf.write(str(png), f"assets/{icon_name}.png")

            plan = iconmap.plan_import(str(zpath))
            self.assertEqual(plan["apply_count"], 2)
            self.assertEqual(plan["theme_count"], 1)
            self.assertEqual(plan["asset_count"], 1)
            with apply_lock():
                result = iconmap.apply_import_plan(plan, backup=False)
            self.assertEqual(result["applied_count"], 2)
            self.assertEqual(result["failed_count"], 0)
            self.assertEqual(
                read_desktop_icon_value(os.path.join(USER_APPS_DIR, DESKTOP_ID)),
                icon_name,
            )
            self.assertEqual(
                read_desktop_icon_value(
                    os.path.join(USER_APPS_DIR, "org.example.theme.desktop")
                ),
                "system-file-manager",
            )
            installed = Path(USER_ICONS_DIR) / "hicolor" / "512x512" / "apps" / f"{icon_name}.png"
            self.assertTrue(installed.is_file())

    def test_invalid_format(self) -> None:
        with temp_xdg() as sb:
            load_engine()
            from kappicon import iconmap

            zpath = sb.data_dir / "bad.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr(
                    "kappicon-map.json",
                    json.dumps({"format": "nope", "version": 1, "entries": []}),
                )
            with self.assertRaises(iconmap.IconMapError):
                iconmap.plan_import(str(zpath))


if __name__ == "__main__":
    unittest.main()
