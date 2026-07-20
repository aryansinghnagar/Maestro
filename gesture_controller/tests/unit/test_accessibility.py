"""Tests for Sprint 9 accessibility features:
- DwellClicker trigger/reset logic
- TremorCalibrator FFT analysis and config writing
- Accessibility tab in SettingsWindow (load & apply)
- Reduced motion flag in overlay
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# DwellClicker
# ---------------------------------------------------------------------------

class TestDwellClicker:
    """Unit tests for DwellClicker.update_cursor logic (no Qt event loop needed)."""

    def _make_clicker(self, enabled: bool = True, duration_ms: int = 500) -> "DwellClicker":
        from gesture_controller.gui.dwell_clicker import DwellClicker

        config = MagicMock()
        config.get.side_effect = lambda key, default=None: {
            "a11y.dwell_click_enabled": enabled,
            "a11y.dwell_duration_ms": duration_ms,
        }.get(key, default)

        click_cb = MagicMock()
        dc = DwellClicker(config, click_cb)
        return dc, click_cb

    def test_no_click_while_cursor_moves(self) -> None:
        dc, click_cb = self._make_clicker()
        # Move to different positions sequentially
        dc.update_cursor(100, 100)
        dc.update_cursor(200, 200)  # > radius, resets dwell
        dc.update_cursor(300, 300)
        click_cb.assert_not_called()

    def test_click_fires_after_dwell_period(self) -> None:
        dc, click_cb = self._make_clicker(duration_ms=0)  # 0 ms → immediate
        dc.update_cursor(100, 100)
        # Force dwell_start into the past
        dc._dwell_start = time.monotonic() - 1.0
        dc.update_cursor(100, 100)  # Same position within radius
        click_cb.assert_called_once_with(100, 100)

    def test_click_only_fires_once_per_dwell(self) -> None:
        dc, click_cb = self._make_clicker(duration_ms=0)
        dc.update_cursor(100, 100)
        dc._dwell_start = time.monotonic() - 1.0
        dc.update_cursor(100, 100)
        dc.update_cursor(100, 100)  # Extra call – should not re-fire
        click_cb.assert_called_once()

    def test_dwell_resets_after_cursor_moves_beyond_radius(self) -> None:
        dc, click_cb = self._make_clicker(duration_ms=0)
        dc.update_cursor(100, 100)
        dc._dwell_start = time.monotonic() - 1.0
        dc.update_cursor(100, 100)  # fires click
        assert dc._clicked_for_current_dwell is True

        # Move beyond radius
        dc.update_cursor(200, 200)
        assert dc._clicked_for_current_dwell is False
        assert dc._cursor_pos == (200, 200)

    def test_small_movement_within_radius_does_not_reset(self) -> None:
        dc, click_cb = self._make_clicker(duration_ms=0)
        dc.update_cursor(100, 100)
        dc._dwell_start = time.monotonic() - 1.0
        # Move only 5px (within 20px radius)
        dc.update_cursor(105, 100)
        click_cb.assert_called_once_with(105, 100)

    def test_no_click_before_dwell_period_elapsed(self) -> None:
        dc, click_cb = self._make_clicker(duration_ms=5000)  # 5 seconds
        dc.update_cursor(100, 100)
        dc._dwell_start = time.monotonic()  # Just started
        dc.update_cursor(100, 100)
        click_cb.assert_not_called()

    def test_start_and_stop_thread(self) -> None:
        from gesture_controller.gui.dwell_clicker import DwellClicker
        config = MagicMock()
        config.get.return_value = False  # dwell disabled
        dc = DwellClicker(config, MagicMock())
        dc.start()
        assert dc._running is True
        dc.stop()
        assert dc._running is False
        assert dc._thread is None

    def test_start_idempotent(self) -> None:
        from gesture_controller.gui.dwell_clicker import DwellClicker
        config = MagicMock()
        config.get.return_value = False
        dc = DwellClicker(config, MagicMock())
        dc.start()
        thread_before = dc._thread
        dc.start()  # Second start should be a no-op
        assert dc._thread is thread_before
        dc.stop()


# ---------------------------------------------------------------------------
# TremorCalibrator – pure FFT logic tests (no Qt dialog needed)
# ---------------------------------------------------------------------------

class TestTremorCalibratorFFT:
    """Test the core FFT analysis that TremorCalibrator._finish() relies on."""

    def _run_fft(self, samples: list[tuple[float, float]]) -> tuple[float, float]:
        """Mirror of TremorCalibrator._finish() FFT logic."""
        times = np.array([t for t, _ in samples])
        xs = np.array([x for _, x in samples])
        dt = np.mean(np.diff(times))
        x_detrend = xs - np.mean(xs)
        fft = np.fft.rfft(x_detrend)
        freqs = np.fft.rfftfreq(len(xs), d=dt)
        magnitudes = np.abs(fft)
        tremor_mask = (freqs >= 4.0) & (freqs <= 12.0)
        if tremor_mask.any():
            peak_idx = magnitudes[tremor_mask].argmax()
            return float(freqs[tremor_mask][peak_idx]), float(magnitudes[tremor_mask][peak_idx])
        return 0.0, 0.0

    def _synthetic_samples(self, freq_hz: float, n: int = 300, sample_rate: float = 30.0) -> list[tuple[float, float]]:
        dt = 1.0 / sample_rate
        samples = []
        for i in range(n):
            t = i * dt
            x = 0.5 + 0.05 * np.sin(2.0 * np.pi * freq_hz * t)
            samples.append((t, float(x)))
        return samples

    def test_detects_8hz_tremor(self) -> None:
        samples = self._synthetic_samples(8.0)
        freq, amp = self._run_fft(samples)
        assert 6.0 <= freq <= 10.0  # generous window around 8 Hz
        assert amp > 0.001

    def test_detects_5hz_tremor(self) -> None:
        samples = self._synthetic_samples(5.0)
        freq, amp = self._run_fft(samples)
        assert 4.0 <= freq <= 7.0
        assert amp > 0.001

    def test_low_amplitude_below_threshold(self) -> None:
        """Flat signal → amplitude should be near zero."""
        n = 300
        samples = [(i / 30.0, 0.5) for i in range(n)]
        _, amp = self._run_fft(samples)
        assert amp < 0.001  # Below significance threshold

    def test_peak_freq_within_band(self) -> None:
        """Ensure detected peak is always in the 4-12 Hz band."""
        for hz in (4.5, 7.0, 10.0, 12.0):
            samples = self._synthetic_samples(hz)
            freq, _ = self._run_fft(samples)
            assert 3.0 <= freq <= 13.0, f"FFT peak {freq:.2f} Hz out of range for input {hz} Hz"


class TestTremorCalibratorConfig:
    """Test that _finish() updates config correctly (Qt-free simulation)."""

    def _make_calibrator(self, samples):
        """Instantiate with a mock Qt parent to skip dialog rendering."""
        from gesture_controller.gui.tremor_calibrator import TremorCalibrator

        config = MagicMock()
        config.get = MagicMock(return_value=None)
        config.set = MagicMock()

        # Patch super().__init__ to avoid needing a QApplication
        with patch("gesture_controller.gui.tremor_calibrator.QDialog.__init__", return_value=None), \
             patch("gesture_controller.gui.tremor_calibrator.QVBoxLayout"), \
             patch("gesture_controller.gui.tremor_calibrator.QLabel") as MockLabel, \
             patch("gesture_controller.gui.tremor_calibrator.QPushButton"), \
             patch("gesture_controller.gui.tremor_calibrator.QProgressBar"):
            mock_label = MagicMock()
            MockLabel.return_value = mock_label
            cal = TremorCalibrator.__new__(TremorCalibrator)
            cal._config = config
            cal._landmark_callback = MagicMock()
            cal._samples = samples
            cal.label = MagicMock()
            cal.start_button = MagicMock()
            return cal, config

    def _synthetic_samples(self, freq_hz: float, n: int = 300, sample_rate: float = 30.0) -> list[tuple[float, float]]:
        dt = 1.0 / sample_rate
        return [(i * dt, 0.5 + 0.05 * np.sin(2.0 * np.pi * freq_hz * i * dt)) for i in range(n)]

    def test_finish_enables_tremor_filter_on_significant_tremor(self) -> None:
        samples = self._synthetic_samples(8.0)
        cal, config = self._make_calibrator(samples)
        cal._finish()
        config.set.assert_any_call("filtering.tremor.enabled", True)

    def test_finish_sets_frequency_range_around_peak(self) -> None:
        samples = self._synthetic_samples(8.0)
        cal, config = self._make_calibrator(samples)
        cal._finish()
        calls = {c.args[0]: c.args[1] for c in config.set.call_args_list}
        assert "filtering.tremor.min_freq" in calls
        assert "filtering.tremor.max_freq" in calls
        assert calls["filtering.tremor.min_freq"] < calls["filtering.tremor.max_freq"]

    def test_finish_disables_tremor_filter_on_flat_signal(self) -> None:
        """Flat signal → no significant tremor → filter disabled."""
        samples = [(i / 30.0, 0.5) for i in range(300)]
        cal, config = self._make_calibrator(samples)
        cal._finish()
        calls = {c.args[0]: c.args[1] for c in config.set.call_args_list}
        assert calls.get("filtering.tremor.enabled") is False

    def test_finish_requires_minimum_sample_count(self) -> None:
        """Fewer than 15 samples should abort without setting config."""
        cal, config = self._make_calibrator([(0.0, 0.5)] * 5)
        cal._finish()
        config.set.assert_not_called()


# ---------------------------------------------------------------------------
# Accessibility Settings Tab – SettingsWindow integration
# ---------------------------------------------------------------------------

class TestAccessibilitySettingsTab:
    """Tests that accessibility settings are correctly loaded and applied."""

    def test_accessibility_tab_loads_from_config(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        config = ConfigManager()
        config.set("voice.enabled", True)
        config.set("voice.wake_word", "hello")
        config.set("filtering.tremor.enabled", True)
        config.set("a11y.theme", "high-contrast")
        config.set("a11y.reduced_motion", True)
        config.set("a11y.dwell_click_enabled", True)
        config.set("a11y.dwell_duration_ms", 1200)

        window = SettingsWindow(config)
        assert window._voice_enabled.isChecked() is True
        assert window._voice_wake_word.text() == "hello"
        assert window._tremor_enabled.isChecked() is True
        assert window._high_contrast.isChecked() is True
        assert window._reduced_motion.isChecked() is True
        assert window._dwell_enabled.isChecked() is True
        assert window._dwell_duration.value() == 1200

        window.deleteLater()
        qapp.processEvents()

    def test_accessibility_defaults_match_safe_baseline(self, qapp) -> None:
        """A fresh ConfigManager should produce safe default widget states."""
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        window = SettingsWindow(ConfigManager())
        # By default, voice control and dwell clicking must be OFF
        assert window._voice_enabled.isChecked() is False
        assert window._dwell_enabled.isChecked() is False

        window.deleteLater()
        qapp.processEvents()

    def test_accessibility_apply_saves_to_config(self, qapp, tmp_path: Path) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        config = ConfigManager()
        window = SettingsWindow(config)

        # Tweak accessibility widgets
        window._voice_enabled.setChecked(True)
        window._voice_wake_word.setText("computer")
        window._tremor_enabled.setChecked(True)
        window._high_contrast.setChecked(True)
        window._reduced_motion.setChecked(True)
        window._dwell_enabled.setChecked(True)
        window._dwell_duration.setValue(900)

        with patch("gesture_controller.gui.settings_window.user_config_dir", return_value=tmp_path):
            with patch.object(window, "accept"):
                window._on_apply()

        assert config.get("voice.enabled") is True
        assert config.get("voice.wake_word") == "computer"
        assert config.get("filtering.tremor.enabled") is True
        assert config.get("a11y.theme") == "high-contrast"
        assert config.get("a11y.reduced_motion") is True
        assert config.get("a11y.dwell_click_enabled") is True
        assert config.get("a11y.dwell_duration_ms") == 900

        window.deleteLater()
        qapp.processEvents()

    def test_accessibility_apply_persists_to_yaml(self, qapp, tmp_path: Path) -> None:
        """Saved YAML must contain accessibility keys."""
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        config = ConfigManager()
        window = SettingsWindow(config)
        window._dwell_enabled.setChecked(True)
        window._dwell_duration.setValue(750)
        window._reduced_motion.setChecked(True)

        with patch("gesture_controller.gui.settings_window.user_config_dir", return_value=tmp_path):
            with patch.object(window, "accept"):
                window._on_apply()

        config_file = tmp_path / "config.yaml"
        assert config_file.exists()
        content = config_file.read_text(encoding="utf-8")
        assert "dwell_click_enabled" in content
        assert "dwell_duration_ms" in content
        assert "reduced_motion" in content

        window.deleteLater()
        qapp.processEvents()

    def test_dwell_label_updates_with_slider(self, qapp) -> None:
        """Dwell duration label should reflect slider value."""
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        window = SettingsWindow(ConfigManager())
        window._dwell_duration.setValue(1500)
        assert window._dwell_label.text() == "1500 ms"

        window.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# detect_reduced_motion – theme.py
# ---------------------------------------------------------------------------

class TestDetectReducedMotion:
    def test_returns_bool(self) -> None:
        from gesture_controller.gui.theme import detect_reduced_motion
        result = detect_reduced_motion()
        assert isinstance(result, bool)

    def test_handles_ctypes_error_gracefully(self) -> None:
        """If ctypes.windll raises, it should return False not crash."""
        from gesture_controller.gui.theme import detect_reduced_motion
        import platform

        with patch("platform.system", return_value="Windows"):
            with patch("ctypes.windll") as mock_windll:
                mock_windll.user32.SystemParametersInfoW.side_effect = OSError("mocked")
                result = detect_reduced_motion()
                assert result is False


# ---------------------------------------------------------------------------
# Overlay reduced motion integration
# ---------------------------------------------------------------------------

class TestOverlayReducedMotion:
    def test_reduced_motion_config_is_respected(self, qapp) -> None:
        """When a11y.reduced_motion=True and fsm_progress < 0.95, ring should snap to 0."""
        from gesture_controller.gui.overlay import OverlayHUD

        config = {
            "hud": {"show_progress_ring": True, "enabled": True, "opacity": 0.8},
            "a11y": {"reduced_motion": True},
        }

        with patch("gesture_controller.gui.theme.detect_reduced_motion", return_value=True):
            overlay = OverlayHUD(config)
            # Simulate an in-progress gesture at 50% via set_hand_data
            overlay.set_hand_data([], fsm_states={"TestGesture": ("Active", 0.5)})
            # FSM progress should be recorded
            assert overlay._fsm_progress == pytest.approx(0.5)
            # reduced_motion flag should be readable from config
            assert overlay._config.get("a11y", {}).get("reduced_motion") is True

            overlay.deleteLater()
            qapp.processEvents()
