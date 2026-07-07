# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-07

### Added
- **Native OS Input Injection**: Completely replaced `pyautogui` keyboard/mouse simulation with direct native Win32 `SendInput` and `SetCursorPos` ctypes injections for Windows (ADR-005).
- **RestrictedPython Sandboxing**: Integrated compile-time RestrictedPython validation checks for all dynamic third-party plugins.
- **Structured Latency Metrics**: Implemented a thread-safe `MetricsCollector` emitting detailed latency counters, gauges, and p50/p90/p99 histograms to structlog.
- **Supply-Chain Security Workflows**: Configured GHA builder workflow compiling CycloneDX SBOM dynamically and generating SLSA build provenance.
- **Automated Fuzzing**: Integrated scheduled nightly Atheris fuzzing targets.
- **Strict Typing Compliance**: Enforced strict mypy type safety rules (`strict = true`) across all core business logic files.

### Changed
- Refactored PyQt6 mock boundaries to use function-scoped, autouse pytest `monkeypatch` fixtures instead of process-global patching.

## [0.1.0] - 2026-07-03

### Added
- Multi-process SharedMemory camera stream and landmark extractor pipeline.
- One-Euro vector low-pass filter with NaN/Inf recovery.
- FSM-driven gesture recognition engine with AST-safe conditions parser.
- Custom template dynamic time warping sequence matching.
- Cross-platform OS input simulation controllers (Windows, macOS Quartz, Linux Wayland `/dev/uinput`).
- PyQt6 system tray icon, overlay HUD, settings control panel, and custom gesture recorder.
- Dynamic plugin system with hot reloading.
- Comprehensive unit and integration test suite passing on all major platforms.
