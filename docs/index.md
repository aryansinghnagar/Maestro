# Maestro

Welcome to the documentation for **Maestro**, a cross-platform desktop hand-gesture controller that translates hand movements captured by a standard webcam into native operating system input commands.

## Key Features

- **Platform Agnostic**: Runs natively on Windows, macOS, and Linux (Wayland/X11).
- **Zero-Latency Design**: Decoupled multi-threaded pipeline with atomic lock-free shared memory buffers.
- **Advanced Recognition**: Combined Finite State Machine (FSM) and Dynamic Time Warping (DTW) matching.
- **Privacy First**: Fully offline architecture. No camera frames or voice audio are transmitted off-device.
- **Secure Sandboxing**: Dynamic plugins execute in restricted WASM and AST-scanned environments.
