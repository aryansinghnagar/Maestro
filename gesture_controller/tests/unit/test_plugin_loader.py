import sys
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import jsonschema

from gesture_controller.core.event_bus import EventBus
import gesture_controller.plugins.plugin_loader as plugin_loader
from gesture_controller.plugins.plugin_loader import PluginLoader, PluginLoadError, Plugin


@pytest.fixture
def mock_event_bus() -> MagicMock:
    return MagicMock(spec=EventBus)


@pytest.fixture
def temp_plugin_dirs(tmp_path: Path) -> Path:
    # Backup original PLUGIN_DIRS
    old_dirs = plugin_loader.PLUGIN_DIRS.copy()

    # Configure to use temp dir
    plugin_loader.PLUGIN_DIRS = [tmp_path]
    yield tmp_path

    # Restore
    plugin_loader.PLUGIN_DIRS = old_dirs


def test_load_valid_plugin(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    plugin_content = """
PLUGIN_META = {
    "name": "test-plugin",
    "version": "1.2.3",
    "description": "Mock plugin",
    "author": "tester"
}

GESTURE_DEFINITIONS = [
    {
        "name": "MockGesture",
        "type": "static",
        "priority": 5,
        "states": [
            {
                "id": "Idle",
                "transitions": []
            }
        ]
    }
]

ACTION_HANDLERS = {
    "CustomAction:Test": lambda: "executed"
}
"""
    plugin_path = temp_plugin_dirs / "valid_plugin.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    plugins = loader.discover_all()

    assert len(plugins) == 1
    plugin = plugins[0]
    assert plugin.meta["name"] == "test-plugin"
    assert plugin.meta["version"] == "1.2.3"
    assert len(plugin.gestures) == 1
    assert plugin.gestures[0]["name"] == "MockGesture"
    assert "CustomAction:Test" in plugin.actions
    assert plugin.actions["CustomAction:Test"]() == "executed"


def test_reject_plugin_missing_meta(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    plugin_content = """
# Missing PLUGIN_META completely
GESTURE_DEFINITIONS = []
"""
    plugin_path = temp_plugin_dirs / "invalid_plugin.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    plugins = loader.discover_all()
    # Loader should skip invalid plugin and not crash
    assert len(plugins) == 0


def test_reject_plugin_invalid_meta_schema(
    temp_plugin_dirs: Path, mock_event_bus: MagicMock
) -> None:
    plugin_content = """
# name is missing from meta (required)
PLUGIN_META = {
    "version": "1.0.0"
}
"""
    plugin_path = temp_plugin_dirs / "invalid_schema.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    plugins = loader.discover_all()
    assert len(plugins) == 0


def test_skip_prefixed_files(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    plugin_content = """
PLUGIN_META = {
    "name": "ignored",
    "version": "1.0.0"
}
"""
    # prefix with _
    plugin_path = temp_plugin_dirs / "_ignored_plugin.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    plugins = loader.discover_all()
    assert len(plugins) == 0


def test_duplicate_plugin_names(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    # Two files declaring the same plugin name
    plugin_1 = """
PLUGIN_META = {"name": "duplicate-name", "version": "1.0"}
"""
    plugin_2 = """
PLUGIN_META = {"name": "duplicate-name", "version": "2.0"}
"""
    with open(temp_plugin_dirs / "p1.py", "w") as f:
        f.write(plugin_1)
    with open(temp_plugin_dirs / "p2.py", "w") as f:
        f.write(plugin_2)

    loader = PluginLoader(mock_event_bus)
    plugins = loader.discover_all()
    # Only the first alphabetical file (p1) should be loaded, p2 skipped as duplicate name
    assert len(plugins) == 1
    assert plugins[0].meta["version"] == "1.0"


def test_get_all_gestures_merging(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    plugin_1 = """
PLUGIN_META = {"name": "p1", "version": "1.0"}
GESTURE_DEFINITIONS = [{"name": "G1", "type": "static", "states": [{"id": "Idle"}]}]
"""
    plugin_2 = """
PLUGIN_META = {"name": "p2", "version": "1.0"}
GESTURE_DEFINITIONS = [{"name": "G2", "type": "static", "states": [{"id": "Idle"}]}]
"""
    with open(temp_plugin_dirs / "p1.py", "w") as f:
        f.write(plugin_1)
    with open(temp_plugin_dirs / "p2.py", "w") as f:
        f.write(plugin_2)

    loader = PluginLoader(mock_event_bus)
    loader.discover_all()

    gestures = loader.get_all_gestures()
    assert len(gestures) == 2
    names = [g["name"] for g in gestures]
    assert "G1" in names
    assert "G2" in names


def test_get_action_handler(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    plugin_content = """
PLUGIN_META = {"name": "p1", "version": "1.0"}
ACTION_HANDLERS = {"Media:Mute": lambda: "muted"}
"""
    with open(temp_plugin_dirs / "p1.py", "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    loader.discover_all()

    handler = loader.get_action_handler("Media:Mute")
    assert handler is not None
    assert handler() == "muted"

    assert loader.get_action_handler("NonExistent") is None


def test_hot_reload_functionality(temp_plugin_dirs: Path, mock_event_bus: MagicMock) -> None:
    plugin_content_v1 = """
PLUGIN_META = {"name": "hot-plugin", "version": "1.0"}
GESTURE_DEFINITIONS = [{"name": "G1", "type": "static", "states": [{"id": "Idle"}]}]
"""
    plugin_path = temp_plugin_dirs / "hot_plugin.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content_v1)

    loader = PluginLoader(mock_event_bus)
    loader.discover_all()

    assert len(loader.get_all_gestures()) == 1
    assert loader._plugins["hot-plugin"].meta["version"] == "1.0"

    # Start reload watcher
    loader.start_hot_reload()

    # Modify plugin file (v2)
    plugin_content_v2 = """
PLUGIN_META = {"name": "hot-plugin", "version": "2.0"}
GESTURE_DEFINITIONS = [
    {"name": "G1", "type": "static", "states": [{"id": "Idle"}]},
    {"name": "G2", "type": "static", "states": [{"id": "Idle"}]}
]
"""
    # Sleep slightly to ensure filesystems register modifications clearly
    time.sleep(0.1)
    with open(plugin_path, "w") as f:
        f.write(plugin_content_v2)

    # Trigger watchdog event handler manually since filesystem sync might take too long in tests
    from watchdog.events import FileSystemEvent

    event = FileSystemEvent(str(plugin_path))
    event.event_type = "modified"

    # Retrieve loader's scheduler handler and fire event
    handlers = list(loader._observer._handlers.values())[0]
    list(handlers)[0].on_modified(event)

    # Verify event published on event bus and state reloaded
    mock_event_bus.publish.assert_called_with("plugin_reloaded", "hot-plugin")
    assert loader._plugins["hot-plugin"].meta["version"] == "2.0"
    assert len(loader.get_all_gestures()) == 2

    # Stop hot reload
    loader.stop_hot_reload()


def test_plugin_ast_sandbox_fails_without_permission(
    temp_plugin_dirs: Path, mock_event_bus: MagicMock
) -> None:
    plugin_content = """
PLUGIN_META = {
    "name": "malicious-plugin",
    "version": "1.0",
    "permissions": []
}
import pyautogui
"""
    plugin_path = temp_plugin_dirs / "malicious_plugin.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    with pytest.raises(PluginLoadError, match="Unauthorized import"):
        loader._load_plugin(plugin_path)


def test_plugin_ast_sandbox_passes_with_permission(
    temp_plugin_dirs: Path, mock_event_bus: MagicMock
) -> None:
    plugin_content = """
PLUGIN_META = {
    "name": "authorized-plugin",
    "version": "1.0",
    "permissions": ["os:input"]
}
import pyautogui
"""
    plugin_path = temp_plugin_dirs / "authorized_plugin.py"
    with open(plugin_path, "w") as f:
        f.write(plugin_content)

    loader = PluginLoader(mock_event_bus)
    with patch("importlib.util.spec_from_file_location") as mock_spec_func:
        mock_spec = MagicMock()
        mock_spec.loader = MagicMock()
        mock_spec_func.return_value = mock_spec
        with patch.dict("sys.modules", {}):
            plugin = loader._load_plugin(plugin_path)
            assert plugin is not None
