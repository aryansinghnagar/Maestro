# Maestro Plugin Development Guide

Maestro features a plugin architecture supporting both Python plugins (powered by `pluggy`) and WASM sandboxed plugins (powered by `wasmtime`).

---

## Python Plugin Structure

A Python plugin is a single `.py` file placed inside `~/.config/maestro/plugins/`:

```python
"""
name: Zoom Control Plugin
version: 1.0.0
description: Maps gestures to Zoom meeting controls
author: Developer
"""

from gesture_controller.plugins import hookimpl

@hookimpl
def on_gesture_triggered(gesture_name: str, action: str) -> None:
    print(f"[Zoom Plugin] Gesture detected: {gesture_name}")

@hookimpl
def on_plugin_loaded() -> None:
    print("[Zoom Plugin] Loaded successfully")
```

---

## Security & RestrictedPython

All dynamic Python plugins are inspected at load time by `RestrictedPython`:
- Disallowed constructs: `__import__`, `eval`, `exec`, direct `open()` file writes outside plugin directory.
- Plugins execute inside isolated namespace environments.

---

## WASM Plugins

WASM plugins reside in a subfolder containing a `maestro.toml` manifest and a `.wasm` binary:

```toml
[plugin]
name = "custom-wasm-filter"
version = "0.1.0"
description = "High-performance landmark filter"
author = "Dev"
entry = "filter.wasm"
```
