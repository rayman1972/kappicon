"""Temporary XDG / kAppIcon path isolation for mutation tests."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional


@dataclass
class XDGSandbox:
    """Absolute paths under a temporary root used by mutation tests."""

    root: Path
    home: Path
    config_dir: Path
    data_dir: Path
    user_apps: Path
    user_icons: Path
    backups: Path
    library: Path
    target: Path
    system_share: Path
    system_apps: Path
    pictures: Path
    downloads: Path


_ENV_KEYS = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_BIN_HOME",
    "XDG_DATA_DIRS",
    "XDG_PICTURES_DIR",
    "XDG_DOWNLOAD_DIR",
    "CONFIG_DIR",
    "DATA_DIR",
    "USER_APPS_DIR",
    "USER_ICONS_DIR",
    "TARGET_DIR",
    "LIBRARY_DIR",
    "BACKUP_DIR_DEFAULT",
    "DOWNLOADS_DIR",
    "DESKTOP_LIST",
)


def assert_path_under_sandbox(path: os.PathLike | str, root: Path) -> None:
    real_path = Path(path).resolve()
    real_root = root.resolve()
    try:
        real_path.relative_to(real_root)
    except ValueError as exc:
        raise AssertionError(f"{real_path} is not under sandbox {real_root}") from exc


@contextmanager
def temp_xdg(*, inherit_system_data_dirs: bool = False) -> Iterator[XDGSandbox]:
    """
    Create a temporary home/XDG layout and export kAppIcon path env vars.

    Restores prior environment on exit (deletes keys that were unset before).
    """
    saved: Dict[str, Optional[str]] = {k: os.environ.get(k) for k in _ENV_KEYS}

    with tempfile.TemporaryDirectory(prefix="kappicon-test-") as tmp:
        root = Path(tmp).resolve()
        home = root / "home"
        config = home / ".config"
        data = home / ".local" / "share"
        xdg_bin = home / ".local" / "bin"
        system_share = root / "system" / "share"
        system_apps = system_share / "applications"
        pictures = home / "Pictures"
        downloads = home / "Downloads"

        kappicon_data = data / "kappicon"
        user_apps = data / "applications"
        user_icons = data / "icons"
        backups = kappicon_data / "backups"
        library = kappicon_data / "icons"
        target = pictures / "KAppIcon"
        config_app = config / "KAppIcon"

        for d in (
            home,
            config,
            config_app,
            data,
            xdg_bin,
            kappicon_data,
            user_apps,
            user_icons,
            backups,
            library,
            target,
            system_share,
            system_apps,
            pictures,
            downloads,
        ):
            d.mkdir(parents=True, exist_ok=True)

        data_dirs = str(system_share)
        if inherit_system_data_dirs:
            host = (saved.get("XDG_DATA_DIRS") or os.environ.get("XDG_DATA_DIRS") or "").strip()
            if host:
                data_dirs = f"{system_share}:{host}"
            else:
                data_dirs = f"{system_share}:/usr/local/share:/usr/share"

        os.environ["HOME"] = str(home)
        os.environ["XDG_CONFIG_HOME"] = str(config)
        os.environ["XDG_DATA_HOME"] = str(data)
        os.environ["XDG_BIN_HOME"] = str(xdg_bin)
        os.environ["XDG_DATA_DIRS"] = data_dirs
        os.environ["XDG_PICTURES_DIR"] = str(pictures)
        os.environ["XDG_DOWNLOAD_DIR"] = str(downloads)
        os.environ["CONFIG_DIR"] = str(config_app)
        os.environ["DATA_DIR"] = str(kappicon_data)
        os.environ["USER_APPS_DIR"] = str(user_apps)
        os.environ["USER_ICONS_DIR"] = str(user_icons)
        os.environ["TARGET_DIR"] = str(target)
        os.environ["LIBRARY_DIR"] = str(library)
        os.environ["BACKUP_DIR_DEFAULT"] = str(backups)
        os.environ["DOWNLOADS_DIR"] = str(downloads)
        # Empty list: discovery tests install fixtures under system_apps
        os.environ["DESKTOP_LIST"] = ""

        sandbox = XDGSandbox(
            root=root,
            home=home,
            config_dir=config_app,
            data_dir=kappicon_data,
            user_apps=user_apps,
            user_icons=user_icons,
            backups=backups,
            library=library,
            target=target,
            system_share=system_share,
            system_apps=system_apps,
            pictures=pictures,
            downloads=downloads,
        )
        try:
            yield sandbox
        finally:
            for key, val in saved.items():
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val
