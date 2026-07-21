#!/usr/bin/env bash
# Continuous validation for kAppIcon (syntax, embed compile, version, desktop).
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

echo "==> Embedded Python compile (full PYEOF body — compile only, never exec)"
python3 - <<'PY'
import pathlib, re, sys

root = pathlib.Path(".")
text = (root / "gui" / "kappicon").read_text(encoding="utf-8", errors="replace")
m = re.search(r"python3\s+-\s+<<'PYEOF'\n(.*)\nPYEOF\b", text, flags=re.DOTALL)
if not m:
    m = re.search(r"<<'PYEOF'\n(.*)\nPYEOF\b", text, flags=re.DOTALL)
if not m:
    print("Could not extract PYEOF body from gui/kappicon", file=sys.stderr)
    sys.exit(1)
src = m.group(1)
compile(src, "gui/kappicon+PYEOF", "exec")
print("    OK")
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
# Prefer first <release version="..."> in document order (newest listed first in this project)
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
