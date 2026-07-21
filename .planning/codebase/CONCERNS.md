# Codebase Concerns

**Analysis Date:** 2026-07-21

## Tech Debt

**Monolithic GUI executable:**
- Issue: `gui/kappicon` is 6,359 lines and embeds most of a PyQt6 application in one Bash heredoc.
- Impact: UI, discovery, image processing, launcher mutation, and lifecycle changes share one file and cannot be imported normally for tests.
- Fix approach: Extract Python into a package with modules for desktop parsing, icon assets, mutation service, discovery, and Qt views; retain a thin executable wrapper.

**Duplicated mutation implementations:**
- Issue: Desktop validation, locking, atomic writes, backup/restore, content hashing, hicolor install, and cache refresh are implemented in the GUI's Python engine, the GUI's legacy shell fallback, and `cli/kappicon-cli`.
- Files: `gui/kappicon`, `cli/kappicon-cli`.
- Impact: A safety or semantic fix can land in one path while the others drift; the outer GUI fallback is normally unreachable but remains substantial maintenance surface.
- Fix approach: Move mutation logic into one Python library/command API consumed by GUI and CLI, then retire the legacy close-to-apply path.

**No dependency manifest:**
- Issue: Runtime dependencies are documented and installed by distro-specific shell logic, but versions are not machine-declared or locked.
- Files: `README.md`, `install.sh`, `packaging/aur/*/PKGBUILD`.
- Impact: PyQt6/ImageMagick behavior can vary by distribution and upgrades without a repeatable development environment.
- Fix approach: Document minimum tested versions and add a development/validation manifest without undermining distro packaging.

## Known Bugs

- No reproducible functional bug was confirmed during the static mapping pass.
- `desktop-file-validate` reports non-fatal hints that `gui/kappicon.desktop` has multiple main categories and could extend `DesktopSettings` with `Settings`; validation still succeeds.

## Security Considerations

**Shell lock is optional:**
- Risk: `acquire_apply_lock` in `cli/kappicon-cli` and the legacy shell section of `gui/kappicon` silently proceeds when the `flock` executable is absent.
- Current mitigation: Typical util-linux systems provide `flock`; the current in-process GUI engine uses Python `fcntl.flock` directly.
- Recommendation: Treat missing `flock` as a hard error for shell mutation paths or replace them with the shared Python lock implementation.

**Self-update trust boundary:**
- Risk: Non-git `install.sh --update` downloads executable files from the GitHub `main` raw URLs and installs them without a pinned release checksum or signature.
- Current mitigation: HTTPS/GitHub transport and a user-level default install reduce scope; stable AUR packaging uses a SHA-256 source checksum.
- Recommendation: Fetch a tagged release/archive and verify a published checksum before replacing executables.

**User launcher mutations:**
- Risk: A defect can hide or corrupt application launchers even without root.
- Current mitigation: validated basenames, user-only destinations, atomic writes, optional fail-closed backups, exclusive locks, safe reset comparison, and session undo.
- Recommendation: Add sandboxed regression tests for every mutation and restore path before refactoring.

## Performance Bottlenecks

**Synchronous startup discovery:**
- Problem: GUI startup enumerates desktop files before Python launch and `CombinedWindow.__init__` calls `discover_icon_themes` on the UI thread; theme detection can recursively inspect directories.
- Files: `gui/kappicon` around desktop discovery, `discover_icon_themes`, and `CombinedWindow.__init__`.
- Measurement: Not benchmarked in this pass.
- Improvement path: Add timing instrumentation, cache discovery metadata, and move large scans to cancellable worker tasks if startup is measurably slow.

**Theme icon scanning:**
- Problem: Selecting a theme can walk its tree with symlink following and file scoring.
- Current mitigation: visited-realpath cycle detection and per-theme result caching in `_theme_icons_cache`.
- Improvement path: Incremental/background scanning and cache invalidation keyed to theme modification time.

## Fragile Areas

