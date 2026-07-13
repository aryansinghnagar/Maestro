---
title: "DS-002: Event-Driven GUI Spec"
---

## DS-002: Event-Driven GUI Spec

**Confidence: High.** Full design spec for event-driven GUI.

### 97.1 Overview

Replace 60 FPS polling timer with event-driven updates via Qt signals. `GuiEventBridge` emits signals only when state changes.

### 97.2 Architecture

```
Engine Thread                    GUI Thread
    │                                │
    ├─ raw_landmarks event ──────────┤ (sync, ultra-low-latency)
    │                                ├─ GuiEventBridge._on_landmarks()
    │                                ├─ emit landmarks_updated signal
    │                                ├─ OverlayHUD.set_hand_data()
    │                                └─ QWidget.update() (only if data changed)
    │                                │
    ├─ gesture_triggered event ──────┤ (async)
    │                                ├─ GuiEventBridge._on_gesture()
    │                                ├─ emit gesture_triggered signal
    │                                ├─ OverlayHUD.show_action_feedback()
    │                                └─ TrayController.update_status()
    │                                │
    ├─ config_changed event ─────────┤ (async)
    │                                ├─ GuiEventBridge._on_config_changed()
    │                                ├─ emit config_changed signal
    │                                └─ SettingsWindow.reload()
    │                                │
    ├─ engine_started event ─────────┤ (async)
    │                                ├─ GuiEventBridge._on_engine_started()
    │                                └─ TrayController.set_status("running")
    │                                │
    ├─ engine_stopped event ─────────┤ (async)
    │                                ├─ GuiEventBridge._on_engine_stopped()
    │                                └─ TrayController.set_status("idle")
    │                                │
    └─ error event ──────────────────┤ (async)
                                     ├─ GuiEventBridge._on_error()
                                     └─ TrayController.show_error()
```

### 97.3 Signals

```python
class GuiEventBridge(QObject):
    landmarks_updated = pyqtSignal(list)       # list[Hand]
    gesture_triggered = pyqtSignal(object)     # GestureEvent
    config_changed = pyqtSignal(dict)          # new config
    engine_started = pyqtSignal()
    engine_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)           # error message
    status_changed = pyqtSignal(str)           # "running", "paused", "error"
```

### 97.4 Subscribers

| Subscriber | Signal | Action |
|---|---|---|
| `OverlayHUD` | `landmarks_updated` | Set hand data; trigger repaint (only if changed) |
| `OverlayHUD` | `gesture_triggered` | Show gesture feedback animation |
| `TrayController` | `engine_started` | Set icon to "running" |
| `TrayController` | `engine_stopped` | Set icon to "idle" |
| `TrayController` | `gesture_triggered` | Show tray notification |
| `TrayController` | `error_occurred` | Show error notification |
| `SettingsWindow` | `config_changed` | Reload settings UI |
| `OnboardingWizard` | `engine_started` | Enable "Finish" button |

### 97.5 Change detection

To avoid unnecessary repaints:

```python
def _hands_changed(self, new: list[Hand], old: list[Hand]) -> bool:
    """Check if hands list changed."""
    if len(new) != len(old):
        return True
    for n, o in zip(new, old):
        if n.track_id != o.track_id:
            return True
        # Compare landmark positions (with tolerance)
        if any(abs(a - b) > 0.001 for a, b in zip(n.landmarks[0], o.landmarks[0])):
            return True
    return False
```

### 97.6 Performance impact

| Metric | Polling (current) | Event-driven (target) |
|---|---|---|
| Idle CPU% (no hands) | 5-10% | <1% |
| Active CPU% (with hands) | 10-15% | 5-10% |
| Repaint frequency (no hands) | 60 Hz | 0 Hz |
| Repaint frequency (with hands) | 60 Hz | 30 Hz (frame rate) |
| UI frame time | 16ms (always) | 5ms (when changes) |

---