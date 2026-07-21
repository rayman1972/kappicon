#!/usr/bin/env bash
# Continuous validation for kAppIcon (syntax, package compile, version, desktop).
# CI-friendly: no network, no GUI, no PyQt6 required for hard checks.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "==> Shell syntax (bash -n)"
bash -n gui/kappicon
bash -n cli/kappicon-cli
bash -n install.sh
bash -n scripts/validate.sh
echo "    OK"

echo "==> Python package compile (python/kappicon)"
PYTHONPATH=python python3 - <<'PY'
import compileall
import sys
from pathlib import Path

root = Path("python/kappicon")
if not root.is_dir():
    sys.exit("missing python/kappicon")
if not compileall.compile_dir(str(root), quiet=1):
    sys.exit(1)
print("    compileall OK")
PY

echo "==> Python package import smoke under temp XDG"
PYTHONPATH=python python3 - <<'PY'
import os
import sys
import tempfile
from pathlib import Path

d = tempfile.mkdtemp(prefix="kappicon-validate-")
share = Path(d) / "share"
cfg = Path(d) / "config"
pics = Path(d) / "Pictures" / "KAppIcon"
for p in (
    share,
    cfg,
    pics,
    share / "kappicon",
    share / "applications",
    share / "icons",
    share / "kappicon" / "backups",
    share / "kappicon" / "icons",
):
    p.mkdir(parents=True, exist_ok=True)
os.environ.update(
    {
        "HOME": d,
        "XDG_DATA_HOME": str(share),
        "XDG_CONFIG_HOME": str(cfg),
        "DATA_DIR": str(share / "kappicon"),
        "USER_APPS_DIR": str(share / "applications"),
        "USER_ICONS_DIR": str(share / "icons"),
        "BACKUP_DIR_DEFAULT": str(share / "kappicon" / "backups"),
        "TARGET_DIR": str(pics),
        "LIBRARY_DIR": str(share / "kappicon" / "icons"),
        "DOWNLOADS_DIR": str(Path(d) / "Downloads"),
    }
)
for k in list(sys.modules):
    if k == "kappicon" or k.startswith("kappicon."):
        del sys.modules[k]
import kappicon  # noqa: E402

for name in (
    "apply_icon_to_desktop",
    "apply_lock",
    "prepare_icon_value",
    "is_valid_desktop_id",
    "prune_unreferenced_kappicon_assets",
):
    if not hasattr(kappicon, name):
        sys.exit(f"missing export: {name}")
assert str(kappicon.DATA_DIR).startswith(d), kappicon.DATA_DIR
# Mutation package must not require PyQt6 at import
import kappicon.mutation  # noqa: E402
assert "PyQt6" not in open("python/kappicon/mutation.py", encoding="utf-8").read()
print("    import smoke OK")
PY

echo "==> VERSION present"
VERSION="$(tr -d '[:space:]' < VERSION)"
[[ -n "$VERSION" ]] || fail "VERSION file empty"
echo "    VERSION=$VERSION"

echo "==> AppStream release version matches VERSION"
python3 - <<PY
import pathlib, re, sys
version = pathlib.Path("VERSION").read_text(encoding="utf-8").strip()
meta = pathlib.Path("data/io.github.rayman1972.kappicon.metainfo.xml").read_text(
    encoding="utf-8", errors="replace"
)
m = re.search(r'<release\s+version="([^"]+)"', meta)
if not m:
    print("No <release version=...> in metainfo", file=sys.stderr)
    sys.exit(1)
rel = m.group(1)
if rel != version:
    print(f"VERSION={version!r} != metainfo first release={rel!r}", file=sys.stderr)
    sys.exit(1)
print(f"    OK ({rel})")
PY

echo "==> desktop-file-validate (soft-skip if missing)"
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate gui/kappicon.desktop
  echo "    OK"
else
  echo "    SKIP: desktop-file-validate not installed" >&2
fi

if command -v appstreamcli >/dev/null 2>&1; then
  echo "==> appstreamcli validate --no-net (soft)"
  if appstreamcli validate --no-net data/io.github.rayman1972.kappicon.metainfo.xml; then
    echo "    OK"
  else
    echo "    WARN: appstreamcli reported issues (non-fatal for validate.sh)" >&2
  fi
fi

echo "==> All hard checks passed"