**Desktop reset/restore semantics:**
- Why fragile: Reset must distinguish a pure icon override from a user launcher containing unrelated edits or desktop actions.
- Files: `gui/kappicon` functions `_normalized_desktop_without_main_icon`, `user_override_only_differs_by_icon`, and `apply_icon_to_desktop`; restore logic also exists in `cli/kappicon-cli`.
- Safe modification: Preserve full-file comparison and test representative multi-section desktop files.
- Test coverage: None automated.

**Managed icon garbage collection:**
- Why fragile: Pruning must retain assets referenced by live launchers, backups, and the session undo stack while an apply lock is held.
- Files: `gui/kappicon` functions `collect_referenced_kappicon_names`, `prune_unreferenced_kappicon_assets`, and `undo_keep_icon_names`.
- Safe modification: Treat reference discovery, lock ownership, and content-addressed names as one invariant; add fixture-based tests.
- Test coverage: None automated.

**Shell/Python heredoc boundary:**
- Why fragile: Quoting, heredoc markers, environment exports, and exit/result parsing couple two languages inside `gui/kappicon`.
- Common failures: A shell edit can break Python extraction or a Python output can be interpreted by the legacy protocol.
- Safe modification: Run both `bash -n` and embedded Python compilation; prefer extracting modules rather than adding more boundary logic.
- Test coverage: Syntax checks only.

## Scaling Limits

**Repository maintainability:**
- Current size: 7,550 executable lines across `gui/kappicon`, `cli/kappicon-cli`, and `install.sh`; almost 300 KB of source concentrated in scripts.
- Limit: Changes increasingly require whole-file reasoning and manual cross-path verification.
- Scaling path: Modularize shared core logic and establish automated tests before expanding workflows.

**Desktop/theme inventory:**
- Current capacity: Unbounded local launcher/theme enumeration; no published benchmark.
- Limit: Very large icon-theme installations may increase startup or theme-switch latency.
- Scaling path: Measure, cache, and background scans.

## Dependencies at Risk

**External command variability:**
- Risk: ImageMagick exposes both `magick` and legacy `convert`; KDE ships versioned cache tools; libicns package/command names vary by distro.
- Impact: Feature availability and output may differ across supported distributions.
- Mitigation: Runtime detection and distro mappings already exist in `install.sh`.
- Recommendation: Add a CI/manual compatibility matrix with at least Arch, Debian/Ubuntu, Fedora, and openSUSE containers where GUI-independent checks can run.

## Missing Critical Features

**Automated safety regression suite:**
- Problem: The project edits user launcher state but relies on manual testing.
- Current workaround: Defensive implementation and contribution checklist.
- Blocks: Confident refactoring of duplicated mutation paths and broad compatibility changes.
- Implementation complexity: Medium; environment overrides already make temporary XDG isolation feasible.

**Continuous validation:**
- Problem: Metadata/version/syntax drift is only caught locally or during packaging.
- Current workaround: Maintainer release discipline and AUR metadata commits.
- Blocks: Fast feedback on pull requests.
- Implementation complexity: Low for syntax and metadata checks; GUI behavior remains a separate concern.

## Test Coverage Gaps

**Apply/reset/undo/restore:**
- What's not tested: Atomic writes, backups, user-only launchers, action preservation, lock contention, and failure rollback.
- Risk: User-level launcher loss or incorrect icon state.
- Priority: High.

**Icon processing and pruning:**
- What's not tested: Format branches, shape output, hicolor size installation, content hashes, backup/undo retention, and garbage collection.
- Risk: Missing icons, stale assets, or broken undo.
- Priority: High.

**Discovery/UI classification:**
- What's not tested: Desktop visibility rules, overrides, missing icons, Flatpak/Snap roots, theme symlinks, and recents/session restoration.
- Risk: Apps disappear, duplicate, or receive incorrect status.
- Priority: Medium.

---
*Concerns audit: 2026-07-21*
*Update as duplication is removed, tests land, or new platform evidence appears*
