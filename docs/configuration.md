# Maestro Configuration Guide

Maestro persists configuration in human-readable YAML format located at:
- **Windows**: `%APPDATA%\maestro\config.yaml`
- **Linux / macOS**: `~/.config/maestro/config.yaml`

---

## Configuration Schema

Below is an annotated sample `config.yaml`:

```yaml
app:
  language: "en"             # Interface language ("en", "fr", "de", "ja")
  onboarding_complete: true  # Onboarding status flag

engine:
  min_detection_confidence: 0.7
  min_tracking_confidence: 0.5
  max_hands: 2
  fps_cap: 30
  global_cooldown_ms: 200.0

filtering:
  one_euro:
    min_cutoff: 1.0
    beta: 0.007
    d_cutoff: 1.0
  tremor:
    enabled: false
    window_size: 10
    max_displacement_px: 5.0

voice:
  enabled: true
  wake_word: "maestro"
  commands:
    - phrase: "open browser"
      gesture: "SwipeRight"

profiles:
  auto_detect_app: true
  app_profiles:
    chrome.exe:
      SwipeLeft: "KeyPress:Ctrl+Shift+Tab"
      SwipeRight: "KeyPress:Ctrl+Tab"
    vlc.exe:
      Fist: "Media:PlayPause"

hud:
  enabled: true
  opacity: 0.85
  show_tracking_dots: true
  show_progress_ring: true
```

---

## Hot-Reloading

Maestro watches `config.yaml` using `watchdog`. Changes made to `config.yaml` via text editor are automatically reloaded at runtime without requiring an application restart.
