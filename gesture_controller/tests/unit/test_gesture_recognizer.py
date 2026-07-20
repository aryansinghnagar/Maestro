import pytest
from unittest.mock import MagicMock
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.gesture_recognizer import GestureRecognizer


def test_gesture_recognizer() -> None:
    config = ConfigManager()
    event_bus = EventBus()

    recognizer = GestureRecognizer(config, event_bus)
    assert recognizer._custom_matcher is not None
    assert recognizer._fsm_manager is not None
