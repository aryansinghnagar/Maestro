import pytest
import socket
import urllib.request
from unittest.mock import MagicMock, patch

from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.engine import GestureEngine


class NetworkBlockerError(AssertionError):
    """Raised when a network call is attempted during restricted execution."""

    pass


@pytest.fixture
def block_network() -> None:
    """Fixture that blocks all socket connections and urllib requests."""

    def blocked_socket(*args, **kwargs):
        raise NetworkBlockerError("Outbound socket connection blocked by policy")

    def blocked_urlopen(*args, **kwargs):
        raise NetworkBlockerError("Outbound urllib request blocked by policy")

    with (
        patch("socket.socket", side_effect=blocked_socket),
        patch("urllib.request.urlopen", side_effect=blocked_urlopen),
        patch("urllib.request.urlretrieve", side_effect=blocked_urlopen),
    ):
        yield


def test_config_manager_no_network(block_network) -> None:
    """Verify ConfigManager does not make network calls on initialization."""
    # This should load configuration files locally without issues
    manager = ConfigManager()
    assert manager.get("engine") is not None


def test_event_bus_no_network(block_network) -> None:
    """Verify EventBus publishes and delivers events completely offline."""
    import time

    bus = EventBus()
    delivered = []

    def handler(data):
        delivered.append(data)

    bus.subscribe("test_event", handler)
    bus.publish("test_event", "hello")
    time.sleep(0.05)
    assert delivered == ["hello"]


def test_engine_init_no_network(block_network) -> None:
    """Verify GestureEngine initialization and shutdown do not trigger network calls."""
    mock_extractor = MagicMock()
    mock_process = MagicMock()
    mock_shm = MagicMock()
    mock_shm.name = "mock_shm_segment"
    mock_shm.buf = bytearray(1843208)

    with (
        patch("gesture_controller.core.engine.LandmarkExtractor", return_value=mock_extractor),
        patch("gesture_controller.core.engine.start_camera_process", return_value=mock_process),
        patch("multiprocessing.shared_memory.SharedMemory", return_value=mock_shm),
        patch("gesture_controller.core.engine.PluginLoader"),
        patch("gesture_controller.core.engine.CustomGestureMatcher"),
    ):
        engine = GestureEngine()
        assert engine._shm_name == "mock_shm_segment"
        engine.start()
        engine.shutdown()
