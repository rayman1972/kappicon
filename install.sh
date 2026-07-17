#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.local/bin"
REPO_URL="https://raw.githubusercontent.com/system-rw/macosicons-linux/main"
LOCAL_VERSION_FILE="$HOME/.config/KAppIcon/VERSION"
REMOTE_VERSION=$(curl -sf "$REPO_URL/VERSION" 2>/dev/null | tr -d '[:space:]')

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
    echo "🔄 Updating KAppIcon..."
    if [ -d .git ]; then
        git pull --rebase 2>/dev/null || { echo "❌ git pull failed — are you in the repo directory?"; exit 1; }
    else
        echo "📥 Downloading latest files..."
        mkdir -p cli gui
        curl -sfL "$REPO_URL/cli/kappicon" -o cli/kappicon || { echo "❌ Download failed."; exit 1; }
        curl -sfL "$REPO_URL/gui/kappicon" -o gui/kappicon
        curl -sfL "$REPO_URL/install.sh" -o install.sh
        curl -sfL "$REPO_URL/VERSION" -o VERSION
    fi
    echo "📦 Installing updated files..."
    mkdir -p "$INSTALL_DIR" ~/.local/share/applications ~/.local/share/icons ~/.local/share/kappicon/icons
    ln -f cli/kappicon "$INSTALL_DIR/kappicon"
    ln -f gui/kappicon "$INSTALL_DIR/kappicon-gui"
    chmod +x "$INSTALL_DIR/kappicon" "$INSTALL_DIR/kappicon-gui"
    # Compatibility shims for old names
    ln -sf kappicon "$INSTALL_DIR/apply-mac-icon" 2>/dev/null || true
    ln -sf kappicon-gui "$INSTALL_DIR/apply-mac-icon-gui" 2>/dev/null || true
    [ -f assets/kappicon.png ] && cp assets/kappicon.png ~/.local/share/icons/kappicon.png
    [ -f assets/kappicon-gui.png ] && cp assets/kappicon-gui.png ~/.local/share/icons/kappicon-gui.png
    # Also register under legacy icon names if present
    [ -f assets/kappicon.png ] && cp assets/kappicon.png ~/.local/share/icons/macosicons.png 2>/dev/null || true
    # GUI is the main menu entry; CLI uses a distinct filename so it does not overwrite.
    cp gui/kappicon.desktop ~/.local/share/applications/kappicon.desktop
    [ -f cli/kappicon-cli.desktop ] && cp cli/kappicon-cli.desktop ~/.local/share/applications/kappicon-cli.desktop
    # Clean accidental overwrite from older installs
    if grep -q 'KAppIcon (CLI)' ~/.local/share/applications/kappicon.desktop 2>/dev/null; then
        cp gui/kappicon.desktop ~/.local/share/applications/kappicon.desktop
    fi
    mkdir -p "$(dirname "$LOCAL_VERSION_FILE")"
    [ -f VERSION ] && cp VERSION "$LOCAL_VERSION_FILE"
    echo "✅ Updated to $REMOTE_VERSION"
    exit 0
fi

echo "🎨 Installing KAppIcon (CLI, GUI & Icon Editor) for Linux..."

check_update

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
        PKG="zypper"
        SUDO="sudo zypper install -y"
        declare -A PKGS=(
            [python]=python3
            [pyqt6]=python3-qt6
            [icns]=libicns-utils
            [imagemagick]=ImageMagick
            [kdialog]=kdialog
            [fzf]=fzf
        )
    else
        echo "⚠️  Could not detect package manager. Install manually:"
        echo "   python3, PyQt6, libicns/icnsutils (icns2png), imagemagick, kdialog, fzf"
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
        $SUDO "${NEED_SYS[@]}"
    fi
    if [ ${#NEED_PIP[@]} -gt 0 ]; then
        echo "   pip: ${NEED_PIP[*]}"
        pip install "${NEED_PIP[@]}"
    fi
    echo "✅ Dependencies installed."
}

install_deps

mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/share/icons ~/.local/share/kappicon/icons

ln -f cli/kappicon ~/.local/bin/kappicon
ln -f gui/kappicon ~/.local/bin/kappicon-gui
chmod +x ~/.local/bin/kappicon ~/.local/bin/kappicon-gui
# Old command names still work
ln -sf kappicon ~/.local/bin/apply-mac-icon
ln -sf kappicon-gui ~/.local/bin/apply-mac-icon-gui

if [ -f assets/kappicon.png ]; then
    cp assets/kappicon.png ~/.local/share/icons/kappicon.png
fi
if [ -f assets/kappicon-gui.png ]; then
    cp assets/kappicon-gui.png ~/.local/share/icons/kappicon-gui.png
fi

# Desktop launchers — distinct filenames (both used to be kappicon.desktop and the CLI won)
cp gui/kappicon.desktop ~/.local/share/applications/kappicon.desktop
[ -f cli/kappicon-cli.desktop ] && cp cli/kappicon-cli.desktop ~/.local/share/applications/kappicon-cli.desktop

# Remove legacy desktop entries if present
rm -f ~/.local/share/applications/macosicons.desktop \
      ~/.local/share/applications/macosicons-gui.desktop 2>/dev/null || true

if command -v kbuildsycoca6 &> /dev/null; then
    kbuildsycoca6 --noincremental
elif command -v kbuildsycoca5 &> /dev/null; then
    kbuildsycoca5 --noincremental
fi

mkdir -p "$(dirname "$LOCAL_VERSION_FILE")"
[ -f VERSION ] && cp VERSION "$LOCAL_VERSION_FILE"

echo "✅ Done! Run:  kappicon-gui   or search for “KAppIcon” in the app menu."
echo "   CLI:        kappicon --help"
