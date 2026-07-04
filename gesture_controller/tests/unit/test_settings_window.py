import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

from gesture_controller.gui.settings_window import SettingsWindow, HotkeyCaptureWidget
from gesture_controller.core.config_manager import ConfigManager


def test_hotkey_capture_widget(qapp: QApplication) -> None:
    widget = HotkeyCaptureWidget("Ctrl+Alt+P")
    assert widget.text() == "Ctrl+Alt+P"
    
    # 1. Trigger capture state
    widget._start_capture()
    assert widget._capturing is True
    assert widget.text() == "Press key combination..."
    
    # 2. Simulate key press event (e.g. Ctrl + Shift + A)
    signals = []
    widget.hotkey_captured.connect(lambda s: signals.append(s))
    
    # Synthesize key press event
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        "A"
    )
    widget.keyPressEvent(event)
    
    assert widget._capturing is False
    assert widget.text() == "Ctrl+Shift+A"
    assert len(signals) == 1
    assert signals[0] == "Ctrl+Shift+A"

    # Clean up to prevent segfaults
    widget.deleteLater()
    qapp.processEvents()

def test_settings_window_initialization(qapp: QApplication) -> None:
    config = ConfigManager()
    # Populate predefined gesture templates mock list
    config.set("gestures", [{"name": "Mock", "type": "static", "states": [{"id": "Trigger", "action": "KeyPress:A"}]}])
    
    window = SettingsWindow(config)
    assert window.windowTitle() == "Settings"
    assert window._camera_device.count() == 4
    assert window._gestures_tree.topLevelItemCount() == 1
    assert window._gestures_tree.topLevelItem(0).text(0) == "Mock"
    assert window._gestures_tree.topLevelItem(0).text(1) == "static"
    assert window._gestures_tree.topLevelItem(0).text(2) == "KeyPress:A"

    # Clean up to prevent segfaults
    window.deleteLater()
    qapp.processEvents()

def test_settings_window_apply_overrides(qapp: QApplication, tmp_path: Path) -> None:
    config = ConfigManager()
    window = SettingsWindow(config)
    
    # Simulate user changing widgets
    window._camera_device.setCurrentIndex(2)
    window._sens_slider.setValue(150)  # 1.5 multiplier
    window._hud_enabled.setChecked(False)
    window._hotkey_widget.setText("Ctrl+Alt+Q")
    
    signals = []
    window.config_changed.connect(lambda d: signals.append(d))
    
    # Patch USER_CONFIG_DIRS in the settings_window module where it's imported
    with patch("gesture_controller.gui.settings_window.USER_CONFIG_DIRS", {"Windows": tmp_path, "Linux": tmp_path, "Darwin": tmp_path}):
        with patch.object(window, "accept") as mock_accept:
            window._on_apply()
            mock_accept.assert_called_once()
            
    assert len(signals) == 1
    new_cfg = signals[0]
    # ConfigManager.set uses dot notation -> nested dicts
    assert config.get("camera.device_id") == 2
    assert config.get("sensitivity.global_multiplier") == 1.5
    assert config.get("hud.enabled") is False
    assert config.get("safety.toggle_recognition_hotkey") == "Ctrl+Alt+Q"

    # Clean up to prevent segfaults
    window.deleteLater()
    qapp.processEvents()

def test_settings_window_preserves_comments(qapp: QApplication, tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    initial_content = (
        "# This is a top-level comment\n"
        "camera:\n"
        "  device_id: 0  # this is a nested comment\n"
    )
    config_file.write_text(initial_content, encoding="utf-8")
    
    config = ConfigManager()
    window = SettingsWindow(config)
    
    window._camera_device.setCurrentIndex(3)
    
    with patch("gesture_controller.gui.settings_window.USER_CONFIG_DIRS", {"Windows": tmp_path, "Linux": tmp_path, "Darwin": tmp_path}):
        with patch.object(window, "accept"):
            window._on_apply()
            
    content = config_file.read_text(encoding="utf-8")
    assert "# This is a top-level comment" in content
    assert "# this is a nested comment" in content
    assert "device_id: 3" in content

    window.deleteLater()
    qapp.processEvents()

