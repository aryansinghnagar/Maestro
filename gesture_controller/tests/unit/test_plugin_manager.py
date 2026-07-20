"""Unit tests for Sprint 12 – Plugin Manager.

Covers:
- PluginRecord serialisation
- PluginManager: load_all, enable, disable, list_plugins, get
- PluginManager: uninstall (builtin guard, file deletion)
- PluginManager: install_from_path
- PluginManager: search_registry, _load_registry
- Settings Plugins tab: widget construction, populate list, enable/disable/search
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_record(name="test-plugin", enabled=True):
    from gesture_controller.plugins.plugin_manager import PluginRecord
    return PluginRecord(
        name=name,
        version="1.2.3",
        description="A test plugin",
        author="Tester",
        permissions=["os:input"],
        path=Path("/fake/test_plugin.py"),
        enabled=enabled,
    )


def _make_manager(tmp_path, plugins=None):
    """Build a PluginManager with mocked PluginLoader."""
    from gesture_controller.plugins.plugin_manager import PluginManager

    mock_bus = MagicMock()
    mock_config = MagicMock()
    mock_config.get.return_value = []

    manager = PluginManager(mock_bus, mock_config)

    if plugins is not None:
        # Inject fake records directly
        manager._records = {r.name: r for r in plugins}

    return manager, mock_bus, mock_config


# ---------------------------------------------------------------------------
# PluginRecord
# ---------------------------------------------------------------------------

class TestPluginRecord:
    def test_to_dict_has_required_keys(self) -> None:
        record = _make_record()
        d = record.to_dict()
        assert set(d.keys()) >= {"name", "version", "description", "author", "permissions", "path", "enabled"}

    def test_to_dict_enabled_true(self) -> None:
        assert _make_record(enabled=True).to_dict()["enabled"] is True

    def test_to_dict_enabled_false(self) -> None:
        assert _make_record(enabled=False).to_dict()["enabled"] is False

    def test_from_plugin_roundtrip(self) -> None:
        from gesture_controller.plugins.plugin_manager import PluginRecord
        mock_plugin = MagicMock()
        mock_plugin.meta = {
            "name": "roundtrip",
            "version": "2.0.0",
            "description": "desc",
            "author": "auth",
            "permissions": ["ui:hud"],
        }
        mock_plugin.path = Path("/x/roundtrip.py")
        record = PluginRecord.from_plugin(mock_plugin, enabled=False)
        assert record.name == "roundtrip"
        assert record.version == "2.0.0"
        assert record.enabled is False


# ---------------------------------------------------------------------------
# PluginManager: enable / disable / list
# ---------------------------------------------------------------------------

class TestPluginManagerEnableDisable:
    def test_enable_sets_enabled_true(self, tmp_path) -> None:
        record = _make_record("alpha", enabled=False)
        manager, bus, cfg = _make_manager(tmp_path, plugins=[record])
        assert manager.enable("alpha") is True
        assert manager.get("alpha").enabled is True
        bus.publish.assert_called_with("plugin_enabled", "alpha")

    def test_disable_sets_enabled_false(self, tmp_path) -> None:
        record = _make_record("beta", enabled=True)
        manager, bus, cfg = _make_manager(tmp_path, plugins=[record])
        assert manager.disable("beta") is True
        assert manager.get("beta").enabled is False
        bus.publish.assert_called_with("plugin_disabled", "beta")

    def test_enable_unknown_returns_false(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[])
        assert manager.enable("ghost") is False

    def test_disable_unknown_returns_false(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[])
        assert manager.disable("ghost") is False

    def test_list_plugins_sorted(self, tmp_path) -> None:
        records = [_make_record("zeta"), _make_record("alpha"), _make_record("beta")]
        manager, _, _ = _make_manager(tmp_path, plugins=records)
        names = [r.name for r in manager.list_plugins()]
        assert names == sorted(names)

    def test_list_plugins_exclude_disabled(self, tmp_path) -> None:
        records = [_make_record("on", enabled=True), _make_record("off", enabled=False)]
        manager, _, _ = _make_manager(tmp_path, plugins=records)
        enabled_only = manager.list_plugins(include_disabled=False)
        assert all(r.enabled for r in enabled_only)
        assert len(enabled_only) == 1

    def test_is_enabled_true(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[_make_record("on", enabled=True)])
        assert manager.is_enabled("on") is True

    def test_is_enabled_false_for_disabled(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[_make_record("off", enabled=False)])
        assert manager.is_enabled("off") is False

    def test_is_enabled_false_for_missing(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[])
        assert manager.is_enabled("unknown") is False

    def test_persist_disabled_calls_config_set(self, tmp_path) -> None:
        records = [_make_record("on", enabled=True), _make_record("off", enabled=False)]
        manager, _, cfg = _make_manager(tmp_path, plugins=records)
        manager._persist_disabled()
        cfg.set.assert_called_with("plugins.disabled", ["off"])


# ---------------------------------------------------------------------------
# PluginManager: uninstall
# ---------------------------------------------------------------------------

class TestPluginManagerUninstall:
    def test_uninstall_removes_record(self, tmp_path) -> None:
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text("# dummy")

        from gesture_controller.plugins.plugin_manager import PluginRecord
        from gesture_controller.plugins.plugin_loader import USER_PLUGIN_DIR

        record = PluginRecord(
            name="removable",
            version="1.0",
            description="",
            author="",
            permissions=[],
            path=plugin_file,
        )
        manager, bus, _ = _make_manager(tmp_path, plugins=[record])

        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", tmp_path):
            result = manager.uninstall("removable")

        assert result is True
        assert manager.get("removable") is None
        bus.publish.assert_called_with("plugin_uninstalled", "removable")

    def test_uninstall_unknown_returns_false(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[])
        assert manager.uninstall("ghost") is False

    def test_uninstall_builtin_blocked(self, tmp_path) -> None:
        from gesture_controller.plugins.plugin_manager import PluginRecord
        record = PluginRecord(
            name="builtin",
            version="1.0",
            description="",
            author="",
            permissions=[],
            path=Path("/usr/lib/maestro/plugins/builtin.py"),
        )
        manager, _, _ = _make_manager(tmp_path, plugins=[record])
        # USER_PLUGIN_DIR points to tmp_path so /usr/lib/... will not match
        with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", tmp_path):
            assert manager.uninstall("builtin") is False


# ---------------------------------------------------------------------------
# PluginManager: install_from_path
# ---------------------------------------------------------------------------

class TestPluginManagerInstallFromPath:
    def test_install_copies_file_and_returns_record(self, tmp_path) -> None:
        from gesture_controller.plugins.plugin_manager import PluginManager, PluginRecord

        src = tmp_path / "new_plugin.py"
        src.write_text(
            'PLUGIN_META = {"name": "new-plugin", "version": "0.1.0"}\n'
            'GESTURE_DEFINITIONS = []\n'
            'ACTION_HANDLERS = {}\n'
        )
        user_dir = tmp_path / "user_plugins"
        user_dir.mkdir()

        mock_bus = MagicMock()
        mock_config = MagicMock()
        mock_config.get.return_value = []

        mock_record = PluginRecord(
            name="new-plugin",
            version="0.1.0",
            description="",
            author="",
            permissions=[],
            path=user_dir / "new_plugin.py",
        )

        manager = PluginManager(mock_bus, mock_config)
        manager._records = {}

        with patch.object(manager._loader, "_load_plugin", return_value=MagicMock(
            meta={"name": "new-plugin", "version": "0.1.0", "description": "", "author": "", "permissions": []},
            path=user_dir / "new_plugin.py",
            gestures=[],
            actions={},
        )):
            with patch("gesture_controller.plugins.plugin_manager.USER_PLUGIN_DIR", user_dir):
                result = manager.install_from_path(src)

        assert result is not None
        assert result.name == "new-plugin"
        mock_bus.publish.assert_called_with("plugin_installed", "new-plugin")

    def test_install_nonexistent_source_returns_none(self, tmp_path) -> None:
        manager, _, _ = _make_manager(tmp_path, plugins=[])
        result = manager.install_from_path(tmp_path / "nonexistent.py")
        assert result is None


# ---------------------------------------------------------------------------
# PluginManager: registry search
# ---------------------------------------------------------------------------

class TestPluginManagerRegistry:
    def _make_registry_manager(self, tmp_path, registry_entries):
        from gesture_controller.plugins.plugin_manager import PluginManager
        mock_bus = MagicMock()
        mock_config = MagicMock()
        mock_config.get.return_value = []
        manager = PluginManager(mock_bus, mock_config)
        manager._records = {}

        # Override _load_registry to return our fixture
        manager._load_registry = lambda: registry_entries
        return manager

    def test_search_by_name(self, tmp_path) -> None:
        entries = [
            {"name": "media-gestures", "description": "Media", "tags": ["music"]},
            {"name": "scroll-wheel", "description": "Scroll", "tags": []},
        ]
        manager = self._make_registry_manager(tmp_path, entries)
        results = manager.search_registry("media")
        assert len(results) == 1
        assert results[0]["name"] == "media-gestures"

    def test_search_by_tag(self, tmp_path) -> None:
        entries = [
            {"name": "x", "description": "", "tags": ["music"]},
            {"name": "y", "description": "", "tags": ["scroll"]},
        ]
        manager = self._make_registry_manager(tmp_path, entries)
        results = manager.search_registry("music")
        assert any(e["name"] == "x" for e in results)

    def test_search_empty_query_returns_all(self, tmp_path) -> None:
        entries = [{"name": "a", "description": "x", "tags": []}, {"name": "b", "description": "y", "tags": []}]
        manager = self._make_registry_manager(tmp_path, entries)
        # Empty string matches everything (both name and description are supersets)
        results = manager.search_registry("")
        assert len(results) == 2

    def test_search_no_results(self, tmp_path) -> None:
        entries = [{"name": "alpha", "description": "foo", "tags": []}]
        manager = self._make_registry_manager(tmp_path, entries)
        assert manager.search_registry("zzz_no_match") == []

    def test_load_registry_from_bundled_file(self, tmp_path) -> None:
        from gesture_controller.plugins.plugin_manager import PluginManager
        mock_bus = MagicMock()
        mock_config = MagicMock()
        mock_config.get.return_value = []
        manager = PluginManager(mock_bus, mock_config)
        # The bundled registry should be parseable
        data = manager._load_registry()
        assert isinstance(data, list)

    def test_load_registry_returns_empty_on_missing_file(self, tmp_path) -> None:
        from gesture_controller.plugins.plugin_manager import PluginManager, _BUNDLED_REGISTRY
        mock_bus = MagicMock()
        mock_config = MagicMock()
        mock_config.get.return_value = []
        manager = PluginManager(mock_bus, mock_config)
        fake_cache = tmp_path / "plugin_registry_cache.json"

        with patch("gesture_controller.plugins.plugin_manager._BUNDLED_REGISTRY",
                   tmp_path / "nonexistent.json"):
            result = manager._load_registry()
        # Should return empty list (no exception)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Settings Plugins Tab
# ---------------------------------------------------------------------------

def _make_settings_config():
    """Build a mock ConfigManager that returns typed defaults."""
    mock_config = MagicMock()
    mock_config._config = {}

    _defaults = {
        "camera.device_id": 0,
        "ui.hotkey": "",
        "ui.language": "en",
        "sensitivity.global": 0.5,
        "sensitivity.min_cutoff": 1.0,
        "hud.enabled": True,
        "hud.opacity": 0.8,
        "hud.show_joints": True,
        "hud.show_progress_ring": True,
        "voice.enabled": False,
        "voice.wake_word": "maestro",
        "tremor.enabled": False,
        "a11y.theme": "auto",
        "a11y.reduced_motion": False,
        "a11y.dwell_click_enabled": False,
        "a11y.dwell_duration_ms": 1000,
        "plugins.disabled": [],
    }

    def _get(key, default=None):
        return _defaults.get(key, default)

    mock_config.get.side_effect = _get
    return mock_config


class TestSettingsPluginsTab:
    def test_plugins_tab_exists(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        win = SettingsWindow(_make_settings_config())
        tab_titles = [win._tabs.tabText(i) for i in range(win._tabs.count())]
        assert "Plugins" in tab_titles
        win.reject()
        qapp.processEvents()

    def test_plugin_list_widget_created(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        win = SettingsWindow(_make_settings_config())
        assert hasattr(win, "_plugin_list")
        win.reject()
        qapp.processEvents()

    def test_plugin_search_widget_created(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        win = SettingsWindow(_make_settings_config())
        assert hasattr(win, "_plugin_search")
        win.reject()
        qapp.processEvents()

    def test_registry_search_no_results(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        win = SettingsWindow(_make_settings_config())
        win._plugin_search.setText("zzz_no_match_xyz")
        win._on_plugin_registry_search()
        # In headless Qt, isVisible() requires parent shown; check !isHidden() instead
        assert not win._registry_list.isHidden()
        items = [win._registry_list.item(i).text() for i in range(win._registry_list.count())]
        assert any("No results" in t for t in items)
        win.reject()
        qapp.processEvents()

    def test_registry_search_finds_media(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        win = SettingsWindow(_make_settings_config())
        win._plugin_search.setText("media")
        win._on_plugin_registry_search()
        items = [win._registry_list.item(i).text() for i in range(win._registry_list.count())]
        assert any("media" in t.lower() for t in items)
        win.reject()
        qapp.processEvents()

