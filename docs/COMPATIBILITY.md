# Multi-distro non-GUI compatibility checks

Lightweight recipe for maintainers to run **headless** regression checks on or
for more than one Linux family. No display, no GUI E2E, no mandatory CI matrix.

## Primary checklist (any host with a checkout)

```bash
./scripts/validate.sh
python3 -m unittest discover -s tests -v
```

Optional local performance investigation (not required for compatibility):

```bash
KAPPICON_TIMING=1 kappicon   # stderr timing lines; see CONTRIBUTING.md
```

## Minimum environments

Aim to run the primary checklist on at least:

| Family | Example host / image | Notes |
|--------|----------------------|--------|
| **Arch** | Arch / CachyOS host, or `archlinux:latest` | Packages: `python`, `bash`; optional `desktop-file-utils` for `desktop-file-validate` |
| **Debian/Ubuntu** | Debian bookworm / Ubuntu LTS, or container | Packages: `python3`, `bash`; optional `desktop-file-utils` |

Validate’s hard checks do **not** require PyQt6 or ImageMagick. Soft skips apply
when optional tools (`desktop-file-utils`, `appstreamcli`) are missing.

## Optional container recipes

Use **podman** or **docker**. Network is only needed to install packages inside
the container; the checks themselves are offline.

### Arch

```bash
podman run --rm -v "$PWD":/src:Z -w /src archlinux:latest \
  bash -lc 'pacman -Syu --noconfirm python bash desktop-file-utils && ./scripts/validate.sh && python -m unittest discover -s tests -v'
```

### Debian / Ubuntu

```bash
podman run --rm -v "$PWD":/src:Z -w /src debian:bookworm \
  bash -lc 'apt-get update && apt-get install -y python3 bash desktop-file-utils && ./scripts/validate.sh && python3 -m unittest discover -s tests -v'
```

(`docker run` works the same way if you prefer Docker.)

## Out of scope here

- Full GUI under Xvfb / nested compositor CI
- Fedora / openSUSE as required matrices (optional later)
- Committing container images or mandatory GitHub Actions workflows

For development layout and release checksums, see [CONTRIBUTING.md](../CONTRIBUTING.md).
