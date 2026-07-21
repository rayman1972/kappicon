# Architecture

**Analysis Date:** 2026-07-21

## Pattern Overview

**Overall:** Dual-entry desktop utility implemented as monolithic executable scripts with shared file-system contracts.

**Key Characteristics:**
- `gui/kappicon` is a Bash launcher containing a large embedded PyQt6 application and a retained legacy shell apply path.
- `cli/kappicon-cli` is an interactive Bash workflow with small embedded Python helpers for safe file/config operations.
- GUI and CLI interoperate through XDG paths, QSettings-compatible configuration, a common lock file, freedesktop launchers, and user hicolor assets rather than through an internal package API.
- State is local and file-based; there is no daemon, database, or service process.

## Layers

**Shell bootstrap and environment layer:**
- Purpose: Resolve XDG paths, discover desktop files, choose external commands, and launch the application mode.
- Contains: Top-level Bash in `gui/kappicon`, `cli/kappicon-cli`, and `install.sh`.
- Depends on: Linux shell utilities and environment variables.
- Used by: Both user entry points and installation/update flows.

**GUI presentation layer:**
- Purpose: Map icons, create/edit images, configure behavior, inspect overrides, and identify missing icons.
- Contains: `PixelCanvas`, `ImportPositionView`, `ImportPositionDialog`, and `CombinedWindow` in embedded Python within `gui/kappicon`.
- Depends on: PyQt6, discovery helpers, and the in-process mutation engine.
- Used by: `kappicon` desktop/command entry point.

**Mutation and safety layer:**
- Purpose: Validate desktop ids, serialize applies, back up launchers, perform atomic writes, install icons, reset/undo, and prune unused assets.
- Contains: Python functions such as `apply_lock`, `prepare_icon_value`, and `apply_icon_to_desktop` plus corresponding shell functions in both executables.
- Depends on: XDG paths, file system, ImageMagick/libicns, and cache refresh utilities.
- Used by: GUI Apply/Reset/Undo/Restore and CLI mapping/restore.

**Discovery and resolution layer:**
- Purpose: Find launchers, parse visible apps, resolve current/system icons, discover icon themes, and locate missing/overridden entries.
- Contains: `get_desktop_dirs` in shell and Python helpers including `discover_icon_themes`, `scan_theme_icons`, `resolve_icon`, `scan_user_launcher_overrides`, and `scan_apps_missing_icons` in `gui/kappicon`.
- Depends on: XDG, Flatpak, Snap, Qt icon resolution, and local file trees.
- Used by: Map, Overrides, Missing, and CLI pickers.

**Distribution layer:**
- Purpose: Install/update binaries and publish desktop/software-center metadata.
- Contains: `install.sh`, `gui/kappicon.desktop`, AppStream XML under `data/`, and AUR files under `packaging/aur/`.
- Depends on: GitHub/raw downloads for self-update or Arch makepkg for packages.

## Data Flow

**GUI icon apply:**
1. Bash resolves XDG/user directories and exports discovered desktop-entry paths from `gui/kappicon`.
2. Embedded Python builds `app_data`, starts `QApplication`, and creates `CombinedWindow`.
3. The user selects a file, an existing theme name, or an installed theme-pack icon plus one or more target applications.
4. `_apply_icon_specs` acquires `apply_lock`, snapshots/backups launcher state, and calls `apply_icon_to_desktop` for each app.
5. Custom files become content-addressed hicolor assets; theme selections remain freedesktop icon names.
6. The user `.desktop` override is atomically copied/rewritten, unused managed assets are pruned, caches are refreshed, and undo/session state is updated.

**CLI icon apply:**
1. `cli/kappicon-cli` loads the shared source-folder and backup settings.
2. `fzf` selects an image and desktop entry.
3. The script validates basenames, hashes the source/desktop id, acquires the shared lock, and converts/installs the asset.
4. It copies the source launcher to the user applications directory when needed, atomically changes `Icon=`, and refreshes caches.

**State Management:**
- Durable settings: QSettings INI file.
- Durable user content: icon library, backups, rendered/hicolor icons, and `.desktop` overrides.
- Ephemeral GUI state: selections, canvas history, session apply undo stack, timers, and theme icon cache.
- Coordination: `$XDG_DATA_HOME/kappicon/apply.lock`.

## Key Abstractions

**Desktop id and launcher override:**
- Purpose: Identify a freedesktop application safely and layer user customization over a system launcher.
- Examples: `is_valid_desktop_id`, `find_system_desktop_path`, `user_override_only_differs_by_icon` in `gui/kappicon`.
- Pattern: Validated basename plus copy-on-write user override.

**Icon specification:**
- Purpose: Represent either a file path or `theme:<name>` without conflating file and theme behavior.
- Examples: `THEME_ICON_PREFIX`, `prepare_icon_value`, `_current_icon_spec` in `gui/kappicon`.
- Pattern: Tagged string at the UI/business boundary.

**Content-addressed managed icon:**
- Purpose: Avoid collisions and preserve old assets for undo/backups.
- Examples: `kappicon_theme_name` in `gui/kappicon` and matching SHA construction in `cli/kappicon-cli`.
- Pattern: Human label + desktop-id hash + content/shape hash.

**Atomic mutation:**
- Purpose: Prevent partial launcher/config/icon files.
- Examples: `_atomic_write_text`, `_atomic_copy_file`, sibling `mktemp` + `os.replace`, and `atomic_replace`.
- Pattern: Stage in destination filesystem, then rename.

## Entry Points

**GUI:**
- Location: `gui/kappicon`.
- Triggers: `kappicon` command or `gui/kappicon.desktop` (`Exec=kappicon`).
- Responsibilities: Environment bootstrap, desktop discovery, PyQt6 application, current in-process mutation workflow, legacy fallback.

**CLI:**
- Location: `cli/kappicon-cli`.
- Triggers: `kappicon-cli` with no flag or `--settings`, `--restore`, `--refresh`, `--help`.
- Responsibilities: Terminal selection, mutation/restore, settings, cache refresh.

**Installer:**
- Location: `install.sh`.
- Triggers: direct execution, optionally `--update` or `--install-deps`.
- Responsibilities: User-level install/update, dependency guidance, metadata installation, legacy-file cleanup.

## Error Handling

**Strategy:** Fail fast at mutation boundaries, surface actionable user messages, and treat optional cache/notification integrations as best effort.

**Patterns:**
- GUI Python raises `ApplyError` for expected user-visible failures and catches around UI actions.
- Shell paths use exit statuses, guard clauses, stderr, and explicit cleanup traps.
- Backup-enabled mutations fail closed if backup creation fails.
- Cache refresh failures are generally ignored after the primary mutation succeeds.

## Cross-Cutting Concerns

**Validation:** Safe desktop basenames, control-character rejection, realpath containment checks, supported extensions, and strict managed-icon naming.

**Concurrency:** Python `fcntl.flock` and shell `flock` target the same apply lock; GUI busy guards prevent UI re-entry.

**File integrity:** Atomic replacement, destination-side staging, content-addressed assets, and backup/undo retention.

**Compatibility:** XDG paths, localized user directories, multiple desktop cache tools, Flatpak host execution, Snap/Flatpak launcher discovery, and ImageMagick command fallback.

---
*Architecture analysis: 2026-07-21*
*Update when executable boundaries or mutation ownership change*
