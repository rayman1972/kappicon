# macOSicons Companion

macOSicons Companion is a professional-grade utility designed to map custom icons to your Linux application launchers (.desktop files) with the look and feel of macOS.

## 🚀 Features

* **Settings Dashboard**: A centralized UI to manage themes, glass effects, and backup preferences.
* **Terminal & GUI Launchers**: Comes with dedicated .desktop files for both versions. One launches the interactive tool inside your terminal, and the other opens the standalone GUI.
* **Smart Format Support**: Handles raw PNGs, ICOs, and ICNS files, mapping them cleanly to your applications.
* **Desktop Integration**: Automatically updates your system's desktop entries (.desktop files) to ensure correct icon application.
* **KDE Sync**: Forces a KDE system configuration cache rebuild (kbuildsycoca) so your new icons show up instantly without a system reboot.
* **Automated Safety**: Timestamped backups of all .desktop files are created automatically before any changes are made.
* **One-Click Restore**: Easily roll back to any previous backup state directly from the Settings tab.
* **Glassmorphic Design**: A beautiful, adaptive interface with configurable transparency and theme options.
* **Persistent Config**: All settings are saved automatically via QSettings (~/.config/macOSicons/macOSicons.conf), shared seamlessly between the CLI and GUI.

## 📸 Screenshots

### GUI Interface (Clean View)
![macOSicons GUI Interface](screenshots/gui-dark-light.png)

## 🛠️ Installation

Ensure you have the required dependencies installed, which is added to the install script. But in case it didn't work try to install: python3 python3-pyqt6 icnsutils imagemagick kdialog.  With your system's package manager

Then, run:

```bash
./install.sh
```

## 💻 Usage

### Graphical Interface (GUI)

```bash
~/.local/bin/apply-mac-icon-gui
```

### Command Line Interface (CLI)

```bash
apply-mac-icon --help
```

## 🛡️ Safety & Configuration

* **Backups**: Located at ~/.local/share/macosicons/backups/
* **Persistence**: Config file located at ~/.config/macOSicons/macOSicons.conf
