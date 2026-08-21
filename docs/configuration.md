# Maestro Configuration Reference

Maestro persists its configuration in human-readable YAML format with automatic schema validation, versioned migrations, and dynamic hot-reloading.

---

## 1. Configuration File Locations

Maestro follows standard OS directory conventions:

| Operating System | Default Configuration Path | Data / Templates Directory |
|---|---|---|
| **Windows** | `%APPDATA%\maestro\config.yaml` | `%LOCALAPPDATA%\maestro\templates\` |
| **Linux** | `~/.config/maestro/config.yaml` | `~/.local/share/maestro/templates/` |
| **macOS** | `~/Library/Application Support/maestro/config.yaml` | `~/Library/Application Support/maestro/templates/` |

> [!TIP]
> You can override the default configuration directory at any time by setting the `MAESTRO_CONFIG_DIR` environment variable.

---

## 2. Complete `config.yaml` Schema

Below is the fully annotated YAML configuration:

```yaml
# ==============================================================================
# Maestro Configuration File (Schema v1.2)
# ==============================================================================

app:
  language: "en"               # UI language ("en", "es", "fr", "de", "ja", "zh")
  onboarding_complete: true    # First-run onboarding completion status
  theme: "system"              # "system", "dark", "light", or "high_contrast"
  start_minimized: true        # Launch directly into system tray
  panic_hotkey: "ctrl+alt+shift+q"

engine:
  min_detection_confidence: 0.70  # Minimum confidence for initial palm detection
  min_tracking_confidence: 0.50   # Minimum confidence for landmark tracking
  max_hands: 2                    # Number of simultaneous hands (1 or 2)
  fps_cap: 30                     # Target camera capture FPS cap (10 - 60)
  global_cooldown_ms: 200.0       # Cooldown between sequential gesture triggers
  preferred_backend: "auto"       # "auto", "directml", "tensorrt", "coreml", "cpu"
  adaptive_tiers_enabled: true    # Automatic dynamic scaling (T0 - T3)

filtering:
  one_euro:
    min_cutoff: 1.0     # Minimum cutoff frequency (lower = smoother when slow)
    beta: 0.007         # Speed coefficient (higher = less lag during rapid movement)
    d_cutoff: 1.0       # Derivative cutoff frequency
  tremor:
    enabled: false
    window_size: 10
    max_displacement_px: 5.0

dwell_clicker:
  enabled: false
  dwell_time_ms: 800
  radius_px: 20
  action: "MouseClick:Left"

voice:
  enabled: false
  wake_word: "maestro"
  wake_window_seconds: 5.0
  model_path: "models/vosk-model-small-en-us-0.15"
  commands:
    - phrase: "swipe left"
      action: "KeyPress:Ctrl+Shift+Tab"
    - phrase: "swipe right"
      action: "KeyPress:Ctrl+Tab"
    - phrase: "minimize"
      action: "OS:MinimizeActiveWindow"
    - phrase: "play pause"
      action: "Media:PlayPause"

profiles:
  auto_detect_app: true
  default:
    SwipeLeft: "KeyPress:Ctrl+Shift+Tab"
    SwipeRight: "KeyPress:Ctrl+Tab"
    SwipeUp: "OS:ShowDesktop"
    SwipeDown: "OS:SwitchWindow"
    Fist: "OS:MinimizeActiveWindow"
  app_profiles:
    chrome.exe:
      SwipeLeft: "KeyPress:Ctrl+Shift+Tab"
      SwipeRight: "KeyPress:Ctrl+Tab"
      Fist: "KeyPress:Ctrl+W"
    vlc.exe:
      SwipeLeft: "KeyPress:Alt+Left"
      SwipeRight: "KeyPress:Alt+Right"
      Fist: "Media:PlayPause"

hud:
  enabled: true
  opacity: 0.85
  show_tracking_dots: true
  show_skeleton_lines: true
  show_progress_ring: true
  show_fps: false

broker:
  rate_limit_per_second: 30
  rate_limit_burst: 10
  audit_logging: true

updater:
  auto_check: true
  check_interval_hours: 24
  channel: "stable"    # "stable" or "beta"
```

---

## 3. Trigger Conditions DSL

Maestro supports contextual trigger conditions evaluated via a restricted, safe Abstract Syntax Tree (AST) evaluator. You can bind gestures conditionally based on runtime state:

### Supported Variables

| Variable | Type | Description | Example |
|---|---|---|---|
| `app_name` | string | Lowercase name of foreground application process | `app_name == "chrome.exe"` |
| `time_hour` | integer | Current 24-hour local clock hour (0–23) | `time_hour >= 18` |
| `display_count` | integer | Number of active desktop monitors | `display_count > 1` |
| `is_audio_playing` | boolean | Whether system media is currently active | `is_audio_playing == True` |
| `hand_count` | integer | Number of detected hands in frame | `hand_count == 2` |
| `handedness` | string | Primary hand classification (`"Left"` / `"Right"`) | `handedness == "Right"` |

### Example Conditional Expressions

```yaml
profiles:
  custom_conditions:
    - gesture: "SwipeLeft"
      condition: 'app_name == "chrome.exe" and display_count == 1'
      action: "KeyPress:Ctrl+Shift+Tab"
    - gesture: "SwipeLeft"
      condition: 'app_name == "chrome.exe" and display_count > 1'
      action: "KeyPress:Ctrl+Alt+Left"
```

---

## 4. Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `MAESTRO_CONFIG_DIR` | Custom directory containing `config.yaml` | Platform default |
| `MAESTRO_LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `MAESTRO_NO_GUI` | Run headless daemon mode without PyQt6 GUI | `0` |
| `MAESTRO_FORCE_TIER` | Lock performance tier (`T0`, `T1`, `T2`, `T3`) | Dynamic |
| `MAESTRO_PATCH_CDLL` | Apply Windows ctypes MediaPipe runtime fix | `1` |
| `QT_QPA_PLATFORM` | PyQt6 rendering platform (e.g. `offscreen` for headless CI) | Platform native |

---

## 5. Dynamic Hot-Reloading & Schema Migrations

- **Hot-Reloading**: Maestro runs a filesystem watcher (`watchdog`) monitoring `config.yaml`. Editing the file in any text editor updates running parameters in-memory instantly without dropping camera frames or restarting the process.
- **Config Migration**: When upgrading between Maestro releases, `config_migrator.py` automatically updates existing YAML files to the latest schema version while preserving custom gesture profiles and bindings.

