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

REPO_URL="https://raw.githubusercontent.com/rayman1972/kappicon/main"
LOCAL_VERSION_FILE="$CONFIG_DIR/VERSION"
REMOTE_VERSION=$(curl -sf "$REPO_URL/VERSION" 2>/dev/null | tr -d '[:space:]')

# Prefer hard link (same inode as repo checkout); fall back to copy across filesystems.
install_bin() {
    local src="$1" dest="$2"
    if ln -f -- "$src" "$dest" 2>/dev/null; then
        return 0
    fi
    cp -f -- "$src" "$dest"
}

# ── Check for updates ────────────────────────────────────────────────────
check_update() {
    [ -z "$REMOTE_VERSION" ] && return
    if [ -f "$LOCAL_VERSION_FILE" ]; then
        LOCAL_VERSION=$(cat "$LOCAL_VERSION_FILE" | tr -d '[:space:]')
        if [ "$LOCAL_VERSION" != "$REMOTE_VERSION" ]; then
            echo ""
            echo "⬆️  Update available: $LOCAL_VERSION → $REMOTE_VERSION"
            echo "   Run ./install.sh --update to get the latest version."
            echo ""
        fi
    fi
}

# ── Update mode ──────────────────────────────────────────────────────────
if [ "${1:-}" = "--update" ]; then
    echo "🔄 Updating kAppIcon..."
    if [ -d .git ]; then
        git pull --rebase 2>/dev/null || { echo "❌ git pull failed — are you in the repo directory?"; exit 1; }
    else
        echo "📥 Downloading latest files..."
        mkdir -p cli gui
        curl -sfL "$REPO_URL/cli/kappicon-cli" -o cli/kappicon-cli || { echo "❌ Download failed."; exit 1; }
        curl -sfL "$REPO_URL/gui/kappicon" -o gui/kappicon
        curl -sfL "$REPO_URL/gui/kappicon.desktop" -o gui/kappicon.desktop
        curl -sfL "$REPO_URL/install.sh" -o install.sh
        curl -sfL "$REPO_URL/VERSION" -o VERSION
    fi
    echo "📦 Installing updated files..."
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
    # Also clean default ~/.local paths if XDG_* differs (legacy installs)
    if [ "$XDG_DATA_HOME" != "$HOME/.local/share" ]; then
        rm -f "$HOME/.local/share/applications/kappicon-cli.desktop" \
            "$HOME/.local/share/applications/macosicons.desktop" \
            "$HOME/.local/share/applications/macosicons-gui.desktop" 2>/dev/null || true
    fi
    [ -f assets/kappicon.png ] && cp assets/kappicon.png "$ICONS_DIR/kappicon.png"
    [ -f assets/kappicon-gui.png ] && cp assets/kappicon-gui.png "$ICONS_DIR/kappicon-gui.png"
    # GUI is the only application menu entry.
    cp gui/kappicon.desktop "$APPS_DIR/kappicon.desktop"
    # Clean accidental overwrite from older installs
    if grep -q 'KAppIcon (CLI)' "$APPS_DIR/kappicon.desktop" 2>/dev/null; then
        cp gui/kappicon.desktop "$APPS_DIR/kappicon.desktop"
    fi
    [ -f VERSION ] && cp VERSION "$LOCAL_VERSION_FILE"
    echo "✅ Updated to $REMOTE_VERSION"
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

    echo "📦 Installing missing dependencies..."
    if [ ${#NEED_SYS[@]} -gt 0 ]; then
        echo "   $PKG: ${NEED_SYS[*]}"
        if ! $SUDO "${NEED_SYS[@]}"; then
            echo "⚠️  Package install had errors; will try pip for PyQt6 if needed."
        fi
    fi
    # If distro PyQt6 package failed / missing, fall back to pip
    if ! python3 -c "import PyQt6" 2>/dev/null; then
        if [[ " ${NEED_PIP[*]} " != *" PyQt6 "* ]]; then
            NEED_PIP+=("PyQt6")
        fi
    fi
    if [ ${#NEED_PIP[@]} -gt 0 ]; then
        echo "   pip: ${NEED_PIP[*]}"
        python3 -m pip install --user "${NEED_PIP[@]}" 2>/dev/null \
            || pip3 install --user "${NEED_PIP[@]}" 2>/dev/null \
            || pip install "${NEED_PIP[@]}"
    fi
    # Final sanity checks (non-fatal for optional tools)
    if ! python3 -c "import PyQt6" 2>/dev/null; then
        echo "❌ PyQt6 is still missing. Install it with your package manager or: pip install PyQt6"
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

if command -v kbuildsycoca6 &> /dev/null; then
    kbuildsycoca6 --noincremental
elif command -v kbuildsycoca5 &> /dev/null; then
    kbuildsycoca5 --noincremental
fi

[ -f VERSION ] && cp VERSION "$LOCAL_VERSION_FILE"

echo "✅ Done! Run:  kappicon   or search for “kAppIcon” in the app menu."
echo "   CLI:        kappicon-cli --help"
echo "   Paths honor XDG_CONFIG_HOME / XDG_DATA_HOME / XDG_BIN_HOME and xdg-user-dir."
