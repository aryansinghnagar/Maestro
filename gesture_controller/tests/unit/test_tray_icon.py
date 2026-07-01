import sys
from unittest.mock import MagicMock

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
from gesture_controller.core.event_bus import EventBus
from gesture_controller.gui.tray_icon import TrayController, create_tray_icon

# Ensure a QApplication singleton is available for Qt widgets testing
@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

def test_create_tray_icon(qapp: QApplication) -> None:
    # Under mock, create_tray_icon still runs its QIcon drawing logic
    icon_active = create_tray_icon(paused=False)
    icon_paused = create_tray_icon(paused=True)
    assert icon_active is not None
    assert icon_paused is not None

def test_tray_controller_initialization(qapp: QApplication) -> None:
    mock_bus = MagicMock(spec=EventBus)
    tray = TrayController(mock_bus)
        
    assert tray._paused is False
    assert tray._camera_active is True

    # Clean up
    tray.deleteLater()
    qapp.processEvents()

def test_tray_controller_toggle_pause(qapp: QApplication) -> None:
    mock_bus = MagicMock(spec=EventBus)
    tray = TrayController(mock_bus)
    
    signals = []
    tray.pause_toggled.connect(lambda v: signals.append(v))
    
    # Toggle once (pauses)
    tray.toggle_pause()
    assert tray._paused is True
    assert len(signals) == 1
    assert signals[0] is True
    
    # Toggle twice (resumes)
    tray.toggle_pause()
    assert tray._paused is False
    assert len(signals) == 2
    assert signals[1] is False

    # Clean up
    tray.deleteLater()
    qapp.processEvents()

def test_tray_controller_camera_events(qapp: QApplication) -> None:
    mock_bus = MagicMock(spec=EventBus)
    tray = TrayController(mock_bus)
    
    # Verify event bus subscriptions
    assert mock_bus.subscribe.call_count == 2
    calls = [c[0][0] for c in mock_bus.subscribe.call_args_list]
    assert "camera_disconnected" in calls
    assert "camera_recovered" in calls
    
    # Trigger disconnected handler
    tray._on_camera_disconnected(None)
    assert tray._camera_active is False
    
    # Trigger recovered handler
    tray._on_camera_recovered(None)
    assert tray._camera_active is True

    # Clean up
    tray.deleteLater()
    qapp.processEvents()

def test_tray_update_status(qapp: QApplication) -> None:
    mock_bus = MagicMock(spec=EventBus)
    tray = TrayController(mock_bus)
    
    tray.update_status(fps=30.0, gesture_count=5)
    
    # ToolTip should be set on the mock system tray icon
    tray._tray_icon.setToolTip.assert_called_once()
    tooltip = tray._tray_icon.setToolTip.call_args[0][0]
    assert "30.0" in tooltip
    assert "5" in tooltip

    # Clean up
    tray.deleteLater()
    qapp.processEvents()
