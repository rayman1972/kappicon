# kAppIcon

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](#requirements)
[![Arch](https://img.shields.io/badge/arch-x86__64%20%7C%20arm64-blue.svg)](#requirements)
[![Desktop](https://img.shields.io/badge/desktop-KDE%20Plasma%20%7C%20freedesktop-informational.svg)](#features)
[![UI](https://img.shields.io/badge/UI-PyQt6-41cd52.svg)](#requirements)
[![Release](https://img.shields.io/github/v/release/rayman1972/kappicon?include_prereleases&label=release)](https://github.com/rayman1972/kappicon/releases)

**Version 3.0** — change **Linux app launcher icons** without root.

**kAppIcon** is a small **icon manager** for **KDE Plasma** and other **freedesktop** desktops. Map a custom image, copy another app’s icon, or pick one icon from any installed **icon theme** (WhiteSur, Tela, Breeze, Papirus, …) and apply it to a single application — without switching your whole system theme.

It only edits **user-level** [desktop entries](https://specifications.freedesktop.org/desktop-entry-spec/) (`.desktop` files), installs icons into your personal icon theme when needed, and refreshes Plasma / GTK icon caches so menus and panels pick up the change.

| | |
|---|---|
| **GUI** | `kappicon` — Map · Create · Settings |
| **CLI** | `kappicon-cli` — interactive terminal mapper (`fzf`) |
| **Install** | `./install.sh` → `~/.local/bin` (honors XDG paths) |
| **Source** | [github.com/rayman1972/kappicon](https://github.com/rayman1972/kappicon) |

### Quick install

```bash
git clone https://github.com/rayman1972/kappicon.git
cd kappicon
./install.sh
kappicon          # GUI
# kappicon-cli    # terminal
```

### Arch Linux (AUR)

```bash
# stable release
yay -S kappicon
# or latest git
yay -S kappicon-git
```

- [kappicon](https://aur.archlinux.org/packages/kappicon) — tagged release  
- [kappicon-git](https://aur.archlinux.org/packages/kappicon-git) — latest `main`  

PKGBUILDs are also kept in-tree under [`packaging/aur/`](packaging/aur/) (see [packaging/aur/README.md](packaging/aur/README.md) for updates).

### Flatpak (local build)

App id: **`io.github.rayman1972.kappicon`** — see [`packaging/flatpak/`](packaging/flatpak/).

```bash
flatpak-builder --user --install --force-clean \
  packaging/flatpak/build-dir \
  packaging/flatpak/io.github.rayman1972.kappicon.yml
flatpak run io.github.rayman1972.kappicon
```

Not on Flathub yet. The sandbox grants **home + host-os** access on purpose so launchers and system icon themes can be read/written.

## Screenshots

### Map — pick a file icon and an application

![Map tab](screenshots/gui-map.png)

### Map — reuse another app’s icon

![Map from another app](screenshots/gui-map-from-app.png)

### Map — pick an icon from any installed theme pack

Browse packs such as **WhiteSur**, **Tela**, **Breeze**, or any theme under `~/.local/share/icons` / `/usr/share/icons`, then apply a single icon from that pack to any app — without switching your whole system theme.

![Map from icon theme](screenshots/gui-map-icon-theme.png)

### Create — pixel editor, undo/redo, and icon library

Draw or import, **Undo** / **Redo** mistakes (Ctrl+Z), then save a standard 512×512 icon.

![Create tab](screenshots/gui-create.png)

### Settings — appearance, shape, backups

![Settings tab](screenshots/gui-settings.png)

## Features

| Area | What you get |
|------|----------------|
| **Map · From file** | Assign downloaded or library images (PNG, ICNS, SVG, …) to a launcher |
| **Map · From another app** | Copy the theme icon another installed app already uses (e.g. give Shelly Discover’s icon) |
| **Map · From icon theme** | Cross-use icons from **any installed icon theme pack** (WhiteSur, Tela, Breeze, Papirus, …) — pick a theme set, browse its app icons, apply one to a different program |
| **Create** | Pixel canvas (pen / eraser / fill / picker) with **undo/redo**; **import with pan/zoom** so you can frame a subject in a larger photo; saves are always **512×512** PNGs in your library |
| **Overrides** | List user launcher overrides; open in Map or reset to the system icon |
| **Missing** | Find apps with empty or unresolved `Icon=`; jump to Map to fix them |
| **Shapes** | When applying custom images: keep as designed, or mask to square / rounded / circle |
| **Reset** | Restore an app’s system icon from Map or Overrides |
| **Backups** | Optional auto-backup of `.desktop` files before changes + restore UI |
| **CLI** | Terminal mapper with `fzf` (`kappicon-cli`) |
| **Safe by design** | User overrides only (`~/.local/share/applications/`), atomic writes, apply lock, validated desktop ids |

Supported image types include **PNG, JPG, WEBP, SVG, ICNS, BMP, GIF, XPM**.

## Requirements

- Linux desktop (Plasma / Breeze-friendly; works elsewhere with freedesktop menus)
- **x86_64 and arm64** compatible (architecture-independent; needs deps for your arch)
- Python 3 + **PyQt6**
- **ImageMagick** (`magick` or `convert`) for rasterizing custom icons
- **icns2png** (`libicns` / `icnsutils`) for Apple `.icns` files
- **fzf** for the CLI
- **kdialog** (optional notifications on KDE)

## Installation

```bash
git clone https://github.com/rayman1972/kappicon.git
cd kappicon
./install.sh
```

To update later (from a git clone):

```bash
./install.sh --update
```

`install.sh` installs into `$XDG_BIN_HOME` (default `~/.local/bin`) and adds a desktop entry under `$XDG_DATA_HOME/applications`. Dependencies are installed via your package manager when possible:

| Distro | Packages |
|--------|----------|
| **Arch / CachyOS** | `python python-pyqt6 libicns imagemagick kdialog fzf` |
| **Debian / Ubuntu** | `python3 python3-pyqt6 icnsutils imagemagick kdialog fzf` |
| **Fedora** | `python3 python3-pyqt6 libicns-utils ImageMagick kdialog fzf` |
| **openSUSE Leap / Tumbleweed** | `python3` `python3-PyQt6` (or `python3XY-PyQt6` for your Python) `libicns` `ImageMagick` `kdialog` `fzf` |

On openSUSE, `install.sh` picks the PyQt6 RPM that matches your default `python3` (e.g. `python312-PyQt6`) when the generic name is not available, and falls back to `pip install PyQt6` if needed.

Ensure your user bin dir (`$XDG_BIN_HOME`, default `~/.local/bin`) is on your `PATH`.

## Usage

### GUI

```bash
kappicon
```

Or open **kAppIcon** from the application menu.

**Tabs**

1. **Map** — choose the icon source, then the app to change, then **Apply**  
   - *From file* — downloads, your library, or any browsed image  
   - *From another app* — reuse the freedesktop theme icon another launcher already points at  
   - *From icon theme* — pick an **installed theme pack** (user or system), filter its app icons, and assign one of those icons to a different application. Your global icon theme stays as-is; only that app’s launcher is overridden  
2. **Create** — draw or import (pan/zoom) → **Save icon** or **Save and use in Map**  
3. **Settings** — light/dark/system colors, applied icon shape, backups, source folder, restore, cache refresh  
4. **Overrides** — review user-customized launchers; open in Map or reset to system  
5. **Missing** — apps with no usable icon; open in Map to assign one  

### CLI

```bash
kappicon-cli --help
kappicon-cli              # interactive icon → app mapper (fzf)
kappicon-cli --settings
kappicon-cli --restore
kappicon-cli --refresh
```

## Paths

Paths follow the [XDG Base Directory](https://specifications.freedesktop.org/basedir-spec/latest/) spec and [xdg-user-dirs](https://www.freedesktop.org/wiki/Software/xdg-user-dirs/) (localized Downloads/Pictures). Defaults match a typical Linux home layout.

| What | Where (default) | Env / override |
|------|-----------------|----------------|
| Config (Qt + CLI) | `$XDG_CONFIG_HOME/KAppIcon/` → `~/.config/KAppIcon/` | `XDG_CONFIG_HOME` |
| Created icons (library) | `$XDG_DATA_HOME/kappicon/icons/` | `XDG_DATA_HOME` |
| Desktop backups | `$XDG_DATA_HOME/kappicon/backups/` | `XDG_DATA_HOME` |
| User launcher overrides | `$XDG_DATA_HOME/applications/` | `XDG_DATA_HOME` |
| User hicolor theme icons | `$XDG_DATA_HOME/icons/hicolor/` | `XDG_DATA_HOME` |
| Installed binaries | `$XDG_BIN_HOME/` → `~/.local/bin/` | `XDG_BIN_HOME` |
| Source folder default | `xdg-user-dir DOWNLOAD` → `~/Downloads` | Settings / `source/folder` |
| Rendered apply PNGs | `xdg-user-dir PICTURES/KAppIcon` → `~/Pictures/KAppIcon/` | `XDG_PICTURES_DIR` (via user-dirs) |
| Theme packs (read-only) | `$XDG_DATA_HOME/icons/`, `~/.icons/`, `$XDG_DATA_DIRS/*/icons` | — |

## How it works

- Edits only your **user** `.desktop` overrides — system packages are left alone.
- *From another app* and many theme sources set `Icon=` to a freedesktop **name** so they follow theme resolution.
- *From icon theme* can also apply a concrete file from the pack (then installed under your user **hicolor** theme like other custom images).
- Custom image files are installed under the user **hicolor** theme (and often referenced by name) so Plasma menus refresh reliably.
- SVG sources can be used as-is when shape is *As designed*; other shapes re-export a masked 512×512 PNG.

## Origins

kAppIcon grew out of **[macosicons-linux](https://github.com/system-rw/macosicons-linux)** by [System RW](https://github.com/system-rw) (MIT). Their project is a focused tool for mapping custom images (including macOS-style `.icns`) onto Linux launchers.

This repository continues under the same MIT license as a **substantial rework and expansion**: multi-source mapping (file / another app / installed icon theme packs), a Create tab with undo/redo, safer apply/restore paths, XDG-aware install, and a rebranded GUI + CLI (`kappicon` / `kappicon-cli`). Thanks to the original author for the idea and the base that made this possible.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).  
Security reports: [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).

Copyright notices include the original author (System RW) and later substantial contributions in this project.
