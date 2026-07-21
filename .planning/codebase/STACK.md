# Technology Stack

**Analysis Date:** 2026-07-21

## Languages

**Primary:**
- Bash — executable entry points, XDG discovery, installation, CLI interaction, and a legacy GUI apply path in `gui/kappicon`, `cli/kappicon-cli`, and `install.sh`.
- Python 3 — embedded in heredocs inside both executables; the main GUI and current GUI apply engine occupy most of `gui/kappicon`.

**Secondary:**
- Desktop Entry syntax — application launcher in `gui/kappicon.desktop`.
- AppStream XML — software-center metadata in `data/io.github.rayman1972.kappicon.metainfo.xml`.
- Arch PKGBUILD shell — stable and VCS packages under `packaging/aur/`.

## Runtime

**Environment:**
- Linux desktop with freedesktop/XDG data directories; KDE Plasma is the primary experience, with GTK/freedesktop compatibility.
- Python 3 with PyQt6 for the GUI.
- No compilation or application server; `gui/kappicon` and `cli/kappicon-cli` run directly as executables.

**Package Manager:**
- No language-level package manager, manifest, or lockfile.
- User installation is handled by `install.sh`; Arch system installation is described by `packaging/aur/kappicon/PKGBUILD` and `packaging/aur/kappicon-git/PKGBUILD`.

## Frameworks

**Core:**
- PyQt6 — widgets, painting, dialogs, settings, timers, drag/drop, and icon-theme access in `gui/kappicon`.
- Qt `QSettings` — persistent GUI/CLI-compatible INI configuration under `$XDG_CONFIG_HOME/KAppIcon/`.

**Testing:**
- No committed automated test framework, test files, coverage configuration, or CI workflow.
- Current checks are syntax/metadata validation and manual GUI/CLI smoke testing; see `TESTING.md`.

**Build/Dev:**
- No build step.
- AUR packages install the executable scripts and metadata verbatim.

## Key Dependencies

**Critical:**
- PyQt6 — required for `gui/kappicon`.
- ImageMagick (`magick` or legacy `convert`) — raster conversion, resizing, and shape masks.
- `icns2png` from libicns/icnsutils — extraction of Apple `.icns` assets.
- `fzf` — interactive selection in `cli/kappicon-cli`.
- util-linux `flock` / Python `fcntl` — cross-process serialization of launcher and icon mutations.

**Desktop integration:**
- `kbuildsycoca6`/`kbuildsycoca5`, `update-desktop-database`, and `gtk-update-icon-cache` refresh desktop caches when available.
- `kdialog` is optional for KDE-native dialogs/notifications; `zenity` and `notify-send` are fallback notification paths in the shell wrapper.
- `xdg-user-dir` is optional; scripts fall back to `user-dirs.dirs` and conventional home paths.

## Configuration

**Environment:**
- Honors `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_BIN_HOME`, `XDG_DATA_DIRS`, `XDG_RUNTIME_DIR`, `TMPDIR`, and `FLATPAK_ID`.
- Test/development overrides include `CONFIG_DIR`, `DATA_DIR`, `USER_APPS_DIR`, `USER_ICONS_DIR`, `TARGET_DIR`, and `DOWNLOADS_DIR`.
- No application secrets or `.env` files are used.

**Persistent files:**
- `VERSION` is the source version marker (`3.1.1` at analysis time).
- User preferences live in `KAppIcon.conf` through `QSettings`; generated icons, backups, and the apply lock live below `$XDG_DATA_HOME/kappicon/`.

## Platform Requirements

**Development:**
- Linux, Bash, Python 3, and PyQt6; optional metadata validators include `desktop-file-validate` and `appstreamcli`.
- Architecture-independent source; README states x86_64 and arm64 support when dependencies exist.

**Production:**
- User install defaults to `$XDG_BIN_HOME` and `$XDG_DATA_HOME` without root.
- Arch packages install system-wide under `/usr`; package version metadata is maintained under `packaging/aur/`.

---
*Stack analysis: 2026-07-21*
*Update after major dependency or packaging changes*
