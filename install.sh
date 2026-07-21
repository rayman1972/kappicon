#!/usr/bin/env bash
set -e

# Honor XDG Base Directory (defaults match the freestanding Linux layout).
: "${XDG_CONFIG_HOME:=$HOME/.config}"
: "${XDG_DATA_HOME:=$HOME/.local/share}"
: "${XDG_BIN_HOME:=$HOME/.local/bin}"

INSTALL_DIR="${INSTALL_DIR:-$XDG_BIN_HOME}"
APPS_DIR="${APPS_DIR:-$XDG_DATA_HOME/applications}"
ICONS_DIR="${ICONS_DIR:-$XDG_DATA_HOME/icons}"
DATA_DIR="${DATA_DIR:-$XDG_DATA_HOME/kappicon}"
CONFIG_DIR="${CONFIG_DIR:-$XDG_CONFIG_HOME/KAppIcon}"

GITHUB_REPO="rayman1972/kappicon"
LOCAL_VERSION_FILE="$CONFIG_DIR/VERSION"

# Prefer hard link (same inode as repo checkout); fall back to copy across filesystems.
install_bin() {
    local src="$1" dest="$2"
    if ln -f -- "$src" "$dest" 2>/dev/null; then
        return 0
    fi
    cp -f -- "$src" "$dest"
}

# Latest GitHub release version (no leading v). Empty if API unavailable.
resolve_latest_release_version() {
    local json tag
    json=$(curl -sfL "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" 2>/dev/null) || return 1
    tag=$(printf '%s' "$json" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    t = (d.get("tag_name") or "").strip()
    if t.startswith("v") or t.startswith("V"):
        t = t[1:]
    print(t)
except Exception:
    sys.exit(1)
' 2>/dev/null) || return 1
    [ -n "$tag" ] || return 1
    printf '%s\n' "$tag"
}

download_to() {
    local url="$1" dest="$2"
    curl -sfL "$url" -o "$dest"
}

# Verify archive basename against SHA256SUMS in the same directory (fail closed).
verify_sha256sums() {
    local dir="$1" archive_name="$2"
    local sums="$dir/SHA256SUMS"
    [ -f "$sums" ] || return 1
    [ -f "$dir/$archive_name" ] || return 1
    command -v sha256sum >/dev/null 2>&1 || {
        echo "❌ sha256sum is required to verify releases (coreutils)." >&2
        return 1
    }
    # Only check the archive entry (SUMS may list more files later).
    if ! grep -E "[[:space:]]${archive_name}\$" "$sums" >/dev/null 2>&1; then
        echo "❌ SHA256SUMS has no entry for ${archive_name}." >&2
        return 1
    fi
    (
        cd "$dir" || exit 1
        grep -E "[[:space:]]${archive_name}\$" SHA256SUMS | sha256sum -c -
    )
}

# Install product files from a source tree root into user XDG destinations.
install_from_tree() {
    local root="$1"
    mkdir -p "$INSTALL_DIR" "$APPS_DIR" "$ICONS_DIR" "$DATA_DIR/icons" "$CONFIG_DIR"
    install_bin "$root/gui/kappicon" "$INSTALL_DIR/kappicon"
    install_bin "$root/cli/kappicon-cli" "$INSTALL_DIR/kappicon-cli"
    chmod +x "$INSTALL_DIR/kappicon" "$INSTALL_DIR/kappicon-cli"
    rm -f "$INSTALL_DIR/kappicon-gui" \
        "$INSTALL_DIR/apply-mac-icon" "$INSTALL_DIR/apply-mac-icon-gui" \
        "$ICONS_DIR/macosicons.png" "$ICONS_DIR/macosicons-gui.png" \
        "$APPS_DIR/macosicons.desktop" \
        "$APPS_DIR/macosicons-gui.desktop" \
        "$APPS_DIR/kappicon-cli.desktop" 2>/dev/null || true
    if [ "$XDG_DATA_HOME" != "$HOME/.local/share" ]; then
        rm -f "$HOME/.local/share/applications/kappicon-cli.desktop" \
            "$HOME/.local/share/applications/macosicons.desktop" \
            "$HOME/.local/share/applications/macosicons-gui.desktop" 2>/dev/null || true
    fi
    [ -f "$root/assets/kappicon.png" ] && cp "$root/assets/kappicon.png" "$ICONS_DIR/kappicon.png"
    [ -f "$root/assets/kappicon-gui.png" ] && cp "$root/assets/kappicon-gui.png" "$ICONS_DIR/kappicon-gui.png"
    if [ -f "$root/gui/kappicon.desktop" ]; then
        cp "$root/gui/kappicon.desktop" "$APPS_DIR/kappicon.desktop"
    fi
    if [ -f "$APPS_DIR/kappicon.desktop" ] && grep -q 'KAppIcon (CLI)' "$APPS_DIR/kappicon.desktop" 2>/dev/null; then
        cp "$root/gui/kappicon.desktop" "$APPS_DIR/kappicon.desktop"
    fi
    METAINFO_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/metainfo"
    if [ -f "$root/data/io.github.rayman1972.kappicon.metainfo.xml" ]; then
        mkdir -p "$METAINFO_DIR"
        cp "$root/data/io.github.rayman1972.kappicon.metainfo.xml" \
            "$METAINFO_DIR/io.github.rayman1972.kappicon.metainfo.xml"
    fi
    if [ -f "$root/VERSION" ]; then
        cp "$root/VERSION" "$LOCAL_VERSION_FILE"
    fi
}

# ── Check for updates (latest GitHub release tag; non-fatal if offline) ──
check_update() {
    local remote
    remote=$(resolve_latest_release_version 2>/dev/null) || return 0
    [ -n "$remote" ] || return 0
    if [ -f "$LOCAL_VERSION_FILE" ]; then
        LOCAL_VERSION=$(tr -d '[:space:]' < "$LOCAL_VERSION_FILE")
        if [ "$LOCAL_VERSION" != "$remote" ]; then
            echo ""
            echo "⬆️  Update available: $LOCAL_VERSION → $remote"
            echo "   Run ./install.sh --update to get the latest version."
            echo ""
        fi
    fi
}

# Flags: --update · --install-deps (privileged package installs are opt-in)
INSTALL_DEPS=0
DO_UPDATE=0
for arg in "$@"; do
    case "$arg" in
        --update) DO_UPDATE=1 ;;
        --install-deps) INSTALL_DEPS=1 ;;
        -h|--help)
            echo "Usage: ./install.sh [--update] [--install-deps]"
            echo "  Default: user-level install only (~/.local) — no sudo."
            echo "  --install-deps  Install missing system packages (may prompt for sudo)."
            echo "  --update        Update then reinstall:"
            echo "                    git clone → git pull --rebase"
            echo "                    otherwise → latest GitHub release tarball + SHA256SUMS verify"
            exit 0
            ;;
    esac
