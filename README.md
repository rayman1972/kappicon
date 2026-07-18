# KAppIcon

**Version 3.0** — customize Linux application launcher icons without root.

KAppIcon updates your user-level [freedesktop](https://specifications.freedesktop.org/desktop-entry-spec/) `.desktop` files, installs icons into your personal icon theme when needed, and refreshes Plasma / GTK icon caches so menus and panels pick up the change.

**Source:** [github.com/rayman1972/kappicon](https://github.com/rayman1972/kappicon)

## Screenshots

### Map — pick a file icon and an application

![Map tab](screenshots/gui-map.png)

### Map — reuse another app’s icon

![Map from another app](screenshots/gui-map-from-app.png)

### Map — pick an icon from any installed theme pack

Browse packs such as **WhiteSur**, **Tela**, **Breeze**, or any theme under `~/.local/share/icons` / `/usr/share/icons`, then apply a single icon from that pack to any app — without switching your whole system theme.

![Map from icon theme](screenshots/gui-map-icon-theme.png)

### Create — pixel editor and icon library

![Create tab](screenshots/gui-create.png)

### Settings — appearance, shape, backups

![Settings tab](screenshots/gui-settings.png)

## Features

| Area | What you get |
|------|----------------|
| **Map · From file** | Assign downloaded or library images (PNG, ICNS, SVG, …) to a launcher |
| **Map · From another app** | Copy the theme icon another installed app already uses (e.g. give Shelly Discover’s icon) |
| **Map · From icon theme** | Cross-use icons from **any installed icon theme pack** (WhiteSur, Tela, Breeze, Papirus, …) — pick a theme set, browse its app icons, apply one to a different program |
| **Create** | Pixel canvas (pen / eraser / fill / picker) with **undo/redo**; imports and saves are always **512×512** PNGs in your library |
| **Shapes** | When applying custom images: keep as designed, or mask to square / rounded / circle |
| **Reset** | Restore an app’s system icon from Map |
| **Backups** | Optional auto-backup of `.desktop` files before changes + restore UI |
| **CLI** | Terminal mapper with `fzf` (`kappicon`) |
| **Safe by design** | User overrides only (`~/.local/share/applications/`), atomic writes, apply lock, validated desktop ids |

Supported image types include **PNG, JPG, WEBP, SVG, ICNS, BMP, GIF, XPM**.

## Requirements

- Linux desktop (Plasma / Breeze-friendly; works elsewhere with freedesktop menus)
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

`install.sh` installs into `~/.local/bin` and adds desktop entries. Dependencies are installed via your package manager when possible:

| Distro | Packages |
|--------|----------|
| **Arch / CachyOS** | `python python-pyqt6 libicns imagemagick kdialog fzf` |
| **Debian / Ubuntu** | `python3 python3-pyqt6 icnsutils imagemagick kdialog fzf` |
| **Fedora** | `python3 python3-pyqt6 libicns-utils ImageMagick kdialog fzf` |
| **openSUSE Leap / Tumbleweed** | `python3` `python3-PyQt6` (or `python3XY-PyQt6` for your Python) `libicns` `ImageMagick` `kdialog` `fzf` |

On openSUSE, `install.sh` picks the PyQt6 RPM that matches your default `python3` (e.g. `python312-PyQt6`) when the generic name is not available, and falls back to `pip install PyQt6` if needed.

Ensure `~/.local/bin` is on your `PATH`.

## Usage

### GUI

```bash
kappicon-gui
```

Or open **KAppIcon** from the application menu.

**Tabs**

1. **Map** — choose the icon source, then the app to change, then **Apply**  
   - *From file* — downloads, your library, or any browsed image  
   - *From another app* — reuse the freedesktop theme icon another launcher already points at  
   - *From icon theme* — pick an **installed theme pack** (user or system), filter its app icons, and assign one of those icons to a different application. Your global icon theme stays as-is; only that app’s launcher is overridden  
2. **Create** — draw or import → **Save icon** or **Save and use in Map**  
3. **Settings** — light/dark/system colors, applied icon shape, backups, source folder, restore, cache refresh  

### CLI

```bash
kappicon --help
kappicon              # interactive icon → app mapper (fzf)
kappicon --settings
kappicon --restore
kappicon --refresh
```

## Paths

| What | Where |
|------|--------|
| Config (Qt settings) | `~/.config/KAppIcon/KAppIcon.conf` |
| Created icons (library) | `~/.local/share/kappicon/icons/` |
| Rendered apply PNGs | `~/Pictures/KAppIcon/` |
| Desktop backups | `~/.local/share/kappicon/backups/` |
| User launcher overrides | `~/.local/share/applications/` |
| User hicolor theme icons | `~/.local/share/icons/hicolor/` |
| Theme packs (read-only browse) | `~/.local/share/icons/`, `~/.icons/`, `/usr/share/icons/`, … |

## How it works

- Edits only your **user** `.desktop` overrides — system packages are left alone.
- *From another app* and many theme sources set `Icon=` to a freedesktop **name** so they follow theme resolution.
- *From icon theme* can also apply a concrete file from the pack (then installed under your user **hicolor** theme like other custom images).
- Custom image files are installed under the user **hicolor** theme (and often referenced by name) so Plasma menus refresh reliably.
- SVG sources can be used as-is when shape is *As designed*; other shapes re-export a masked 512×512 PNG.

## License

See [LICENSE](LICENSE).
