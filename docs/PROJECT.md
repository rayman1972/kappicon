# kAppIcon — high-status project list

Guiding principles (Nate Graham / KDE HIG spirit):

- **Stay proud**: user-level only, atomic writes, apply lock, no surprise bulk changes.
- **Identity**: Map · Create · Settings · Overrides · Missing stay the spine; new power is progressive disclosure, not new “modes” that confuse.
- **Feel logical**: primary action stays **Apply**; multi-select and batch only appear when the user has selected more than one app.
- **No races**: one exclusive apply lock; UI busy-guards; cache refresh debounced after mutations complete.
- **Feedback**: never close the window just to apply an icon; the list updates immediately.

---

## 1. Live apply + instant feedback

**Why:** Closing the app after every Apply breaks the rice loop.

**How:** In-process apply engine (Python, same semantics as the shell path). Apply keeps the window open, updates the app-list icon, status bar, and Overrides when relevant. Cache refresh runs after the lock is released (debounced).

**HIG:** Primary button remains Apply; success is a status message, not a modal.

## 2. Session memory

**Why:** Ricing is dozens of small steps; re-picking source/theme/app is friction.

**How:** `QSettings` keys under `map/` — icon source, theme pack path, icon search, app search, icon size, last app id, last icon path/name. Restored after the lists are built (single-shot, no races with filters).

**HIG:** Silent restore; never override an explicit user choice mid-session.

## 3. Batch apply (multi-select apps)

**Why:** Theme-pass over several launchers without reopening.

**How:** Extended selection on the app list (Ctrl/Shift, standard). Apply label becomes “Apply to N apps” when N>1. Confirm for N>1. Same icon, sequential applies under one lock hold *per app* (still exclusive). One undo entry per app (stack).

**HIG:** Confirm bulk actions; default single-select mental model still works with a simple click.

## 4. Map discovery (comfortable icons + recents)

**Why:** Visual work needs larger previews.

**How:** Compact (32) / Comfortable (48) / Large (64) icon sizes for both lists (Settings-backed). “Recent” icons and apps remembered (capped lists in `QSettings`), pinned to the top of filters when relevant via recents ranking — not a separate cluttered pane.

**HIG:** Density control is familiar; recents are optional helpers, not a second workflow.

## 5. Ship documentation for shipped features

**Why:** Overrides/Missing already exist but README still under-describes them.

**How:** README feature table + usage bullets; no forced release/AUR bump without an explicit release request.

## 6. SVG / theme fidelity

**Why:** Rasterizing theme SVGs destroys rice quality.

**How:** Keep existing rule: *As designed* + SVG → install scalable hicolor (or use theme name for `theme:` sources). Shape masks still rasterize. Documented in status when applicable.

## 7. Undo last apply

**Why:** Mistakes mid-rice must be cheap.

**How:** Session undo stack (max 15) storing previous user `.desktop` bytes or “file did not exist”. Menu/button **Undo last apply** (Ctrl+Z on Map when editor not focused). Redoes not required for v1.

**HIG:** Edit → Undo pattern; disabled when stack empty.

## 8. Drag and drop

**Why:** Muscle memory for ricers.

**How:** Accept image URLs/files on Map icon list and Create canvas. Reject non-images cleanly. Drop does not auto-apply (choose app, then Apply) — no accidental writes.

**HIG:** Drop = select, not mutate system state.

## 9. Richer app filtering

**Why:** Find ugly launchers fast.

**How:** Lightweight filter row: All · Customized only (user override present). Text search unchanged. No heavy category ontology (fragile across DEs).

**HIG:** One obvious filter control; default All.

## 10. Missing: empty vs unresolved

**Why:** Different fix stories.

**How:** Combo or checkable filter: All problems · Empty Icon= only · Unresolved name only. Default All.

**HIG:** Same list, refined — not a second tab.

---

## Guardrails (all items)

| Guard | Mechanism |
|-------|-----------|
| Desktop id safety | `is_valid_desktop_id` |
| Exclusive mutation | `fcntl` flock on `$DATA_DIR/apply.lock` (Apply, Reset, Undo, Restore) |
| Atomic desktop write | temp + `os.replace` |
| Backup fail-closed | abort if backup enabled and fails |
| UI re-entry | `_apply_busy` disables Apply/Reset/batch |
| Cache refresh | after unlock; coalesced timer |
| Undo-safe assets | content-addressed `kappicon-<label>-<idhash>-<content>` hicolor names |
| ID collisions | desktop-id SHA in theme name (not lossy sanitize alone) |
| Ctrl+Z | Map apply undo only on Map tab; text fields get text undo; Create uses canvas |
| Reset | full-file compare (all groups); delete override only if solely Icon= differs; refuse user-only apps |
| Install | user-level by default; `--install-deps` required for package manager installs |
| Asset GC | prune unreferenced `kappicon-*` under `apply_lock`; keep launchers + backups + Undo |

## Out of scope (for pride / focus)

- Global theme switching
- Root/system installs
- Full icon-theme authoring
- Auto-apply on drop
- Flatpak / Flathub (host XDG integration is unreliable for this app class)