done

# ── Update mode ──────────────────────────────────────────────────────────
if [ "$DO_UPDATE" = "1" ]; then
    echo "🔄 Updating kAppIcon..."
    if [ -d .git ]; then
        git pull --rebase 2>/dev/null || { echo "❌ git pull failed — are you in the repo directory?"; exit 1; }
        echo "📦 Installing from working tree..."
        install_from_tree "$(pwd)"
        VER_MSG=$(tr -d '[:space:]' < VERSION 2>/dev/null || true)
        echo "✅ Updated${VER_MSG:+ to $VER_MSG}"
        exit 0
    fi

    command -v sha256sum >/dev/null 2>&1 || {
        echo "❌ sha256sum is required for non-git updates (install coreutils)."
        exit 1
    }
    command -v curl >/dev/null 2>&1 || {
        echo "❌ curl is required for non-git updates."
        exit 1
    }
    command -v tar >/dev/null 2>&1 || {
        echo "❌ tar is required for non-git updates."
        exit 1
    }

    VERSION=$(resolve_latest_release_version) || {
        echo "❌ Could not resolve latest GitHub release for ${GITHUB_REPO}."
        echo "   Use a git clone and ./install.sh --update, or retry when network/API is available."
        exit 1
    }
    TAG="v${VERSION}"
    ARCHIVE_NAME="kappicon-${VERSION}.tar.gz"
    ARCHIVE_URL="https://github.com/${GITHUB_REPO}/archive/refs/tags/${TAG}.tar.gz"
    SUMS_URL="https://github.com/${GITHUB_REPO}/releases/download/${TAG}/SHA256SUMS"

    STAGE=$(mktemp -d "${TMPDIR:-/tmp}/kappicon-update.XXXXXX")
    cleanup_stage() { rm -rf -- "$STAGE"; }
    trap cleanup_stage EXIT

    echo "📥 Downloading ${TAG} release archive (not raw main)..."
    download_to "$ARCHIVE_URL" "$STAGE/$ARCHIVE_NAME" || {
        echo "❌ Failed to download $ARCHIVE_URL"
        exit 1
    }
    echo "🔐 Fetching release SHA256SUMS..."
    download_to "$SUMS_URL" "$STAGE/SHA256SUMS" || {
        echo "❌ Failed to download $SUMS_URL"
        echo "   Non-git update requires a SHA256SUMS release asset (fail closed)."
        echo "   See CONTRIBUTING.md — Release checksums."
        exit 1
    }
    echo "🔐 Verifying checksum..."
    verify_sha256sums "$STAGE" "$ARCHIVE_NAME" || {
        echo "❌ Checksum verification failed — not installing."
        exit 1
    }

    mkdir -p "$STAGE/src"
    tar -xzf "$STAGE/$ARCHIVE_NAME" -C "$STAGE/src" || {
        echo "❌ Failed to extract archive."
        exit 1
    }
    EXTRACTED=$(find "$STAGE/src" -mindepth 1 -maxdepth 1 -type d | head -n1)
    [ -n "$EXTRACTED" ] && [ -f "$EXTRACTED/gui/kappicon" ] && [ -f "$EXTRACTED/cli/kappicon-cli" ] || {
        echo "❌ Unexpected archive layout (missing gui/kappicon or cli/kappicon-cli)."
        exit 1
    }

    echo "📦 Installing verified ${TAG}..."
    install_from_tree "$EXTRACTED"
    echo "✅ Updated to $VERSION (checksum verified)"
    exit 0
