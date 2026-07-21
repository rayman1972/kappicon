# Codebase Structure

**Analysis Date:** 2026-07-21

## Directory Layout

```text
macosicons-linux/
├── assets/                 # Product artwork used by docs and installation
├── cli/
│   └── kappicon-cli        # Bash terminal application
├── data/
│   └── *.metainfo.xml      # AppStream software-center metadata
├── docs/
│   └── PROJECT.md          # Ignored internal product notes, not public source tracking
├── gui/
│   ├── kappicon            # Bash wrapper + embedded PyQt6 GUI + apply engines
│   └── kappicon.desktop    # Desktop launcher
├── packaging/aur/
│   ├── kappicon/           # Stable AUR PKGBUILD and .SRCINFO
│   └── kappicon-git/       # VCS AUR PKGBUILD and .SRCINFO
├── screenshots/            # README/AppStream product screenshots
├── .github/                # Issue and pull-request templates; no CI workflows
├── install.sh              # XDG-aware user installer/updater
├── README.md               # User-facing product and usage documentation
├── CONTRIBUTING.md         # Development and manual verification guidance
├── SECURITY.md             # Security support/reporting policy
└── VERSION                 # Current release version
```

## Directory Purposes

**`gui/`:**
- Purpose: Graphical application and menu entry.
- Contains: One 6,359-line executable combining Bash and embedded Python, plus one desktop-entry file.
- Key files: `gui/kappicon`, `gui/kappicon.desktop`.
- Internal organization: Section comments and functions/classes substitute for modules.

**`cli/`:**
- Purpose: Terminal icon mapper and maintenance commands.
- Contains: `cli/kappicon-cli`, an 856-line Bash executable with embedded Python helpers.
- Key flows: help/settings/restore/refresh flags, then interactive `fzf` mapping.

**`packaging/aur/`:**
- Purpose: Arch Linux stable and latest-git packaging.
- Tracked files: `PKGBUILD` and `.SRCINFO` for each package.
- Generated `src/`, `pkg/`, archives, cloned sources, and package files may exist locally but are ignored by `.gitignore` and are not source of truth.

**`data/` and `assets/`:**
- Purpose: AppStream metadata and installed/displayed artwork.
- Key files: `data/io.github.rayman1972.kappicon.metainfo.xml`, `assets/kappicon.png`.

**`screenshots/`:**
- Purpose: Product documentation for Map, Create, Settings, Overrides, and Missing workflows.
- Consumers: `README.md` and remote AppStream screenshot URLs.

**`.github/`:**
- Purpose: Contribution intake templates.
- Contains: issue forms and pull-request template only.
- Missing: `.github/workflows/` automated checks.

## Key File Locations

**Entry Points:**
- `gui/kappicon` — GUI runtime and current in-process apply engine.
- `cli/kappicon-cli` — terminal runtime.
- `install.sh` — installer and updater.

**Configuration and metadata:**
- `VERSION` — release marker.
- `.gitignore` — excludes AUR/Flatpak build artifacts and `docs/PROJECT.md`.
- `gui/kappicon.desktop` — desktop menu integration.
- `data/io.github.rayman1972.kappicon.metainfo.xml` — AppStream component/releases.
- `packaging/aur/*/PKGBUILD` and `.SRCINFO` — Arch package definitions.

**Core Logic:**
- `gui/kappicon:354` onward — embedded Python imports, constants, services, widgets, and main window.
- `gui/kappicon:1033` — primary Python apply/reset function.
- `gui/kappicon:2770` — `CombinedWindow` UI coordinator.
- `gui/kappicon:5850` onward — application startup and legacy shell fallback.
- `cli/kappicon-cli:380` onward — flag routing and interactive workflow.

**Testing:**
- No test directory, test configuration, fixtures, or CI files exist.
- Manual test expectations are documented in `CONTRIBUTING.md`.

**Documentation:**
- `README.md` — product behavior, dependencies, installation, usage, paths, and design summary.
- `CONTRIBUTING.md` — layout, contribution rules, and safety-sensitive areas.
- `SECURITY.md` — supported versions and private reporting routes.
- `docs/PROJECT.md` — ignored internal feature/guardrail notes still present in this workspace.

## Naming Conventions

**Files:**
- Executable product commands use extensionless kebab-case names: `kappicon`, `kappicon-cli`.
- Repository-level policy/docs use uppercase conventional names: `README.md`, `SECURITY.md`, `VERSION`.
- Distribution files follow platform conventions: `PKGBUILD`, `.SRCINFO`, `.desktop`, `.metainfo.xml`.

**Directories:**
- Lowercase functional groupings: `gui/`, `cli/`, `data/`, `assets/`, `screenshots/`, `packaging/`.
- Packaging nests by ecosystem and package name: `packaging/aur/kappicon[-git]/`.

## Where to Add New Code

**GUI feature:**
- Current convention: add helpers/classes/methods within embedded Python in `gui/kappicon` and connect them from `CombinedWindow`.
- Safer future direction: extract independently testable Python modules before adding another large subsystem; see `CONCERNS.md`.

**CLI feature:**
- Add a shell helper and route it in the flag `case` or interactive flow in `cli/kappicon-cli`.
- Keep mutation semantics aligned with the GUI apply engine.

**Desktop/distribution integration:**
- Update `gui/kappicon.desktop`, AppStream XML under `data/`, `README.md`, and both AUR package definitions as applicable.

**Tests:**
- No established location. Introduce `tests/` with separate shell/unit/integration fixtures rather than embedding tests in product scripts.

## Special Directories

**`packaging/aur/*/{src,pkg}` and package archives:**
- Purpose: Local makepkg output.
- Source: Generated from PKGBUILD.
- Committed: No; excluded by `.gitignore`.

**`.planning/codebase/`:**
- Purpose: Generated GSD reference map of the current repository.
- Source: This analysis.
- Committed: Yes when planning-doc tracking is enabled.

---
*Structure analysis: 2026-07-21*
*Update when source is split into modules or new packaging targets are added*
