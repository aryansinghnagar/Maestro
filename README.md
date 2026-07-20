# Maestro

**Cross-platform desktop hand-gesture controller. Control your computer with hand gestures via webcam.**

[![CI](https://github.com/aryansinghnagar/Maestro/actions/workflows/ci.yml/badge.svg)](https://github.com/aryansinghnagar/Maestro/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/aryansinghnagar/Maestro/branch/main/graph/badge.svg)](https://github.com/aryansinghnagar/Maestro)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/aryansinghnagar/Maestro)](https://github.com/aryansinghnagar/Maestro/releases)

## Features

- **Adaptive Performance Tiers (T0–T3)** — Automatic zero-config dynamic scaling from Ultra (T0: 60 FPS, FP16 model, full HUD) to Minimal (T3: 10 FPS, INT8 model, battery-saver mode) based on real-time hardware capabilities, CPU load, and battery/thermal state
- **21-point hand landmark tracking** — ONNX Runtime with multi-backend GPU acceleration (CUDA / CoreML / TensorRT / DirectML)
- **Cross-platform OS input** — Linux (uinput/X11/Wayland), macOS (CGEvent), Windows (SendInput)
- **FSM-based gesture recognition** with custom gestures via DTW
- **On-device processing** — no data leaves your computer (privacy by design)
- **Plugin system** with pluggy-based hooks and process isolation
- **Accessibility features** — tremor compensation, voice control (Vosk, offline), high contrast themes, screen reader support
- **Trigger conditions DSL** — context-aware gestures (per-app, per-time, per-display, per-audio-state)
- **Per-device profiles** — different gestures for laptop webcam vs external camera
- **Multi-monitor and HiDPI** support
- **Privilege-separated input broker** with Win32 process token SID auth, per-method rate limiting, and audit log verification
- **TUF-signed auto-updates** with threshold=3
- **GDPR compliance** — data export and erasure APIs

## Quick Start

```bash
# Install
pip install gesture-controller

# Run
maestro
```

## Installation

See [INSTALL.md](INSTALL.md) for detailed platform-specific instructions.

### Platform prerequisites

- **Linux:** `sudo usermod -aG input $USER` (for uinput), then log out and back in
- **macOS:** Grant camera permission on first launch
- **Windows:** Install Visual C++ Redistributable

## Documentation

Full documentation at **https://aryansinghnagar.github.io/Maestro/**

- [Getting Started](https://aryansinghnagar.github.io/Maestro/getting-started/)
- [User Guide](https://aryansinghnagar.github.io/Maestro/user-guide/)
- [Configuration](https://aryansinghnagar.github.io/Maestro/configuration/)
- [Architecture](https://aryansinghnagar.github.io/Maestro/architecture/)
- [Plugin Development](https://aryansinghnagar.github.io/Maestro/plugin-development/)
- [API Reference](https://aryansinghnagar.github.io/Maestro/api-reference/)

## Development

```bash
git clone https://github.com/aryansinghnagar/Maestro.git
cd Maestro
uv sync --frozen  # Install dev deps
uv run pytest     # Run tests
uv run maestro    # Run from source
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Developer Guide](https://aryansinghnagar.github.io/Maestro/developer-guide/) for details.

## Performance

| Metric | Value |
|---|---|
| E2E latency (P50, GPU) | <15ms |
| E2E latency (P50, CPU) | <30ms |
| Binary size | <25MB |
| Memory usage | <200MB |
| Cold start | <1.5s |

## License

[AGPL-3.0-or-later](LICENSE)

## Privacy

See [PRIVACY.md](PRIVACY.md). Maestro processes all data on-device. No camera frames, hand landmarks, or voice audio leave your computer.

## Security

See [SECURITY.md](SECURITY.md). To report a vulnerability, email security@aryansinghnagar.dev (PGP key in SECURITY.md).

## Acknowledgements

- [MediaPipe](https://developers.google.com/mediapipe) by Google — hand landmark model
- [ONNX Runtime](https://onnxruntime.ai/) by Microsoft — inference engine
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) by Riverbank Computing — GUI framework
- [pluggy](https://pypi.org/project/pluggy/) by Holger Krekel — plugin system
- [Vosk](https://alphacephei.com/vosk/) by Alpha Cephei — offline speech recognition
