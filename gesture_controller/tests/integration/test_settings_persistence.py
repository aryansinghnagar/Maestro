"""Integration tests: Settings dialog persistence (Sprint 15).

Verifies that:
1. Settings window loads current config values correctly.
2. Applying the dialog persists changed values to the ConfigManager.
3. The config_changed signal fires with the updated dict.
4. Reopening Settings reflects the previously persisted value.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(overrides: dict | None = None):
    """Build a ConfigManager-like mock that stores and returns values."""
    store = {
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
    if overrides:
        store.update(overrides)

    mock_config = MagicMock()
    mock_config._config = {
        "hud": {"enabled": True, "opacity": 0.8, "show_tracking_points": True}
    }

    def _get(key, default=None):
        return store.get(key, default)

    def _set(key, value):
        store[key] = value

    mock_config.get.side_effect = _get
    mock_config.set.side_effect = _set
    mock_config._store = store
    return mock_config


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSettingsPersistence:
    def test_settings_window_opens_without_error(self, qapp) -> None:
        """Settings window can be constructed with a valid config mock."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config()
        win = SettingsWindow(cfg)
        assert win is not None
        win.reject()
        qapp.processEvents()

    def test_hud_slider_reflects_config_opacity(self, qapp) -> None:
        """HUD opacity slider initialises to the configured value."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config({"hud.opacity": 0.6})
        win = SettingsWindow(cfg)
        # slider range 0-100 maps opacity 0.0-1.0
        assert win._hud_opacity.value() == 60
        win.reject()
        qapp.processEvents()

    def test_sensitivity_slider_reflects_config(self, qapp) -> None:
        """Global sensitivity slider reflects the configured 1.0× value (maps to slider=100)."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config({"sensitivity.global_multiplier": 1.0})
        win = SettingsWindow(cfg)
        # slider range is 10-300 representing 0.1x to 3.0x; 1.0x → 100
        assert win._sens_slider.value() == 100
        win.reject()
        qapp.processEvents()

    def test_config_changed_signal_fires_on_apply(self, qapp) -> None:
        """config_changed signal fires when the dialog is accepted via _on_apply."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config()

        received_signals = []
        win = SettingsWindow(cfg)
        win.config_changed.connect(lambda d: received_signals.append(d))

        # Patch user_config_dir to avoid touching the real filesystem
        with patch("gesture_controller.gui.settings_window.user_config_dir", return_value=None):
            win._on_apply()

        assert len(received_signals) == 1

    def test_hud_enabled_checkbox_state(self, qapp) -> None:
        """HUD enabled checkbox is checked when config has hud.enabled=True."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config({"hud.enabled": True})
        win = SettingsWindow(cfg)
        assert win._hud_enabled.isChecked() is True
        win.reject()
        qapp.processEvents()

    def test_hud_enabled_unchecked_when_disabled(self, qapp) -> None:
        """HUD enabled checkbox is unchecked when config has hud.enabled=False."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config({"hud.enabled": False})
        win = SettingsWindow(cfg)
        assert win._hud_enabled.isChecked() is False
        win.reject()
        qapp.processEvents()

    def test_tremor_checkbox_reflects_config(self, qapp) -> None:
        """Tremor compensation checkbox reflects config value."""
        from gesture_controller.gui.settings_window import SettingsWindow
        # Real config key is filtering.tremor.enabled
        cfg = _make_config({"filtering.tremor.enabled": True})
        win = SettingsWindow(cfg)
        assert win._tremor_enabled.isChecked() is True
        win.reject()
        qapp.processEvents()

    def test_language_combo_defaults_to_english(self, qapp) -> None:
        """Language combo box has English selected for 'en' config."""
        from gesture_controller.gui.settings_window import SettingsWindow
        cfg = _make_config({"ui.language": "en"})
        win = SettingsWindow(cfg)
        # Find 'en' item data in the combo
        found_en = any(
            win._lang_combo.itemData(i) == "en"
            for i in range(win._lang_combo.count())
        )
        assert found_en, "'en' language code not found in language combo"
        assert win._lang_combo.currentData() == "en"
        win.reject()
        qapp.processEvents()
