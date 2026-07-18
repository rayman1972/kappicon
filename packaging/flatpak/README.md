# Flatpak packaging for kAppIcon

App ID: **`io.github.rayman1972.kappicon`**

## Why the sandbox is “open”

kAppIcon’s job is to edit **host** launcher icons (`.desktop` files under `~/.local/share/applications`, icon themes, system catalogs). A tight sandbox would break the app.

The manifest therefore grants:

- `--filesystem=home` — user apps, icons, config, Pictures/Downloads  
- `--filesystem=host-os:ro` — host `/usr` as `/run/host/usr` (plain `/usr` is reserved by Flatpak)  
- `--talk-name=org.freedesktop.Flatpak` — run `kbuildsycoca` / cache tools on the host via `flatpak-spawn --host`

This is intentional for a system-integration utility (similar to other host-facing tools).

## Build & install (local)

```bash
# once
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

cd /path/to/kappicon
flatpak-builder --user --install --force-clean \
  packaging/flatpak/build-dir \
  packaging/flatpak/io.github.rayman1972.kappicon.yml
```

Run:

```bash
flatpak run io.github.rayman1972.kappicon
```

Export a bundle (optional, for side-loading):

```bash
flatpak-builder --repo=packaging/flatpak/repo --force-clean \
  packaging/flatpak/build-dir \
  packaging/flatpak/io.github.rayman1972.kappicon.yml
flatpak build-bundle packaging/flatpak/repo kappicon.flatpak io.github.rayman1972.kappicon
```

## Flathub (later)

Publishing to Flathub needs a PR against [flathub/flathub](https://github.com/flathub/flathub) with this app-id and a review of permissions (`filesystem=home` will be scrutinized — explain why in the PR).

Typical flow:

1. Fork flathub, create branch `new-pr`
2. Add submodule / repo `io.github.rayman1972.kappicon`
3. Copy this manifest (use `type: git` / archive sources instead of `type: dir` for Flathub)
4. Open PR per Flathub app requirements

## Runtime stack

| Piece | Version |
|-------|---------|
| `org.kde.Platform` / `Sdk` | 6.10 |
| `com.riverbankcomputing.PyQt.BaseApp` | 6.10 |
| ImageMagick | built as module |
| libicns | built as module |
| fzf | prebuilt binary (x86_64) |
