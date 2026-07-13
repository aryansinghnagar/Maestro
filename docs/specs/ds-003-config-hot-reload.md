---
title: "DS-003: Config Hot-Reload Spec"
---

## DS-003: Config Hot-Reload Spec

### 98.1 Overview

Config changes take effect without restart (where possible). Some changes require restart (camera, backend).

### 98.2 Hot-reloadable vs restart-required

| Config key | Hot-reloadable | Reason |
|---|---|---|
| `filtering.one_euro.min_cutoff` | ✅ | Filter just reads new value |
| `filtering.one_euro.beta` | ✅ | Same |
| `filtering.tremor.enabled` | ✅ | Toggle |
| `engine.max_hands` | ❌ | Requires SHM resize |
| `camera.fps_target` | ❌ | Requires camera process restart |
| `camera.device_id` | ❌ | Requires camera process restart |
| `engine.inference_backend` | ❌ | Requires backend recreation |
| `hud.enabled` | ✅ | Toggle overlay |
| `hud.opacity` | ✅ | Update paint |
| `triggers.conditions` | ✅ | Reload action dispatcher |
| `voice.enabled` | ✅ | Toggle voice listener |
| `a11y.high_contrast` | ✅ | Re-apply theme |
| `a11y.reduced_motion` | ✅ | Toggle animations |

### 98.3 Architecture

```
Config file (YAML)
       ↓
watchdog observer (file watcher)
       ↓
ConfigManager.reload()
       ↓
EventBus.publish("config_changed", old, new)
       ↓
Subscribers:
  - InferencePipeline (filter params)
  - ActionDispatcher (trigger conditions)
  - OverlayHUD (HUD config)
  - SettingsWindow (UI refresh)
  - VoiceListener (enable/disable)
  - ThemeManager (re-apply theme)
```

### 98.4 Subscriber pattern

```python
class InferencePipeline:
    def __init__(self, ..., event_bus):
        # ...
        event_bus.subscribe("config_changed", self._on_config_changed)

    def _on_config_changed(self, event):
        new = event["new"]

        # Hot-swappable: filter params
        new_min_cutoff = self._get_nested(new, "filtering.one_euro.min_cutoff", 1.0)
        new_beta = self._get_nested(new, "filtering.one_euro.beta", 0.0)
        for f in self._filters.values():
            f.min_cutoff = new_min_cutoff
            f.beta = new_beta

        # Requires restart: backend
        new_backend = self._get_nested(new, "engine.inference_backend", "auto")
        if new_backend != self._backend.name and new_backend != "auto":
            logger.warning(f"Backend change to {new_backend} requires restart")
```

### 98.5 Verification

```python
def test_filter_params_hot_reload(config_manager, inference_pipeline):
    """Filter params should update without restart."""
    config_manager.set("filtering.one_euro.min_cutoff", 1.0)
    assert inference_pipeline._filters[0].min_cutoff == 1.0

    config_manager.set("filtering.one_euro.min_cutoff", 2.0)
    config_manager.reload()

    assert inference_pipeline._filters[0].min_cutoff == 2.0
```

---