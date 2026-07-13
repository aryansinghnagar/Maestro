---
title: "DS-004: Plugin SDK Spec"
---

## DS-004: Plugin SDK Spec

**Confidence: High.** Full spec for the Plugin SDK.

### 99.1 Overview

The Plugin SDK is the public API for third-party Maestro plugin developers.

### 99.2 Plugin anatomy

```
my-maestro-plugin/
├── pyproject.toml              # Plugin metadata + entry point
├── my_plugin/
│   ├── __init__.py            # Plugin instance + hookimpls
│   └── gestures.yaml          # Gesture definitions (optional)
├── maestro-plugin.toml        # Maestro-specific metadata
├── tests/
└── README.md
```

### 99.3 Plugin manifest (`maestro-plugin.toml`)

```toml
[plugin]
name = "vscode-gestures"
version = "0.1.0"
author = "Jane Doe <jane@example.com>"
description = "VS Code-specific gestures for Maestro"
license = "MIT"
homepage = "https://github.com/jane/maestro-vscode-gestures"

[plugin.compatibility]
maestro = ">=0.2.0"
python = ">=3.11"

[plugin.permissions]
network = false
filesystem = "read_only"
process = false
input_injection = false

[plugin.sandbox]
mode = "wasm"  # or "trusted"
```

### 99.4 Plugin entry point (`pyproject.toml`)

```toml
[project.entry-points."maestro.plugins"]
vscode-gestures = "my_plugin:PLUGIN_INSTANCE"
```

### 99.5 Plugin code

```python
# my_plugin/__init__.py
from maestro.core.plugin_manager import hookimpl

class MyPlugin:
    @hookimpl
    def get_gestures(self) -> list[dict]:
        return [
            {"name": "MyGesture", "type": "static", "condition": "...", "action": "..."}
        ]

    @hookimpl
    def on_load(self) -> None:
        print("Loaded!")

    @hookimpl
    def on_unload(self) -> None:
        print("Unloaded!")

PLUGIN_INSTANCE = MyPlugin()
```

### 99.6 Hook reference

| Hook | Signature | Returns | Purpose |
|---|---|---|---|
| `get_gestures()` | `() -> list[dict]` | Gesture definitions | Provide gestures |
| `get_action_handlers()` | `() -> dict[str, Callable]` | Action handlers | Custom actions |
| `on_load()` | `() -> None` | None | Initialization |
| `on_unload()` | `() -> None` | None | Cleanup |
| `resolve_action(gesture, context)` | `(str, dict) -> str \| None` | Action string | Custom resolution |
| `get_config_schema()` | `() -> dict` | JSON schema | Plugin config |
| `on_gesture(name, features)` | `(str, dict) -> dict \| None` | Optional action | React to gestures |
| `on_frame(hands, frame_num)` | `(list, int) -> None` | None | Per-frame hook (use sparingly) |
| `on_config_changed(config)` | `(dict) -> None` | None | React to config changes |

### 99.7 Permissions

Plugins declare required permissions in `maestro-plugin.toml`. The sandbox enforces these:

| Permission | Values | Effect |
|---|---|---|
| `network` | `true`, `false` | Allow/block network access |
| `filesystem` | `"none"`, `"read_only"`, `"read_write"` | File system access level |
| `process` | `true`, `false` | Allow/block subprocess |
| `input_injection` | `true`, `false` | Allow/block OS input injection |

If a plugin attempts an operation not in its permissions, the sandbox blocks it and logs a warning.

### 99.8 Testing

```python
# tests/test_plugin.py
import pytest
from my_plugin import MyPlugin

def test_get_gestures():
    plugin = MyPlugin()
    gestures = plugin.get_gestures()
    assert len(gestures) >= 1
    assert "name" in gestures[0]

def test_get_action_handlers():
    plugin = MyPlugin()
    handlers = plugin.get_action_handlers()
    assert isinstance(handlers, dict)
```

### 99.9 Distribution

```bash
# Build
uv build

# Publish to PyPI
uv publish

# Submit to Maestro marketplace
# (open PR to add to marketplace.json)
```

---