# Maestro User Guide

This guide provides exhaustive instructions for operating Maestro, configuring gestures, recording custom temporal motions, leveraging offline voice commands, calibrating assistive features, and managing per-application profiles.

---

## 1. Operating Modes & System Tray Interface

Maestro runs continuously in your system background and manages its state via a system tray icon:

```
  [Tray Icon]
   ├─ Status: Active (Green) / Paused (Yellow) / Error (Red)
   ├─ Pause / Resume Recognition
   ├─ Settings...
   ├─ Record Custom Gesture...
   ├─ Tremor Calibration...
   ├─ Performance Monitor...
   ├─ Crash Reports & Diagnostics...
   └─ Quit
```

### System Tray Context Menu

- **Pause / Resume Recognition**: Instantly freeze or re-enable the gesture recognition loop without shutting down the daemon.
- **Settings**: Open the tabbed configuration window (General, Gestures, Vision & Tiers, Voice, Profiles, Plugins, Security).
- **Record Custom Gesture**: Launch the 3-repetition Dynamic Time Warping (DTW) recording wizard.
- **Tremor Calibration**: Run live jitter measurement to automatically tune One-Euro filtering parameters.
- **Performance Monitor**: Open the floating diagnostics window displaying real-time FPS, P50/P99 frame latency, CPU load, and active hardware tier (T0–T3).
- **Crash Reports & Diagnostics**: Inspect scrubbed crash traces and export sanitized `.zip` bundles.
- **Quit**: Gracefully flush audit logs, close shared memory buffers, and exit.

---

## 2. Built-In Gesture Catalog

Maestro uses a Finite State Machine (FSM) condition compiler to recognize canonical gestures:

| Gesture Name | Physical Hand Pose | Default Trigger Action | Notes / Cooldown |
|---|---|---|---|
| **SwipeLeft** | Open hand swiping rapidly right-to-left | `KeyPress:Ctrl+Shift+Tab` | Previous browser/editor tab |
| **SwipeRight** | Open hand swiping rapidly left-to-right | `KeyPress:Ctrl+Tab` | Next browser/editor tab |
| **SwipeUp** | Open hand pushing upward | `OS:ShowDesktop` | Minimizes all open windows |
| **SwipeDown** | Open hand pushing downward | `OS:SwitchWindow` | Opens Task View / Mission Control |
| **Fist** | Clenched fist held for >300ms | `OS:MinimizeActiveWindow` | Minimizes current foreground window |
| **HoldFist** | Clenched fist held for >1000ms | `OS:LockWorkstation` | Locks desktop session |
| **Pinch** | Thumb tip touching index tip (<35mm) | `MouseClick:Left` | Single left mouse click |
| **DoublePinch** | Two rapid pinches within 400ms | `MouseClick:Double` | Double click |
| **Continuous Scroll** | Pinch held while moving hand vertically | `MouseScroll:Vertical` | Proportional continuous scroll |
| **Two-Hand Spread** | Both palms moving away from each other | `KeyPress:Ctrl+Plus` | Zoom in |
| **Two-Hand Pinch** | Both palms moving toward each other | `KeyPress:Ctrl+Minus` | Zoom out |

---

## 3. Recording Custom Gestures (DTW)

For specialized hand movements not covered by built-in FSM rules, Maestro provides a **Dynamic Time Warping (DTW)** template recorder:

1. Right-click the system tray icon and select **Record Custom Gesture**.
2. **Name & Binding**:
   - Provide a unique identifier (e.g. `WaveHello` or `ThreeFingerTap`).
   - Select the target action (e.g. `KeyPress:Win+D`, `Media:PlayPause`, or custom script).
3. **Recording Phase**:
   - Perform the gesture in front of the camera **3 distinct times** when prompted by the countdown timer.
   - Maestro normalizes 21-point hand landmarks for scale, rotation, and translation invariance, computing a multi-frame template sequence.
