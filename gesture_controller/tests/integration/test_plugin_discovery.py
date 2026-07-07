import pytest
from pathlib import Path
from unittest.mock import MagicMock
import gesture_controller.plugins.plugin_loader as plugin_loader
from gesture_controller.plugins.plugin_loader import PluginLoader
from gesture_controller.core.event_bus import EventBus


def test_plugin_discovery_integration(tmp_path: Path) -> None:
    # 1. Setup mock plugin file in temp folder
    plugin_name = "integration-plugin"
    plugin_code = f"""
PLUGIN_META = {{
    "name": "{plugin_name}",
    "version": "0.1.0",
    "description": "Integration test plugin",
    "author": "integration-runner"
}}

GESTURE_DEFINITIONS = [
    {{
        "name": "IntegrationGesture",
        "type": "static",
        "priority": 1,
        "states": [
            {{
                "id": "Idle",
                "transitions": []
            }}
        ]
    }}
]
"""
    plugin_file = tmp_path / "integration_plugin.py"
    with open(plugin_file, "w") as f:
        f.write(plugin_code)

    # 2. Redirect PluginLoader plugin directories to tmp_path
    old_dirs = plugin_loader.PLUGIN_DIRS.copy()
    plugin_loader.PLUGIN_DIRS = [tmp_path]

    try:
        mock_bus = MagicMock(spec=EventBus)
        loader = PluginLoader(mock_bus)

        # 3. Discover
        plugins = loader.discover_all()
        assert len(plugins) == 1
        assert plugins[0].meta["name"] == plugin_name

        # 4. Check gesture aggregation
        gestures = loader.get_all_gestures()
        assert len(gestures) == 1
        assert gestures[0]["name"] == "IntegrationGesture"

    finally:
        # Restore original directories
        plugin_loader.PLUGIN_DIRS = old_dirs
