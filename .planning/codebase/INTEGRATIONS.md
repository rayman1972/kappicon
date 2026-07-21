# External Integrations

**Analysis Date:** 2026-07-21

## APIs & External Services

**GitHub:**
- `install.sh` checks `https://raw.githubusercontent.com/rayman1972/kappicon/main/VERSION` and can download current scripts/assets during `--update` when not running from a git checkout.
- Git checkouts update through `git pull --rebase`; project links, screenshots, releases, issues, and source metadata also point to GitHub in `README.md` and `data/io.github.rayman1972.kappicon.metainfo.xml`.
- No credentials or GitHub API tokens are required.

**Other network services:**
- None. The GUI and CLI operate on local files and desktop services.

## Data Storage

**Configuration:**
- Qt INI settings under `$XDG_CONFIG_HOME/KAppIcon/KAppIcon.conf` store appearance, source folder, shape, backup, map filters, recents, and window state.
- `cli/kappicon-cli` reads and atomically updates the same QSettings-compatible file.

**Application data:**
- Created icon library: `$XDG_DATA_HOME/kappicon/icons/`.
- Desktop backups: `$XDG_DATA_HOME/kappicon/backups/`.
- Cross-process apply lock: `$XDG_DATA_HOME/kappicon/apply.lock`.
- Rendered assets: localized Pictures directory under `KAppIcon/`.

**Desktop state:**
- User launcher overrides are written below `$XDG_DATA_HOME/applications/`.
- Content-addressed custom icons are installed below `$XDG_DATA_HOME/icons/hicolor/`.
- Installed system launchers and theme packs under XDG, Flatpak, Snap, `/usr/share`, and `/usr/local/share` are treated as read-only sources.

**Databases/caches:**
- No database or remote storage.
- KDE and GTK icon/application caches are refreshed through desktop utilities, but are not owned by the project.

## Authentication & Identity

- No authentication, accounts, OAuth, or secret material.
- All mutations are scoped to the current Linux user by default; AUR packaging is the separate system-install path.

## Desktop Environment Integration

**Freedesktop:**
- Parses and writes the main `[Desktop Entry]` section of `.desktop` files.
- Resolves icon names through Qt and installed icon-theme directories.
- Installs custom images into the user `hicolor` theme and invokes `update-desktop-database` / `gtk-update-icon-cache` when available.

**KDE Plasma:**
- Calls `kbuildsycoca6` or `kbuildsycoca5` after mutations.
- Uses Breeze/Qt theme icons and optionally `kdialog`.
- The legacy shell refresh path also attempts a `qdbus` Plasma configuration reload.

**Flatpak/Snap visibility:**
- Scans exported Flatpak and Snap desktop-entry locations.
- When `FLATPAK_ID` is set, `flatpak-spawn --host` is used for cache tools and `/run/host` paths are considered.

## Image Tool Integration

- ImageMagick converts PNG/JPEG/WEBP/BMP/GIF/XPM/SVG inputs, creates 512px staging images, masks rounded/circle shapes, and writes hicolor sizes.
- `icns2png` extracts raster candidates from `.icns` files.
- Qt handles previews, canvas editing, and SVG/theme display in the GUI.

## Installation & Packaging

- `install.sh` detects pacman, apt, dnf, or zypper only when dependency installation is explicitly requested.
- Stable and git AUR definitions are in `packaging/aur/kappicon/` and `packaging/aur/kappicon-git/`.
- App discovery metadata consists of `gui/kappicon.desktop`, `data/io.github.rayman1972.kappicon.metainfo.xml`, and `assets/kappicon.png`.

## Monitoring & CI/CD

- Runtime messages go to GUI status/dialog surfaces or stdout/stderr; there is no telemetry, analytics, crash reporting, or structured log service.
- No `.github/workflows/` CI pipeline exists. GitHub repository templates only cover issues and pull requests.

## Webhooks & Callbacks

- None.

---
*Integration audit: 2026-07-21*
*Update when external tools, desktop targets, or distribution channels change*