fi

echo "🎨 Installing kAppIcon (GUI & CLI) for Linux..."

check_update

# openSUSE ships versioned PyQt6 RPMs (python312-PyQt6, python313-PyQt6, …)
# Prefer the package matching the default python3, then generic names.
opensuse_pyqt6_pkg() {
    local ver cand
    ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")' 2>/dev/null || true)
    for cand in "python${ver}-PyQt6" "python3-PyQt6" "python-PyQt6"; do
        [ -n "$cand" ] || continue
        # Exact package name present in repos?
        if zypper --non-interactive search --match-exact -t package "$cand" 2>/dev/null \
            | grep -qE "[[:space:]]${cand}[[:space:]]"; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    # Last resort: first *PyQt6 package from search (skip source/src lines)
    cand=$(zypper --non-interactive search -t package PyQt6 2>/dev/null \
        | awk -F'|' '/PyQt6/ && $0 !~ /srcpackage|source/ {
            gsub(/^ +| +$/, "", $2);
            if ($2 ~ /PyQt6$/) { print $2; exit }
        }')
    if [ -n "$cand" ]; then
        printf '%s\n' "$cand"
        return 0
    fi
    return 1
}

# Check and install dependencies
install_deps() {
    if command -v pacman &>/dev/null; then
        PKG="pacman"
        SUDO="sudo pacman -S --noconfirm"
        declare -A PKGS=(
            [python]=python
            [pyqt6]=python-pyqt6
            [icns]=libicns
            [imagemagick]=imagemagick
            [kdialog]=kdialog
            [fzf]=fzf
        )
    elif command -v apt &>/dev/null; then
        PKG="apt"
        SUDO="sudo apt install -y"
        declare -A PKGS=(
            [python]=python3
            [pyqt6]=python3-pyqt6
            [icns]=icnsutils
            [imagemagick]=imagemagick
            [kdialog]=kdialog
            [fzf]=fzf
        )
    elif command -v dnf &>/dev/null; then
        PKG="dnf"
        SUDO="sudo dnf install -y"
        declare -A PKGS=(
            [python]=python3
            [pyqt6]=python3-pyqt6
            [icns]=libicns-utils
            [imagemagick]=ImageMagick
            [kdialog]=kdialog
            [fzf]=fzf
        )
    elif command -v zypper &>/dev/null; then
        # openSUSE Leap / Tumbleweed
        PKG="zypper"
        SUDO="sudo zypper --non-interactive install -y"
        PYQT6_PKG=$(opensuse_pyqt6_pkg || true)
        declare -A PKGS=(
            [python]=python3
            [pyqt6]="${PYQT6_PKG:-}"
            # Tools (icns2png) ship in the main package on openSUSE
            [icns]=libicns
            [imagemagick]=ImageMagick
            [kdialog]=kdialog
            [fzf]=fzf
        )
    else
        echo "⚠️  Could not detect package manager. Install manually:"
        echo "   python3, PyQt6, libicns/icnsutils (icns2png), ImageMagick, kdialog, fzf"
        echo "   openSUSE: python3 python3-PyQt6 (or python3XY-PyQt6) libicns ImageMagick kdialog fzf"
        read -rp "Continue anyway? [y/N] " yn
        [[ "$yn" =~ ^[Yy]$ ]] || exit 1
        return
    fi

    NEED_SYS=()
    NEED_PIP=()

    command -v python3 &>/dev/null || NEED_SYS+=("${PKGS[python]}")
    if ! python3 -c "import PyQt6" 2>/dev/null; then
        if [ -n "${PKGS[pyqt6]:-}" ]; then
            NEED_SYS+=("${PKGS[pyqt6]}")
        else
            NEED_PIP+=("PyQt6")
        fi
    fi
    command -v icns2png &>/dev/null || NEED_SYS+=("${PKGS[icns]}")
    if ! command -v magick &>/dev/null && ! command -v convert &>/dev/null; then
        NEED_SYS+=("${PKGS[imagemagick]}")
    fi
    command -v kdialog &>/dev/null || NEED_SYS+=("${PKGS[kdialog]}")
    command -v fzf &>/dev/null || NEED_SYS+=("${PKGS[fzf]}")

    if [ ${#NEED_SYS[@]} -eq 0 ] && [ ${#NEED_PIP[@]} -eq 0 ]; then
        echo "✅ All dependencies satisfied."
        return
    fi

    echo "📦 Missing dependencies:"
    [ ${#NEED_SYS[@]} -gt 0 ] && echo "   system ($PKG): ${NEED_SYS[*]}"
    [ ${#NEED_PIP[@]} -gt 0 ] && echo "   pip: ${NEED_PIP[*]}"

    # Default stays user-scoped: never invoke sudo unless explicitly requested.
    if [ "${INSTALL_DEPS:-0}" != "1" ]; then
        echo ""
        echo "   Install is user-level only by default (no root)."
        echo "   Re-run with:  ./install.sh --install-deps"
        echo "   Or install packages yourself, then re-run ./install.sh"
        echo ""
        if ! python3 -c "import PyQt6" 2>/dev/null; then
            echo "❌ PyQt6 is required for the GUI. Install it, then re-run ./install.sh"
            echo "   Arch:   pacman -S python-pyqt6"
            echo "   Debian: apt install python3-pyqt6"
            echo "   pip:    pip install --user PyQt6"
            echo "   Or:     ./install.sh --install-deps"
            exit 1
        fi
        if ! command -v magick &>/dev/null && ! command -v convert &>/dev/null; then
            echo "⚠️  ImageMagick not found (magick/convert). Custom image apply may fail."
        fi
        if ! command -v icns2png &>/dev/null; then
            echo "⚠️  icns2png not found (libicns / icnsutils)."
        fi
        return
    fi

    echo "📦 Installing missing dependencies (--install-deps)..."
    if [ ${#NEED_SYS[@]} -gt 0 ]; then
        echo "   $PKG: ${NEED_SYS[*]}"
        if ! $SUDO "${NEED_SYS[@]}"; then
            echo "⚠️  Package install had errors; will try pip for PyQt6 if needed."
        fi
    fi
    # If distro PyQt6 package failed / missing, fall back to pip (user install)
    if ! python3 -c "import PyQt6" 2>/dev/null; then
        if [[ " ${NEED_PIP[*]} " != *" PyQt6 "* ]]; then
            NEED_PIP+=("PyQt6")
        fi
    fi
    if [ ${#NEED_PIP[@]} -gt 0 ]; then
        echo "   pip --user: ${NEED_PIP[*]}"
        python3 -m pip install --user "${NEED_PIP[@]}" 2>/dev/null \
            || pip3 install --user "${NEED_PIP[@]}" 2>/dev/null \
            || pip install --user "${NEED_PIP[@]}"
    fi
    # Final sanity checks (non-fatal for optional tools)
    if ! python3 -c "import PyQt6" 2>/dev/null; then
        echo "❌ PyQt6 is still missing. Install it with your package manager or: pip install --user PyQt6"
        exit 1
    fi
    if ! command -v magick &>/dev/null && ! command -v convert &>/dev/null; then
        echo "⚠️  ImageMagick not found (magick/convert). Custom image apply may fail."
    fi
    if ! command -v icns2png &>/dev/null; then
        echo "⚠️  icns2png not found (openSUSE: libicns, Debian: icnsutils, Fedora: libicns-utils)."
    fi
    echo "✅ Dependencies installed."
}

install_deps

mkdir -p "$INSTALL_DIR" "$APPS_DIR" "$ICONS_DIR" "$DATA_DIR/icons" "$CONFIG_DIR"

# GUI: kappicon · CLI: kappicon-cli
install_bin gui/kappicon "$INSTALL_DIR/kappicon"
install_bin cli/kappicon-cli "$INSTALL_DIR/kappicon-cli"
chmod +x "$INSTALL_DIR/kappicon" "$INSTALL_DIR/kappicon-cli"
# Drop leftover names from older installs / rebrand
# CLI is terminal-only — never ship a menu entry for it.
rm -f "$INSTALL_DIR/kappicon-gui" \
    "$INSTALL_DIR/apply-mac-icon" "$INSTALL_DIR/apply-mac-icon-gui" \
    "$ICONS_DIR/macosicons.png" "$ICONS_DIR/macosicons-gui.png" \
    "$APPS_DIR/macosicons.desktop" \
    "$APPS_DIR/macosicons-gui.desktop" \
    "$APPS_DIR/kappicon-cli.desktop" 2>/dev/null || true
if [ "$XDG_DATA_HOME" != "$HOME/.local/share" ]; then
    rm -f "$HOME/.local/share/applications/kappicon-cli.desktop" \
        "$HOME/.local/share/applications/macosicons.desktop" \
        "$HOME/.local/share/applications/macosicons-gui.desktop" 2>/dev/null || true
fi

if [ -f assets/kappicon.png ]; then
    cp assets/kappicon.png "$ICONS_DIR/kappicon.png"
fi
if [ -f assets/kappicon-gui.png ]; then
    cp assets/kappicon-gui.png "$ICONS_DIR/kappicon-gui.png"
fi

# Desktop launcher — GUI only (CLI is run from the terminal)
cp gui/kappicon.desktop "$APPS_DIR/kappicon.desktop"

# AppStream metainfo for software centers (Pamac / GNOME Software / Discover)
METAINFO_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/metainfo"
if [ -f data/io.github.rayman1972.kappicon.metainfo.xml ]; then
    mkdir -p "$METAINFO_DIR"
    cp data/io.github.rayman1972.kappicon.metainfo.xml \
        "$METAINFO_DIR/io.github.rayman1972.kappicon.metainfo.xml"
fi

if command -v kbuildsycoca6 &> /dev/null; then
    kbuildsycoca6 --noincremental
elif command -v kbuildsycoca5 &> /dev/null; then
    kbuildsycoca5 --noincremental
fi

[ -f VERSION ] && cp VERSION "$LOCAL_VERSION_FILE"

echo "✅ Done! Run:  kappicon   or search for “kAppIcon” in the app menu."
echo "   CLI:        kappicon-cli --help"
echo "   Paths honor XDG_CONFIG_HOME / XDG_DATA_HOME / XDG_BIN_HOME and xdg-user-dir."
