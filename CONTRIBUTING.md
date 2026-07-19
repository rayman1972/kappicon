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

Requirements are listed in the [README](README.md#requirements).

### Layout

| Path | Role |
|------|------|
| `gui/kappicon` | GUI (bash + embedded PyQt6) |
| `cli/kappicon-cli` | Terminal mapper (`fzf`) |
| `install.sh` | User install (XDG-aware) |
| `data/*.metainfo.xml` | AppStream metadata |
| `packaging/aur/` | AUR PKGBUILDs |

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
