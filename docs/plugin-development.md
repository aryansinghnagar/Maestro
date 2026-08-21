# Maestro Plugin Development Guide

Maestro features an extensible plugin architecture that enables developers to define custom gesture state machines, register action handlers, and integrate external applications using either **Python plugins** or sandboxed **WebAssembly (WASM)** modules.

---

## 1. Plugin Types & Execution Models

| Capability | Python Plugins (`.py`) | WASM Plugins (`.wasm`) |
|---|---|---|
| **Runtime Engine** | CPython with `RestrictedPython` AST inspection | `wasmtime` bytecode sandbox |
| **Sandboxing** | AST-enforced namespace isolation | Hardware-isolated memory sandbox |
| **Performance** | Native Python speed | Near-native compiled execution |
| **Use Cases** | Custom FSM gesture rules, OS hooks | High-throughput filters, custom DSP |
| **Location** | `~/.config/maestro/plugins/*.py` | `~/.config/maestro/plugins/<name>/` |

---

## 2. Python Plugin Structure

A Python plugin is a single `.py` file placed inside the user plugin directory. It declares metadata, state machine rules, and optional action callbacks:

```python
"""
name: Zoom Control Plugin
version: 1.0.0
description: Maps custom hand poses to Zoom meeting shortcuts
author: Community Contributor
"""

PLUGIN_META = {
    "name": "zoom-controls",
    "version": "1.0.0",
    "description": "Zoom meeting hand gestures for mute and camera toggle",
    "author": "Community Contributor",
    "permissions": ["os_input", "notifications"],
}

GESTURE_DEFINITIONS = [
    {
        "name": "MuteTogglePose",
        "type": "static",
        "priority": 15,
        "states": [
            {
                "id": "Idle",
                "transitions": [
                    {
                        "to": "PoseActive",
                        "condition": "index_extended == True and middle_extended == True and ring_extended == False and pinky_extended == False",
                    }
                ],
            },
            {
                "id": "PoseActive",
                "min_duration_ms": 300,
                "max_duration_ms": 1500,
                "transitions": [
                    {"to": "Trigger", "condition": "True"},
                    {"to": "Idle", "condition": "index_extended == False", "abort": True},
                ],
            },
            {
                "id": "Trigger",
                "is_terminal": True,
                "action": "KeyPress:Alt+A",  # Zoom default toggle mute shortcut
                "cooldown_ms": 1200,
            },
        ],
    }
]

def on_plugin_loaded():
    """Invoked when Maestro successfully initializes the plugin."""
    pass

def on_plugin_unloaded():
    """Invoked during clean daemon teardown."""
    pass
```

---

## 3. Security & `RestrictedPython` Enforcement

To protect users against untrusted or malicious community plugins, Maestro parses and validates Python plugins through `RestrictedPython` before execution:

- **Forbidden Builtins**: `__import__`, `eval()`, `exec()`, `compile()`, `globals()`, `locals()`.
- **Restricted I/O**: Direct arbitrary filesystem writes (`open(..., 'w')`) and socket creation outside approved APIs are blocked.
- **Process Spawning**: Direct `os.system()` and unbounded `subprocess` calls are rejected.
- **Safe Sandboxing**: Plugins execute within a restricted global scope containing only approved math primitives, string formatting, and Maestro SDK hook interfaces.

---

## 4. WebAssembly (WASM) Plugin Architecture

For maximum isolation and multi-language support (Rust, C/C++, AssemblyScript, Zig), Maestro supports WASM modules executed via `wasmtime`:

### 4.1 Directory Structure

```
~/.config/maestro/plugins/my-wasm-filter/
├── maestro.toml
└── filter.wasm
```

### 4.2 Manifest (`maestro.toml`)

```toml
[plugin]
name = "custom-landmark-filter"
version = "0.1.0"
description = "Kalman landmark filtering compiled to WASM"
author = "Vision Research Lab"
entry = "filter.wasm"

[permissions]
memory_limit_mb = 16
execution_timeout_ms = 5
```

### 4.3 Exported WASM Interface

WASM binaries export standard lifecycle and processing functions:

```rust
// Example in Rust compiled to wasm32-wasi
#[no_mangle]
pub extern "C" fn init() -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn process_landmarks(ptr: *mut f32, count: usize) -> i32 {
    // Modify 21-point coordinates in-place
    0
}
```

---

## 5. Plugin Management CLI

Maestro provides dedicated CLI commands for managing plugins:

```bash
# Search registry
maestro search zoom

# Install a local or registry plugin
maestro install zoom-controls

# List installed plugins and status
maestro list-gestures

# Remove an installed plugin
maestro remove zoom-controls
```

