import time
import pytest
from unittest.mock import MagicMock, patch
from multiprocessing import shared_memory

from gesture_controller.core.engine import GestureEngine


def test_engine_initialization_and_shutdown() -> None:
    mock_extractor = MagicMock()
    mock_process = MagicMock()
    mock_shm = MagicMock()
    mock_shm.name = "mock_shm_segment"
    mock_shm.buf = bytearray(1843208)

    # Patch all the system-dependent resources
    with (
        patch("gesture_controller.core.engine.LandmarkExtractor", return_value=mock_extractor),
        patch("gesture_controller.core.engine.create_camera_process", return_value=mock_process),
        patch("multiprocessing.shared_memory.SharedMemory", return_value=mock_shm),
        patch("gesture_controller.core.engine.PluginLoader") as mock_loader_class,
        patch("gesture_controller.core.engine.CustomGestureMatcher"),
    ):

        engine = GestureEngine()
        assert engine._shm_name == "mock_shm_segment"
        assert engine._camera_process is mock_process
        assert engine._running is False

        # Start the engine thread
        engine.start()
        assert engine._running is True
        assert engine._thread is not None
        assert engine._thread.is_alive()

        # Shutdown the engine thread and verify cleanup
        engine.shutdown()
        assert engine._running is False
        assert engine._thread is None

        mock_extractor.close.assert_called_once()
        mock_shm.close.assert_called_once()
        mock_shm.unlink.assert_called_once()


def test_engine_main_loop_publishing() -> None:
    mock_extractor = MagicMock()
    mock_process = MagicMock()
    mock_shm = MagicMock()
    mock_shm.name = "mock_shm_segment"
    mock_shm.buf = bytearray(1843208)

    dummy_hands = [MagicMock()]
    mock_extractor.extract.return_value = dummy_hands

    with (
        patch("gesture_controller.core.engine.LandmarkExtractor", return_value=mock_extractor),
        patch("gesture_controller.core.engine.create_camera_process", return_value=mock_process),
        patch("multiprocessing.shared_memory.SharedMemory", return_value=mock_shm),
        patch("gesture_controller.core.engine.PluginLoader"),
        patch("gesture_controller.core.engine.CustomGestureMatcher"),
    ):

        engine = GestureEngine()

        events_published = []

        def on_raw_landmarks(event: list) -> None:
            events_published.append(event)

        engine._event_bus.subscribe("raw_landmarks", on_raw_landmarks)

        # Start and let the main loop iterate a few times, then stop
        engine.start()
        for _ in range(5):
            engine._frame_ready_event.set()
            time.sleep(0.01)
        engine.shutdown()

        # We should have successfully published raw landmark events
        assert len(events_published) > 0
        assert events_published[0] == dummy_hands


def test_engine_initialization_rollback() -> None:
    mock_shm = MagicMock()
    mock_shm.name = "mock_shm_segment"
    mock_shm.buf = bytearray(1843208)
    mock_process = MagicMock()

    with (
        patch(
            "gesture_controller.core.engine.LandmarkExtractor",
            side_effect=RuntimeError("MediaPipe failed"),
        ),
        patch("gesture_controller.core.engine.create_camera_process", return_value=mock_process),
        patch("multiprocessing.shared_memory.SharedMemory", return_value=mock_shm),
        patch("gesture_controller.core.engine.PluginLoader"),
        patch("gesture_controller.core.engine.CustomGestureMatcher"),
    ):

        with pytest.raises(RuntimeError, match="MediaPipe failed"):
            GestureEngine()

        mock_process.terminate.assert_called_once()
        mock_shm.close.assert_called_once()
        mock_shm.unlink.assert_called_once()
