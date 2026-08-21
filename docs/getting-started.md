# Getting Started with Maestro

Welcome to **Maestro**, a cross-platform desktop hand-gesture controller that turns ordinary webcam video into low-latency mouse, keyboard, and media commands.

---

## 1. Prerequisites

Before installing Maestro, ensure your machine satisfies the following hardware and software requirements:

- **Operating System**:
  - **Windows**: Windows 10 or 11 (64-bit) with [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe)
  - **macOS**: macOS 12 Monterey or newer (Apple Silicon M-series or Intel Core)
  - **Linux**: Ubuntu 22.04+, Fedora 38+, Arch Linux, or any modern glibc 2.31+ distribution with Wayland or X11
- **Python**: Python 3.11, 3.12, or 3.13 (64-bit)
- **Camera**: Integrated laptop webcam or standard USB camera (720p at 30fps recommended)
- **Audio (Optional)**: Working microphone if using offline voice commands

---

## 2. Installation

### Method 1: Python Package (PyPI)

Install Maestro into an isolated Python environment:

=== "Windows (PowerShell)"

    ```powershell
    # Create and activate virtual environment
    python -m venv .venv
    .venv\Scripts\Activate.ps1

    # Install base package
    pip install --upgrade pip
    pip install gesture-controller

    # Optional: Install voice recognition extra
    pip install "gesture-controller[voice]"
    ```

=== "macOS / Linux"

    ```bash
    # Create and activate virtual environment
    python3 -m venv .venv
    source .venv/bin/activate

    # Install base package
    pip install --upgrade pip
    pip install gesture-controller

    # Optional: Install voice recognition extra
    pip install "gesture-controller[voice]"
    ```

### Method 2: Development Installation with `uv`

For developers and contributors, [uv](https://docs.astral.sh/uv/) provides instant virtual environment setup and dependency synchronization:

```bash
# Clone the repository
git clone https://github.com/aryansinghnagar/Maestro.git
cd Maestro

# Synchronize all packages and tools
uv sync

# Run the test suite
uv run pytest gesture_controller/tests
```

---

## 3. Platform Permission Setup

Maestro requires access to your camera and operating system input injection subsystems:

### Windows Permissions
1. Open **Windows Settings → Privacy & Security → Camera** and ensure **Let desktop apps access your camera** is enabled.
2. Injected inputs to administrative windows require the Maestro input broker to communicate across UIPI (User Interface Privilege Isolation) boundaries.

### macOS Permissions
1. **Camera**: Grant permission when prompted on first launch.
2. **Accessibility & Input Monitoring**:
   - Go to **System Settings → Privacy & Security → Accessibility**.
   - Add and enable your terminal emulator or `Maestro`.
   - Go to **System Settings → Privacy & Security → Input Monitoring** and enable access.

### Linux Permissions
1. Add your user account to the `input` and `video` groups:
   ```bash
   sudo usermod -aG input,video $USER
   ```
2. Install the bundled `udev` rule for non-root `/dev/uinput` access:
   ```bash
   sudo cp packaging/99-gesture-controller-uinput.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
3. Log out and log back in to apply group changes.

---

## 4. First-Run Onboarding & Verification

### Launching the Application

Start Maestro from your terminal or application launcher:

```bash
maestro
```

On first startup, the **Onboarding Wizard** will guide you through:
1. **Hardware Verification**: Validates camera access and probes available GPU compute backends (DirectML / TensorRT / CoreML).
2. **Permission Check**: Verifies OS input injection permissions.
3. **Interactive Calibration**: Opens a preview window displaying 21-point hand landmark tracking in real-time.
4. **Gesture Tutorial**: Practice basic gestures (Swipe, Fist, Pinch, Scroll) with instant visual feedback.

### Automated Self-Test

You can also run Maestro's automated self-diagnostic tool at any time:

```bash
gesture-controller-verify
```

---

## 5. Your First Gestures

Once Maestro is running in your system tray:

1. **Swipe Left**: Raise your open hand and move it swiftly from right to left in front of the camera to switch to the previous tab (`Ctrl+Shift+Tab`).
2. **Swipe Right**: Move your open hand from left to right to switch to the next tab (`Ctrl+Tab`).
3. **Fist**: Clench your hand into a fist and hold for 300ms to minimize the active window.
4. **Continuous Scroll**: Move your index finger up or down while keeping your thumb pinched to scroll smoothly.

> [!TIP]
> You can pause gesture recognition at any time by right-clicking the system tray icon and selecting **Pause**, or by configuring a global panic hotkey in Settings.

---

## Next Steps

- Explore all built-in gestures and voice controls in the **[User Guide](user-guide.md)**.
- Customize trigger conditions and per-app bindings in the **[Configuration Guide](configuration.md)**.
- Learn about system internals in the **[Architecture Overview](architecture.md)**.

