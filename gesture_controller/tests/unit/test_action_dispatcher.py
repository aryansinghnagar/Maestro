import pytest
from unittest.mock import MagicMock, patch
from gesture_controller.os_integration.action_dispatcher import ActionDispatcher
from gesture_controller.models.data_types import GestureEvent
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.config_manager import ConfigManager

@pytest.fixture
def mock_controller() -> MagicMock:
    controller = MagicMock()
    controller.get_foreground_app.return_value = "explorer.exe"
    return controller

@pytest.fixture
def dummy_config() -> MagicMock:
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "profiles.auto_detect_app": True
    }.get(key, default)
    return config

@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()

def test_action_dispatcher_routing_os(mock_controller: MagicMock, dummy_config: MagicMock, event_bus: EventBus) -> None:
    dispatcher = ActionDispatcher(mock_controller, dummy_config, event_bus)
    
    event = GestureEvent(
        gesture_name="MinimizeWindow",
        gesture_type="dynamic",
        action="OS:MinimizeActiveWindow",
        confidence=1.0,
        hand="Right",
        timestamp=0.0
    )
    
    event_bus.publish("gesture_triggered", event)
    mock_controller.minimize_active_window.assert_called_once()

def test_action_dispatcher_routing_keypress(mock_controller: MagicMock, dummy_config: MagicMock, event_bus: EventBus) -> None:
    dispatcher = ActionDispatcher(mock_controller, dummy_config, event_bus)
    
    event = GestureEvent(
        gesture_name="CustomCopy",
        gesture_type="static",
        action="KeyPress:Ctrl+Shift+C",
        confidence=1.0,
        hand="Right",
        timestamp=0.0
    )
    
    event_bus.publish("gesture_triggered", event)
    mock_controller.key_combo.assert_called_once_with(["ctrl", "shift", "c"])

def test_action_dispatcher_routing_scroll(mock_controller: MagicMock, dummy_config: MagicMock, event_bus: EventBus) -> None:
    dispatcher = ActionDispatcher(mock_controller, dummy_config, event_bus)
    
    event = GestureEvent(
        gesture_name="ScrollUpDown",
        gesture_type="continuous",
        action="MouseScroll:-4",
        confidence=1.0,
        hand="Right",
        timestamp=0.0
    )
    
    event_bus.publish("gesture_triggered", event)
    mock_controller.mouse_scroll.assert_called_once_with(delta_y=-4)

def test_action_dispatcher_routing_media(mock_controller: MagicMock, dummy_config: MagicMock, event_bus: EventBus) -> None:
    dispatcher = ActionDispatcher(mock_controller, dummy_config, event_bus)
    
    event = GestureEvent(
        gesture_name="PlayMedia",
        gesture_type="static",
        action="Media:PlayPause",
        confidence=1.0,
        hand="Right",
        timestamp=0.0
    )
    
    event_bus.publish("gesture_triggered", event)
    mock_controller.media_play_pause.assert_called_once()

def test_action_dispatcher_app_profile_resolution(mock_controller: MagicMock, dummy_config: MagicMock, event_bus: EventBus) -> None:
    # 1. Set active foreground process name to chrome.exe
    mock_controller.get_foreground_app.return_value = "chrome.exe"
    
    dispatcher = ActionDispatcher(mock_controller, dummy_config, event_bus)
    
    event = GestureEvent(
        gesture_name="SwipeLeft",  # In profiles config this maps to KeyPress:Ctrl+Shift+Tab
        gesture_type="dynamic",
        action="KeyPress:ArrowLeft", # Default action if no profile matches
        confidence=1.0,
        hand="Right",
        timestamp=0.0
    )
    
    event_bus.publish("gesture_triggered", event)
    
    # Verify that the action executed was the profile-specific override hotkey combo
    mock_controller.key_combo.assert_called_once_with(["ctrl", "shift", "tab"])
    assert event.app_profile == "chrome.exe"
