# Contributing to kAppIcon

Thanks for helping improve kAppIcon. This project is intentionally small:
**user-level** Linux launcher icon management (GUI + CLI).

## Ways to contribute

* **Bug reports** — use the bug issue template; include distro, desktop, and steps
* **Feature ideas** — describe the use case, not only the implementation
* **Pull requests** — fixes, packaging, docs, and tests are all welcome
* **Packaging feedback** — AUR (`kappicon` / `kappicon-git`) and install script

## Development setup

```bash
git clone https://github.com/rayman1972/kappicon.git
cd kappicon
./install.sh          # or: yay -S kappicon-git
kappicon              # GUI
kappicon-cli --help   # CLI
```

Requirements and **minimum tested versions** are listed in the
[README](README.md#requirements) (Python ≥ 3.9, distro PyQt6, ImageMagick,
icns tooling, fzf, util-linux `flock`). Prefer distro packages over pip-only
installs; AUR + `install.sh` remain first-class.

### Layout

| Path | Role |
|------|------|
| `gui/kappicon` | Thin bash launcher (`python3 -m kappicon`) |
| `python/kappicon/` | Shared Python package (mutation + GUI) |
| `cli/kappicon-cli` | Terminal mapper (`fzf`) |
| `install.sh` | User install (XDG-aware; installs package under `$DATA_DIR/python`) |
| `data/*.metainfo.xml` | AppStream metadata |
| `packaging/aur/` | AUR package sources (`PKGBUILD`, `.SRCINFO` only) |
| `tests/` | Headless mutation/core tests (temp XDG; no display) |
| `scripts/validate.sh` | Syntax/metadata + package compile checks |

### Automated tests

Mutation and core engine tests run without a display and without your real home
directory. They import `python/kappicon` under temporary XDG (no Bash heredoc
extract). PyQt6 is not required for mutation tests.

```bash
python3 -m unittest discover -s tests -v
```

Optional continuous validation (shell syntax, embedded Python `compile()`,
version/metadata, `desktop-file-validate` when installed):

```bash
./scripts/validate.sh
```

Mutation/core tests need **Python 3** + stdlib only (PyQt6 is stubbed). Full GUI
needs distro **PyQt6**. CLI/shell apply paths need **`flock`** (util-linux).

Both commands are the continuous validation entry points for local/CI use:

```bash
./scripts/validate.sh && python3 -m unittest discover -s tests -v
```

Multi-distro non-GUI checks (Arch + Debian/Ubuntu, optional containers): see
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

### Performance timing

Opt-in measurement for startup and theme discovery (no change when unset):

```bash
KAPPICON_TIMING=1 kappicon
# or from a checkout:
KAPPICON_TIMING=1 ./gui/kappicon
```

Logs go to **stderr** as lines like `kappicon timing: <label>: <ms> ms`.
Typical labels:

- `shell.desktop_list_find` — bash desktop-file discovery (if timed)
- `python.main` / `python.run_app` / `startup.build_icon_files`
- `discover_icon_themes` — installed theme pack discovery at window init
- `scan_theme_icons:<name>` — first scan of a theme pack (or after mtime change)

Use this when investigating sluggish startup or Map theme browsing. It is not
required for `./scripts/validate.sh` or the unit test suite.

## Release checksums

Non-git `./install.sh --update` installs only from a **tagged** GitHub source
archive after verifying a published **`SHA256SUMS`** asset. Empty release assets
⇒ non-git update **fails closed** by design.

When cutting a release:

1. Set `VERSION` / AppStream release to `X.Y.Z` and tag `vX.Y.Z`.
2. Create the GitHub release for that tag (GitHub generates the source archive).
3. Download the source tarball and save it as `kappicon-X.Y.Z.tar.gz`:
   ```bash
   curl -sfL -o kappicon-X.Y.Z.tar.gz \
     "https://github.com/rayman1972/kappicon/archive/refs/tags/vX.Y.Z.tar.gz"
   ```
4. Generate checksums:
   ```bash
   sha256sum kappicon-X.Y.Z.tar.gz > SHA256SUMS
   ```
5. **Upload `SHA256SUMS` as a release asset** on that GitHub release (required for non-git update).
6. Keep AUR `packaging/aur/kappicon/PKGBUILD` `sha256sums` in sync with the same archive when bumping the stable package.

## Pull requests

1. Fork and branch from `main`
2. Keep changes focused — one concern per PR when possible
3. Match existing style (shell + embedded Python; prefer clear over clever)
4. Test on your machine:
   - GUI: Map (file / other app / icon theme), Create save, Settings
   - CLI: `kappicon-cli --help` and a simple apply if you touch apply logic
5. Update README or packaging notes if install paths or features change
6. Do **not** commit build artifacts (`packaging/aur/*/pkg`, etc.)

### Safety-sensitive areas

Apply/restore paths touch user `.desktop` files. Prefer:

* Atomic writes (temp + replace)
* Validated desktop ids (no path traversal)
* The existing apply lock when mutating shared state

## Code of conduct

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Contributions are accepted under the project [MIT License](LICENSE), including
attribution to the original macosicons-linux lineage described in the README.
