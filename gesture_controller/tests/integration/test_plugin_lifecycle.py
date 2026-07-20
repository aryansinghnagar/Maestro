"""Integration tests: Plugin lifecycle end-to-end (Sprint 15).

Tests the full sequence: install plugin from file → list → enable → disable
→ uninstall, verifying state at each step and event-bus events.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_PLUGIN_SRC = """\
PLUGIN_META = {
    "name": "integration-test-plugin",
    "version": "1.0.0",
    "description": "Integration lifecycle test plugin",
    "author": "Test",
    "permissions": [],
}
GESTURE_DEFINITIONS = []
ACTION_HANDLERS = {}
"""


@pytest.fixture()
def plugin_src(tmp_path) -> Path:
    """Write a minimal valid plugin file and return its path."""
    src = tmp_path / "integration_test_plugin.py"
    src.write_text(MINIMAL_PLUGIN_SRC, encoding="utf-8")
    return src


@pytest.fixture()
def manager(tmp_path):
    """Create a PluginManager with an isolated user plugin directory."""
    from gesture_controller.plugins.plugin_manager import PluginManager

    mock_bus = MagicMock()
    mock_config = MagicMock()
    mock_config.get.return_value = []

    mgr = PluginManager(mock_bus, mock_config)
    mgr._records = {}
    return mgr, mock_bus, tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPluginLifecycle:
    def test_install_then_list(self, manager, plugin_src) -> None:
        """Installed plugin appears in list_plugins()."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            record = mgr.install_from_path(plugin_src)

        assert record is not None
        assert record.name == "integration-test-plugin"
        names = [r.name for r in mgr.list_plugins()]
        assert "integration-test-plugin" in names

    def test_installed_plugin_enabled_by_default(self, manager, plugin_src) -> None:
        """Newly installed plugin is enabled."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            record = mgr.install_from_path(plugin_src)

        assert record is not None
        assert mgr.is_enabled("integration-test-plugin") is True

    def test_disable_installed_plugin(self, manager, plugin_src) -> None:
        """Disabling a plugin makes is_enabled() return False."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            mgr.install_from_path(plugin_src)

        result = mgr.disable("integration-test-plugin")
        assert result is True
        assert mgr.is_enabled("integration-test-plugin") is False

    def test_reenable_disabled_plugin(self, manager, plugin_src) -> None:
        """Re-enabling a disabled plugin restores is_enabled() to True."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            mgr.install_from_path(plugin_src)

        mgr.disable("integration-test-plugin")
        mgr.enable("integration-test-plugin")
        assert mgr.is_enabled("integration-test-plugin") is True

    def test_uninstall_removes_from_list(self, manager, plugin_src) -> None:
        """Uninstalling a plugin removes it from list_plugins()."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            mgr.install_from_path(plugin_src)
            result = mgr.uninstall("integration-test-plugin")

        assert result is True
        names = [r.name for r in mgr.list_plugins()]
        assert "integration-test-plugin" not in names

    def test_uninstall_deletes_file(self, manager, plugin_src) -> None:
        """Uninstalling a user plugin deletes the file from disk."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            mgr.install_from_path(plugin_src)
            dest_file = user_dir / plugin_src.name
            assert dest_file.exists()
            mgr.uninstall("integration-test-plugin")
            assert not dest_file.exists()

    def test_full_lifecycle_events_emitted(self, manager, plugin_src) -> None:
        """All lifecycle events (installed, disabled, enabled, uninstalled) are emitted."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            mgr.install_from_path(plugin_src)
            mgr.disable("integration-test-plugin")
            mgr.enable("integration-test-plugin")
            mgr.uninstall("integration-test-plugin")

        published_events = [c[0][0] for c in bus.publish.call_args_list]
        assert "plugin_installed" in published_events
        assert "plugin_disabled" in published_events
        assert "plugin_enabled" in published_events
        assert "plugin_uninstalled" in published_events

    def test_list_plugins_exclude_disabled(self, manager, plugin_src) -> None:
        """list_plugins(include_disabled=False) excludes disabled plugins."""
        mgr, bus, tmp_path = manager
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            mgr.install_from_path(plugin_src)

        mgr.disable("integration-test-plugin")
        enabled_list = mgr.list_plugins(include_disabled=False)
        assert all(r.enabled for r in enabled_list)
        assert not any(r.name == "integration-test-plugin" for r in enabled_list)

    def test_install_invalid_plugin_returns_none(self, manager, tmp_path) -> None:
        """Installing a file that fails sandbox validation returns None."""
        mgr, bus, _ = manager
        bad_src = tmp_path / "bad_plugin.py"
        # Missing PLUGIN_META → will fail validation
        bad_src.write_text("import os\nos.system('whoami')\n", encoding="utf-8")
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
            result = mgr.install_from_path(bad_src)

        assert result is None
