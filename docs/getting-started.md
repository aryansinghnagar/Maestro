# Getting Started with Maestro

Welcome to **Maestro**, a cross-platform desktop hand-gesture controller that allows you to control your computer using webcam gesture recognition and voice commands.

---

## Key Features

- **21-Point Landmark Tracking**: High-precision hand tracking via ONNX Runtime & MediaPipe.
- **Cross-Platform OS Control**: Direct native input simulation for Windows (`SendInput`), Linux (`uinput`), and macOS (`Quartz/CGEvent`).
- **FSM & DTW Recognition Engine**: AST-compiled state machine condition evaluation and custom dynamic time-warping gesture recording.
- **Offline Voice Control**: Private, offline speech recognition powered by Vosk and configurable wake-word logic.
- **Privacy & Security**: 100% on-device processing. Zero network egress for camera frames, audio, or gesture events.
- **Accessibility & Tremor Compensation**: One-Euro low-pass filtering, high contrast modes, screen reader compliance (WCAG 2.2).

---

## System Requirements

- **Operating System**:
  - Windows 10 / 11 (64-bit)
  - macOS 12+ (Apple Silicon or Intel)
  - Linux (Ubuntu 22.04+, Fedora 38+, Arch)
- **Hardware**: Standard USB webcam or built-in camera (720p 30fps recommended)
- **Python**: 3.11, 3.12, or 3.13 (if installing via PyPI)

---

## Quick Installation

### Option A: Install via PyPI (Recommended for Developers)

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Maestro
pip install gesture-controller

# Launch Maestro
maestro
```

### Option B: Platform Installers

- **Windows**: Download and run `GestureController-Setup-v1.0.0.exe` generated via NSIS.
- **Linux**: Run the setup script to grant non-root `/dev/uinput` privileges:
  ```bash
  git clone https://github.com/aryansinghnagar/Maestro.git
  cd Maestro
  bash packaging/linux/install.sh
  ```
- **macOS**: Grant Camera and Accessibility permissions under **System Settings → Privacy & Security** on first run.

---

## First-Run Onboarding

Upon launching Maestro for the first time:
1. The **Onboarding Wizard** will automatically run to test camera accessibility and OS input privileges.
2. Grant any requested permissions if prompted by your operating system.
3. Test hand recognition using the interactive preview overlay.
