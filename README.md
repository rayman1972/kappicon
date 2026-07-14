# 🍏 macOSicons-linux

> **Automatically map custom macOS (`.icns` / `.png`) icons to Linux desktop launchers. Designed for KDE Plasma, featuring a terminal-based CLI and a Tahoe-styled GUI.**

This utility bridges the gap for customization enthusiasts who want to seamlessly apply custom macOS icons to their Linux applications. No manual extraction, scaling, or desktop entry editing required.

***

⚠️ **Disclaimer:** This is an independent, solo project developed by a single developer. It is **not** affiliated with, endorsed by, or working with the official [macosicons.com](https://macosicons.com) website or its creators. 

***

## ✨ Features

* **Terminal & GUI Launchers:** Comes with dedicated `.desktop` files for both versions. One launches the interactive tool inside your terminal, and the other opens the standalone GUI.
* **Smart Format Support:** Handles raw PNGs and maps them cleanly.
* **Desktop Integration:** Automatically updates your system's desktop entries (`.desktop` files).
* **KDE Sync:** Forces a KDE system configuration cache rebuild (`kbuildsycoca`) so your new icons show up instantly without a system reboot.

---

🚀 Installation
Getting set up is incredibly simple. Just clone the repository and run the automated installer:

```bash
# Clone the repository
git clone https://github.com/system-rw/macosicons-linux.git
cd macosicons-linux

# Run the installer
./install.sh
```

---

🛠️ Usage

🖥️ Desktop Launchers (Recommended)
Once installed, you can launch both versions directly from your application menu (under Settings/System):

Terminal Version (macOSicons): Launch it to open a terminal tab running the interactive CLI tool to guide you through mapping.

GUI Version (macOSicons (GUI)): Launch it to open a dedicated, custom-styled window to visually browse and apply your icons.

🐚 Command Line (Bash)
If you prefer using the terminal directly, you can run the scripts from anywhere after installation:

To run the interactive CLI tool:

Bash
apply-mac-icon
To run the GUI tool:

Bash
apply-mac-icon-gui
📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
