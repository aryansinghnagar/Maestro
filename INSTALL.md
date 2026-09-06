# Maestro Installation & Platform Setup Guide

This document provides detailed installation, dependency setup, and platform permission instructions for **Maestro v1.3.0** across Windows, macOS, and Linux.

---

## 1. System Requirements

| Component | Minimum Requirement | Recommended |
|---|---|---|
| **Operating System** | Windows 10 (64-bit), macOS 12+, Linux (glibc 2.31+) | Windows 11, macOS 14+, Ubuntu 22.04+ |
| **Python** | Python 3.11, 3.12, or 3.13 | Python 3.11 or 3.12 |
| **Camera** | Any USB / integrated webcam (640x480 @ 15fps) | 720p / 1080p @ 30–60fps |
| **CPU / GPU** | Dual-core CPU with AVX2 support | Quad-core CPU with DirectML / CUDA / CoreML GPU |
| **Memory (RAM)** | 512 MB available | 2 GB available |
| **Disk Space** | 200 MB (base) / 350 MB (with Vosk voice model) | 500 MB |

---

## 2. Installation Methods

### Method A: Install via PyPI (Recommended for Users)

```bash
# Create and activate an isolated virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install Maestro package
pip install gesture-controller

# (Optional) Install offline voice recognition support:
pip install "gesture-controller[voice]"

# Launch the application
maestro
```

### Method B: Development Install from Source (Using `uv`)

[uv](https://docs.astral.sh/uv/) is the recommended high-performance Python package manager for Maestro:

```bash
# Clone the repository
git clone https://github.com/aryansinghnagar/Maestro.git
cd Maestro

# Sync dependencies into isolated virtual environment
uv sync

# Run test suite to verify installation
uv run pytest gesture_controller/tests

# Launch Maestro from source
uv run maestro
```

---

## 3. Platform-Specific Prerequisites & Permissions

### Windows (10 / 11 64-bit)

1. **Visual C++ Redistributable**: Ensure the [Microsoft Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe) is installed.
2. **Camera Privacy Access**:
   - Open **Windows Settings → Privacy & Security → Camera**.
   - Ensure **Camera access** and **Let desktop apps access your camera** are toggled **ON**.
3. **Privilege-Separated Broker Service**:
   - On Windows, injected inputs targeting elevated / Administrator windows require the Maestro input broker to communicate across UIPI (User Interface Privilege Isolation) boundaries.
   - Run `maestro verify-audit-log` or `gesture-controller-verify` to validate named pipe IPC and SID token verification.

### macOS (Apple Silicon & Intel)

1. **System Permissions (TCC)**:
   - **Camera Permission**: Upon initial launch, macOS will display a permission prompt asking for Camera access. Select **OK**.
   - **Accessibility & Input Monitoring**:
     - Open **System Settings → Privacy & Security → Accessibility**.
     - Add and enable your terminal emulator or Python application (e.g. `Terminal`, `iTerm2`, or `Maestro`).
     - Open **System Settings → Privacy & Security → Input Monitoring** and ensure the app is checked.
2. **AppleScript Support**:
   - Application switching and media control on macOS use the AppleScript bridge (`applescript_bridge.py`).

### Linux (Wayland & X11)

1. **User Group Permissions (`uinput` & `video`)**:
   - In order to simulate keyboard and mouse inputs without running as root, add your user to the `input` and `video` groups:
   ```bash
   sudo usermod -aG input,video $USER
   ```
2. **Udev Rules Configuration**:
   - Copy the bundled uinput udev rule to allow non-root write access to `/dev/uinput`:
   ```bash
   sudo cp packaging/99-gesture-controller-uinput.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
3. **Log Out & Re-login**:
   - Log out of your desktop session and back in for the group permissions to take effect.
4. **System Dependencies (OpenCV & Audio)**:
   ```bash
   # Debian / Ubuntu:
   sudo apt-get install -y libgl1 libegl1 libglib2.0-0 portaudio19-dev libasound2-dev

   # Fedora / RHEL:
   sudo dnf install -y mesa-libGL mesa-libEGL glib2 portaudio-devel alsa-lib-devel

   # Arch Linux:
   sudo pacman -S mesa libglvnd portaudio alsa-lib
   ```
5. **Systemd User Service (Optional)**:
   ```bash
   mkdir -p ~/.config/systemd/user
   cp packaging/linux/gesture-controller.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now gesture-controller.service
   ```

---

## 4. Verification & Diagnostics

To verify your installation and hardware capabilities automatically, run the built-in diagnostic tool:

```bash
gesture-controller-verify
```

Or query the CLI status:

```bash
maestro status
```

