# Testing Patterns

**Analysis Date:** 2026-07-21

## Test Framework

**Runner:**
- None committed.
- No `tests/` directory, test configuration, package manifest, test dependency, or `.github/workflows/` CI pipeline exists.

**Assertion Library:**
- None.

**Current verification commands:**
```bash
bash -n gui/kappicon
bash -n cli/kappicon-cli
bash -n install.sh
desktop-file-validate gui/kappicon.desktop
appstreamcli validate --no-net data/io.github.rayman1972.kappicon.metainfo.xml
xmllint --noout data/io.github.rayman1972.kappicon.metainfo.xml
kappicon-cli --help
```

**Embedded Python syntax check:**
- The Python between the `PYEOF` heredoc markers in `gui/kappicon` can be extracted to stdout and passed to Python `compile()` without launching the GUI.
- This check passed during the 2026-07-21 mapping run.

## Test File Organization

**Location and naming:**
- No established pattern because no automated tests are tracked.
- `CONTRIBUTING.md` describes manual checks rather than executable suites.

**Recommended initial structure:**
```text
tests/
├── unit/          # Pure desktop parsing, validation, hashing, and config behavior
├── integration/   # XDG sandbox filesystem and external-tool adapter checks
├── fixtures/      # Representative .desktop, icon, backup, and theme trees
└── smoke/         # CLI flags, installer dry paths, and optional Qt offscreen startup
```

## Existing Manual Testing

`CONTRIBUTING.md` asks contributors to exercise:
- GUI Map from a file, another app, and an icon theme.
- Create save behavior and Settings.
- `kappicon-cli --help` and a simple apply when apply logic changes.
- Packaging/docs updates when paths or features change.

There is no documented repeatable matrix for batch apply, undo, reset, restore, missing-icon detection, Flatpak host behavior, or multi-desktop cache refresh.

## Mocking and Isolation

**Current:**
- No mock framework or fixtures.

**Required for safe automation:**
- Override `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_BIN_HOME`, `USER_APPS_DIR`, `USER_ICONS_DIR`, `DATA_DIR`, and `TARGET_DIR` to temporary fixture trees.
- Stub external commands by prepending a controlled bin directory to `PATH` (`magick`, `icns2png`, cache tools, `fzf`, notifications).
- Never point automated mutation tests at the developer's real home XDG directories.
- Use `QT_QPA_PLATFORM=offscreen` for GUI construction tests where supported.

## Fixtures and Factories

High-value fixture cases:
- System and user `.desktop` files with `[Desktop Action ...]` sections and multiple `Icon=` placements.
- Invalid desktop ids, symlink escapes, unreadable files, duplicate names, and user-only launchers.
- PNG/SVG/ICNS inputs and icon themes with symlink cycles, symbolic variants, and multiple sizes.
- Backup filenames containing `.backup.` inside the desktop id.
- Concurrent CLI/GUI apply attempts sharing one lock.

## Coverage

**Requirements:**
- No coverage target or report exists.
- The highest-risk uncovered code is launcher mutation/reset/restore and managed-asset pruning in `gui/kappicon` and `cli/kappicon-cli`.

**Suggested first target:**
- Establish regression coverage for pure parsing/hash/normalization helpers and sandboxed mutation flows before choosing a percentage gate.

## Test Types

**Unit tests:**
- Desktop-entry parsing and normalization.
- Desktop-id/backup-name validation.
- Content-addressed name determinism and collision resistance.
- Theme discovery scoring and missing/override classification.

**Integration tests:**
- Apply/reset/undo/restore against temporary XDG trees.
- Atomic-write behavior on failure.
- Lock contention between two processes.
- Image conversion adapters using minimal fixtures or stub commands.

**E2E tests:**
- Optional PyQt6 offscreen startup and tab construction.
- Manual desktop-session smoke tests remain necessary for KDE/GTK cache visibility.

## Mapping-Run Results

- Bash syntax: passed for `gui/kappicon`, `cli/kappicon-cli`, and `install.sh`.
- Embedded GUI Python syntax: passed.
- AppStream XML: validation passed.
- Desktop entry: valid, with non-fatal category hints about multiple main categories and possible `Settings` extension.
- CLI help: passed with isolated XDG directories.

---
*Testing analysis: 2026-07-21*
*Update when the first automated suite or CI workflow is added*
