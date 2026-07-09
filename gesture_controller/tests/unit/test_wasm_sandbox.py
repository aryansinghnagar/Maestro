import pytest
from pathlib import Path
import shutil
import tempfile
import json
import wasmtime

from gesture_controller.plugins.plugin_loader import PluginLoader, PluginLoadError
from gesture_controller.core.event_bus import EventBus


@pytest.fixture
def temp_plugin_dir() -> Path:
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def create_wasm_plugin(
    directory: Path, name: str, wat_content: str, capabilities: dict
) -> Path:
    plugin_path = directory / name
    plugin_path.mkdir(parents=True, exist_ok=True)

    # Write maestro.toml
    manifest = {
        "plugin": {
            "name": name,
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Tester",
        },
        "capabilities": capabilities,
    }



    # Write manually to avoid dependency conflicts
    toml_str = f"""[plugin]
name = "{name}"
version = "1.0.0"
description = "Test plugin"
author = "Tester"

[capabilities]
"""
    for k, v in capabilities.items():
        val = "true" if v else "false"
        toml_str += f'"{k}" = {val}\n'

    with open(plugin_path / "maestro.toml", "w") as f:
        f.write(toml_str)

    # Write WAT file
    with open(plugin_path / "plugin.wat", "w") as f:
        f.write(wat_content)

    return plugin_path


def test_wasm_load_and_init(temp_plugin_dir: Path) -> None:
    wat = """
    (module
      (import "maestro" "register_gesture" (func $register (param i32 i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "{\\"name\\": \\"SwipeLeft\\", \\"type\\": \\"dynamic\\", \\"states\\": [{\\"id\\": \\"idle\\"}]}")
      (func (export "init")
        i32.const 0
        i32.const 68
        call $register
      )
    )
    """
    create_wasm_plugin(
        temp_plugin_dir,
        "test_gesture_plugin",
        wat,
        {"os:input": True, "config:read": True},
    )

    event_bus = EventBus()
    loader = PluginLoader(event_bus)

    # Override plugin directories for discovery
    from unittest.mock import patch

    with patch("gesture_controller.plugins.plugin_loader.PLUGIN_DIRS", [temp_plugin_dir]):
        plugins = loader.discover_all()
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin.meta["name"] == "test_gesture_plugin"
        assert len(plugin.gestures) == 1
        assert plugin.gestures[0]["name"] == "SwipeLeft"


def test_wasm_permission_denied_trigger_action(temp_plugin_dir: Path) -> None:
    wat = """
    (module
      (import "maestro" "trigger_action" (func $trigger (param i32 i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "VolumeUp")
      (func (export "init")
        i32.const 0
        i32.const 8
        call $trigger
      )
    )
    """
    # capabilities "os:input" is False
    create_wasm_plugin(temp_plugin_dir, "test_blocked_plugin", wat, {"os:input": False})

    event_bus = EventBus()
    loader = PluginLoader(event_bus)

    from unittest.mock import patch

    with patch("gesture_controller.plugins.plugin_loader.PLUGIN_DIRS", [temp_plugin_dir]):
        # Since init triggers trigger_action which lacks permission, load should fail with PluginLoadError
        plugin_path = temp_plugin_dir / "test_blocked_plugin"
        with pytest.raises(PluginLoadError) as exc_info:
            loader._load_wasm_plugin(plugin_path)
        assert "Permission Denied" in str(exc_info.value)


def test_wasm_on_gesture_callback(temp_plugin_dir: Path) -> None:
    # A plugin that listens to gestures and triggers "ActionSuccess" if gesture matches
    wat = """
    (module
      (import "maestro" "trigger_action" (func $trigger (param i32 i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "ActionSuccess")
      (func (export "on_gesture") (param $name_ptr i32) (param $name_len i32) (param $hand i32) (param $conf f32) (param $ts i64)
        i32.const 0
        i32.const 13
        call $trigger
      )
    )
    """
    create_wasm_plugin(temp_plugin_dir, "test_callback_plugin", wat, {"os:input": True})

    event_bus = EventBus()
    loader = PluginLoader(event_bus)

    # Capture triggered actions
    triggered_actions = []

    def on_action(action: str) -> None:
        triggered_actions.append(action)

    event_bus.subscribe("action_triggered", on_action)

    from unittest.mock import patch
    import time

    with patch("gesture_controller.plugins.plugin_loader.PLUGIN_DIRS", [temp_plugin_dir]):
        plugins = loader.discover_all()
        assert len(plugins) == 1
        plugin = plugins[0]

        # Trigger mock gesture callback on the wrapper
        plugin.module.on_gesture("SwipeRight", "Right", 0.99, 12345678)

        # Wait for async EventBus delivery
        time.sleep(0.05)

        assert "ActionSuccess" in triggered_actions
