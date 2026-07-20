# Maestro User Guide

This guide covers daily operation, gesture controls, voice commands, custom gesture recording, and system tray management.

---

## Operating Modes & System Tray Interface

Maestro runs discreetly in your system tray:

- **System Tray Icon**: Indicates current status (Active, Paused, or Camera Disconnected).
- **Context Menu Options**:
  - **Pause / Resume Recognition**: Toggle gesture detection on or off instantly.
  - **Settings**: Open the full GUI configuration window.
  - **Record Custom Gesture**: Launch the DTW custom gesture recorder wizard.
  - **Tremor Calibration**: Run live hand stability calibration.
  - **Crash Reports & Diagnostics**: Inspect crash history and export sanitized diagnostic ZIP archives.
  - **Quit**: Safely stop recognition threads and exit.

---

## Built-In Hand Gestures

Maestro includes built-in state machine gestures:

| Gesture Name | Hand Pose | Default Trigger Action |
|---|---|---|
| **SwipeLeft** | Open hand swiping left | KeyPress `Ctrl+Shift+Tab` / Previous Tab |
| **SwipeRight** | Open hand swiping right | KeyPress `Ctrl+Tab` / Next Tab |
| **SwipeUp** | Open hand swiping upward | OS `ShowDesktop` / Minimize All |
| **SwipeDown** | Open hand swiping downward | OS `SwitchWindow` / Task View |
| **Fist** | Clenched fist held for >300ms | OS `MinimizeActiveWindow` |
| **HoldFist** | Clenched fist held >1000ms | Custom Action / Lock |
| **Continuous Scroll** | Pinch/palm relative vertical motion | Continuous `MouseScroll` |

---

## Voice Commands Engine

Maestro includes an offline speech recognition engine powered by **Vosk**.

### Enabling Voice Control
1. Open **Settings → General**.
2. Check **Enable Voice Control (offline, Vosk)**.
3. If necessary, click **Download Voice Model (~50MB)** to automatically install the lightweight Vosk model.

### Wake-Word & Cooldown
- **Default Wake Word**: `"maestro"` (configurable in `config.yaml`).
- **Wake Cooldown**: Once the wake word is spoken (e.g., `"maestro swipe left"`), a 5-second active window opens during which subsequent phrases do not require re-stating the wake word.
- **Built-in Spoken Commands**:
  - `"maestro swipe left"` → Triggers `SwipeLeft`
  - `"maestro swipe right"` → Triggers `SwipeRight`
  - `"maestro minimize"` → Triggers `MinimizeActiveWindow`
  - `"maestro next track"` → Triggers `MediaNext`
  - `"maestro volume up"` / `"volume down"` → Adjusts volume

---

## Recording Custom Gestures (DTW)

To create personalized gestures:
1. Right-click the system tray icon and choose **Record Custom Gesture**.
2. Name your gesture (e.g. `MyCustomWave`) and select the action to bind (e.g. `KeyPress:Ctrl+C`).
3. Perform the gesture 3 times in front of the camera when prompted.
4. Maestro will construct a Dynamic Time Warping (DTW) template and save it to `~/.config/maestro/templates/`.
