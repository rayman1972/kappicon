# KAppIcon

**KAppIcon** is a Linux utility to change application icons, reuse icons from other apps, and design your own.

It works by safely updating user-level `.desktop` files (no root required) and refreshing the desktop icon cache.

## Features

* **Map icons to apps** — pick any image (or another app’s icon) and apply it to a launcher
* **From another app** — e.g. give Shelly the same icon Discover uses
* **Create tab** — pixel editor + import PNG / JPG / WEBP (and more) to build icons
* **Icon library** — saved creations live in `~/.local/share/kappicon/icons/`
* **Backups & restore** — optional copies of `.desktop` files before changes
* **CLI** — terminal workflow with `fzf` for power users

## Screenshots

### GUI
![KAppIcon GUI](screenshots/gui-dark-light.png)

## Installation

```bash
./install.sh
```

Dependencies (installed automatically when possible):

| Distro | Packages |
|--------|----------|
| **Arch / CachyOS** | `python python-pyqt6 libicns imagemagick kdialog fzf` |
| **Debian / Ubuntu** | `python3 python3-pyqt6 icnsutils imagemagick kdialog fzf` |
| **Fedora** | `python3 python3-pyqt6 libicns-utils ImageMagick kdialog fzf` |

## Usage

### Graphical interface

```bash
kappicon-gui
```

Or search for **KAppIcon** in your app menu.

**Tabs:**

1. **Map** — choose an icon (file / another app) → choose the app to change → Apply  
2. **Create** — draw pixels or import an image → Save / Save & use in Map  
3. **Settings** — theme, backups, source folder, restore, cache refresh  

### Command line

```bash
kappicon --help
kappicon              # interactive mapper
kappicon --settings
kappicon --restore
kappicon --refresh
```

Legacy commands `apply-mac-icon` / `apply-mac-icon-gui` still work as shims after install.

## Paths

| What | Where |
|------|--------|
| Config | `~/.config/KAppIcon/KAppIcon.conf` |
| Created icons | `~/.local/share/kappicon/icons/` |
| Applied icon PNGs | `~/Pictures/KAppIcon/` |
| Desktop backups | `~/.local/share/kappicon/backups/` |

## Notes

* Changes write to `~/.local/share/applications/` so they override system launchers for your user only.
* Theme icons (Map → “From another app”) set `Icon=` to a freedesktop icon name and follow your icon theme.
* Custom files are normalized to a 512×512 PNG under `~/Pictures/KAppIcon/`.

## License

See [LICENSE](LICENSE).
