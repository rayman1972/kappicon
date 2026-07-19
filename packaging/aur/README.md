# AUR packaging for kAppIcon

| Package | Use when |
|---------|----------|
| **`kappicon`** | Stable release from GitHub tags |
| **`kappicon-git`** | Latest `main` (for testers / you) |

These files live in this git repo for maintenance. **Publishing** still happens on [aur.archlinux.org](https://aur.archlinux.org/) as separate package repositories.

## Local test (does not publish)

```bash
cd packaging/aur/kappicon
makepkg -si          # build + install
# or
makepkg -f && namcap PKGBUILD kappicon-*.pkg.tar.zst
```

```bash
cd packaging/aur/kappicon-git
makepkg -si
```

Regenerate `.SRCINFO` after editing a PKGBUILD:

```bash
makepkg --printsrcinfo > .SRCINFO
```

## Publish to the AUR (one-time setup)

1. Create an account at https://aur.archlinux.org/ and upload your **SSH public key**.
2. Install tools: `sudo pacman -S --needed base-devel git`
3. For each package:

```bash
# Stable
git clone ssh://aur@aur.archlinux.org/kappicon.git
cd kappicon
# copy PKGBUILD + .SRCINFO from this repo's packaging/aur/kappicon/
cp /path/to/kappicon/packaging/aur/kappicon/{PKGBUILD,.SRCINFO} .
git add PKGBUILD .SRCINFO
git commit -m "kappicon 3.1.0-1"
git push

# Git version
git clone ssh://aur@aur.archlinux.org/kappicon-git.git
cd kappicon-git
cp /path/to/kappicon/packaging/aur/kappicon-git/{PKGBUILD,.SRCINFO} .
# refresh pkgver/SRCINFO from a real build:
makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "kappicon-git: initial import"
git push
```

First push creates the AUR package if the name is free.

## After a new upstream release

1. Bump `pkgver` / `pkgrel` in `packaging/aur/kappicon/PKGBUILD`
2. Update `sha256sums` for the new `vX.Y.Z` tarball:
   ```bash
   curl -sL -o /tmp/t.tgz "https://github.com/rayman1972/kappicon/archive/refs/tags/vX.Y.Z.tar.gz"
   sha256sum /tmp/t.tgz
   ```
3. `makepkg --printsrcinfo > .SRCINFO`
4. Copy into the AUR clone and push

## Install (once published)

```bash
# helper: yay / paru / etc.
yay -S kappicon
# or
paru -S kappicon-git
```