4. **Template Storage**:
   - The verified template is saved in JSON format under `~/.config/maestro/templates/` (or `%APPDATA%\maestro\templates\` on Windows).
5. **Template Sharing**:
   - Export custom templates using the CLI:
     ```bash
     maestro export-gesture WaveHello --output wave.json
     maestro import-gesture wave.json
     ```

---

## 4. Offline Voice Commands (Vosk)

Maestro integrates an offline speech recognition worker that pairs voice intents with gesture actions.

### Setup & Activation
1. Open **Settings → Voice**.
2. Check **Enable Voice Control**.
3. If the offline model is missing, click **Download Voice Model (~50MB)** or execute:
   ```bash
   maestro download-voice-model
   ```

### Wake-Word Mechanics
- **Default Wake-Word**: `"maestro"` (configurable in `config.yaml`).
- **Wake Window**: When `"maestro"` is spoken, an active listening window opens for 5 seconds (indicated by a cyan ring in the HUD overlay). Any command spoken during this window executes immediately without repeating the wake word.

### Standard Spoken Commands

| Spoken Phrase | Triggered Action |
|---|---|
| `"maestro swipe left"` / `"previous"` | `SwipeLeft` |
| `"maestro swipe right"` / `"next"` | `SwipeRight` |
| `"maestro minimize"` | `MinimizeActiveWindow` |
| `"maestro play"` / `"pause"` | `Media:PlayPause` |
| `"maestro volume up"` / `"volume down"` | Adjusts system audio volume |
| `"maestro pause recognition"` | Pauses the gesture tracking engine |

---

## 5. Assistive Features & Dwell Clicker

Maestro is designed to meet WCAG 2.2 AA accessibility standards and includes dedicated tools for users with motor tremors or limited mobility:

### Hands-Free Dwell Clicker
When enabled (**Settings → Accessibility → Dwell Clicker**):
- Hold your index finger steady over a target on screen for the configurable dwell duration (default: 800ms).
- A circular progress ring fills around the pointer.
- Upon completion, Maestro dispatches a native `LeftClick` at that coordinate.

### Live Tremor Calibration Wizard
- Launch **Tremor Calibration** from the system tray menu.
- Hold your hand stationary in front of the camera for 5 seconds while the calibrator samples coordinate variance.
- The algorithm calculates optimal `min_cutoff` and `beta` values for the One-Euro filter to suppress personal tremor frequencies while keeping cursor response crisp.

---

## 6. HUD Overlay & Performance Monitor

### Non-Intrusive HUD Overlay
- Renders directly over your desktop windows with configurable opacity (default 85%).
- Displays real-time 21-point landmark skeletal connections, active gesture name, and cooldown countdown rings.
- Can be toggled on/off in **Settings → Vision → Show HUD Overlay**.

### Live Performance Monitor
- Displays real-time metrics:
  - **Inference FPS** (Target: 30–60 FPS)
  - **End-to-End Latency** (P50 <15ms GPU / <30ms CPU)
  - **Hardware Tier** (T0: Ultra, T1: Balanced, T2: Power Saver, T3: Minimal)
  - **Memory Usage** (RSS MB)

---

## 7. Per-Application Profiles & Contextual Triggers

Maestro dynamically matches gestures based on the currently focused application window:

```yaml
profiles:
  auto_detect_app: true
  app_profiles:
    chrome.exe:
      SwipeLeft: "KeyPress:Ctrl+Shift+Tab"
      SwipeRight: "KeyPress:Ctrl+Tab"
      Fist: "KeyPress:Ctrl+W"
    vlc.exe:
      SwipeLeft: "KeyPress:Alt+Left"
      SwipeRight: "KeyPress:Alt+Right"
      Fist: "Media:PlayPause"
    code.exe:
      SwipeLeft: "KeyPress:Alt+Left"
      SwipeRight: "KeyPress:Alt+Right"
```

Whenever window focus switches (e.g. from VS Code to VLC), Maestro instantly adapts gesture mappings without user intervention.

---

## 8. Global Hotkeys & Panic Switch

To ensure absolute user control and safety, Maestro supports configurable global keyboard shortcuts:

- **Panic Kill-Switch (`Ctrl+Alt+Shift+Q`)**: Immediately terminates all input injection and shuts down the application.
- **Toggle Pause (`Ctrl+Alt+P`)**: Toggles recognition on/off.
- **Toggle HUD (`Ctrl+Alt+H`)**: Hides or shows the transparent desktop overlay.

