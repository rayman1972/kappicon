# Coding Conventions

**Analysis Date:** 2026-07-21

## Naming Patterns

**Files:**
- Extensionless executable names are kebab-case (`gui/kappicon`, `cli/kappicon-cli`).
- Platform-standard names are preserved (`PKGBUILD`, `.SRCINFO`, `.desktop`, `.metainfo.xml`).
- There is no existing test-file naming convention.

**Functions and methods:**
- Bash and Python functions use `snake_case`: `xdg_user_dir`, `backup_desktop_file`, `prepare_icon_value`.
- Python Qt event methods use framework names (`paintEvent`, `mousePressEvent`, `closeEvent`).
- GUI callbacks commonly use `_on_*`, `_refresh_*`, `_editor_*`, `_overrides_*`, and `_missing_*` prefixes.
- Internal Python helpers are prefixed with `_`; public conceptual operations such as `apply_icon_to_desktop` are not.

**Variables:**
- Bash globals/constants use `UPPER_SNAKE_CASE`; function locals are lower snake case and declared with `local`.
- Python module constants use `UPPER_SNAKE_CASE`; locals and attributes use snake case.
- Boolean state is explicit (`_apply_busy`, `BACKUP_ENABLED`) rather than encoded in ambiguous values.

**Types:**
- Python classes use PascalCase (`ApplyError`, `PixelCanvas`, `CombinedWindow`).
- Type hints appear selectively on Qt/image-facing methods, not comprehensively.

## Code Style

**Bash formatting:**
- Four-space indentation, quoted variable expansions, guard clauses, and `case` for flags/validated enums.
- Functions use `name() { ... }`; grouped section comments use Unicode box lines for navigation.
- Pipelines and external commands often suppress expected discovery/cache errors with `2>/dev/null` and `|| true`.

**Python formatting:**
- Four-space indentation and generally PEP 8-style snake_case/PascalCase.
- Long Qt constructor/configuration blocks are formatted manually; no formatter configuration exists.
- Imports are grouped at the embedded-program boundary, though several imports are combined on single lines.

**Linting/formatting tools:**
- No ShellCheck, Ruff, Black, formatter config, or lint command is committed.
- `shellcheck` was not installed in the analyzed environment.

## Import Organization

**Embedded GUI Python:**
1. Python standard-library imports.
2. PyQt6 widget, GUI, and core imports grouped by Qt module.
3. No internal module imports because all code lives in the heredoc.

**Path aliases/modules:**
- None. The source has no importable project package.

## Error Handling

**Expected failures:**
- GUI Python raises `ApplyError` with user-facing context for invalid selections, missing tools, failed backups, and unsafe reset/apply states.
- UI handlers catch `ApplyError` separately from unexpected exceptions and restore busy state in controlled paths.
- Bash uses status checks and immediate `exit 1` for mutation failures.

**Best-effort operations:**
- Desktop cache refresh and optional notification tools do not invalidate a completed primary mutation.
- Discovery code catches `OSError` and continues when a theme, launcher, or cache path is unreadable.

**Cleanup:**
- Temporary directories are removed in `finally` blocks or shell traps.
- Shell recursive cleanup is guarded by `is_temp_path` before `rm -rf`.

## Logging and User Feedback

- No logging framework or persistent log file.
- GUI uses message boxes, status-bar text, inline labels, and timers that clear transient status.
- CLI/installer use stdout/stderr with concise status markers.
- Errors should state the failed operation and a concrete dependency/path when known.

## Comments

**Observed practice:**
- Section banners divide large scripts by responsibility.
- Comments explain safety invariants and rationale, especially around desktop ids, atomic writes, reset behavior, locks, and content-addressed assets.
- Docstrings are used for non-obvious Python helpers and abstractions.
- No TODO/FIXME convention or issue-linked TODOs were found.

## Function Design

**Current pattern:**
- Small safety/file helpers are preferred for atomic operations and validation.
- GUI assembly methods and workflow methods can be long because the entire application is one embedded module.
- Functions return early on invalid or no-op states.
- Multi-option Python operations use keyword-only arguments where ambiguity matters, for example `apply_icon_to_desktop(..., shape=..., backup=...)`.

**Prescriptive guidance for changes:**
- Reuse existing validation, lock, atomic-write, and cache-refresh helpers rather than adding a new mutation path.
- Keep desktop-system reads separate from user-level writes.
- Preserve `theme:<name>` versus file-path semantics and the matching GUI/CLI content-addressed naming contract.
- Avoid extending the legacy shell fallback unless compatibility specifically requires it.

## Module Design

- There are no project modules, exports, or barrel files.
- Conceptual namespaces are expressed through prefixes and class ownership inside `gui/kappicon`.
- When extracting modules, keep pure parsing/hashing, filesystem mutation, Qt UI, and external command adapters separate to make testing possible.

---
*Convention analysis: 2026-07-21*
*Update when formatting/linting or module boundaries are introduced*
