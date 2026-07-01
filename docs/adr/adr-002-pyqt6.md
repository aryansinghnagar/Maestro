# ADR-002: PyQt6 over Electron for Desktop User Interface

## Status
Approved

## Context
The application requires a configuration settings interface, a translucent HUD overlay to display hand tracking feedback, and a system tray utility to control execution states (pause/resume). 

Choosing an appropriate framework impacts binary size, system resource utilization (memory/CPU), and cross-platform native capability (tray integration, transparency masks).

## Decision
We choose PyQt6 for all UI components. 

## Consequences
- **Binary Size & Footprint:** Reduces compiled application size to under 80MB (compared to >150MB for Chromium-bundled Electron apps) and keeps idle memory under 40MB.
- **Native Tray & Window Attributes:** Provides reliable cross-platform system tray icon manipulation and transparent frameless window creation (HUD overlay) using Qt's `Qt.WindowType.FramelessWindowHint` and `Qt.WindowType.WindowStaysOnTopHint`.
- **Packaging:** PyInstaller natively packages PyQt6 modules with exclusion lists for unused libraries.
