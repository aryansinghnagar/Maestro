"""Integration tests verifying the startup flow of the app entry coordinator.
Ensures tray is active and overlay is visible.
"""
import sys
from unittest.mock import MagicMock, patch

# Define dummy wrapper classes that inherit from MagicMock
# but do not treat the first positional argument (parent widget) as a spec.
class DummySystemTrayIcon(MagicMock):
    class MessageIcon:
        Warning = 1
        Information = 2
        
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()

class DummyMenu(MagicMock):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()

# Mock PyQt6 QSystemTrayIcon and QMenu at the module level before any other imports
import PyQt6.QtWidgets
PyQt6.QtWidgets.QSystemTrayIcon = DummySystemTrayIcon
PyQt6.QtWidgets.QMenu = DummyMenu

import pytest
from PyQt6.QtWidgets import QApplication
from gesture_controller.gui.app_entry import GestureControllerApp

def test_full_pipeline_gui_flow(qapp: QApplication) -> None:
    """Verify tray icon becomes visible and overlay widget opens on app start."""
    with patch("gesture_controller.core.engine.GestureEngine") as MockEngine, \
         patch("PyQt6.QtCore.QTimer.singleShot") as MockSingleShot:
         
        # Mock engine instance config & internal components
        engine_instance = MagicMock()
        engine_instance._config = MagicMock()
        engine_instance._config.get.side_effect = lambda key, default=None: {
            "hud.enabled": True,
            "hud.opacity": 0.8,
            "hud.show_tracking_points": True,
        }.get(key, default)
        
        engine_instance._config._config = {
            "hud": {
                "enabled": True,
                "opacity": 0.8,
                "show_tracking_points": True
            }
        }
        engine_instance._event_bus = MagicMock()
        engine_instance.get_current_hands.return_value = []
        engine_instance.get_fps.return_value = 30.0
        engine_instance.get_gesture_count.return_value = 0
        MockEngine.return_value = engine_instance
        
        # Initialize coordinator app
        app = GestureControllerApp()

        # Check components are instantiated
        assert app._tray is not None
        assert app._overlay is not None
        assert app._settings is not None

        # Check visibility
        assert app._tray._tray_icon.show.called
        assert app._overlay.isVisible() is True

        # Check timers are running
        assert app._poll_timer.isActive() is True
        assert app._status_timer.isActive() is True

        # Test coordinator polling callbacks
        app._poll_engine()
        app._update_tray_status()

        # Test coordinator gesture trigger callback
        app._on_gesture_triggered_gui("Swipe", "NextTab")

        # Graceful shutdown to stop timers and clean up widgets
        app._shutdown()
        assert app._overlay.isHidden() is True
        assert app._tray._tray_icon.hide.called

        # Explicitly delete widgets to prevent GC access violations on exit
        app._settings.deleteLater()
        app._overlay.deleteLater()
        app._tray.deleteLater()
        if hasattr(app, "_bridge"):
            app._bridge.deleteLater()
        qapp.processEvents()
