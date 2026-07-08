import time
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from multiprocessing import shared_memory

from gesture_controller.vision.camera_stream import CameraStream


@pytest.fixture
def dummy_config() -> dict:
    return {
        "camera": {
            "device_id": 0,
            "resolution": [640, 480],
            "fps_target": 30,
            "backend_preference": ["ANY"],
            "auto_reconnect": True,
            "reconnect_backoff_ms": [10, 20],
            "watchdog_timeout_ms": 200,
        }
    }


def test_camera_connection_success(dummy_config: dict) -> None:
    stream = CameraStream(dummy_config, "dummy_shm", MagicMock())
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch("cv2.VideoCapture", return_value=mock_cap) as mock_vc:
        stream._connect_camera()
        assert stream._cap is mock_cap
        mock_vc.assert_called()


def test_camera_connection_failures_raises(dummy_config: dict) -> None:
    stream = CameraStream(dummy_config, "dummy_shm", MagicMock())
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch("cv2.VideoCapture", return_value=mock_cap):
        with pytest.raises(RuntimeError, match="Cannot open camera device"):
            stream._connect_camera()


def test_capture_loop_writes_to_shared_memory(
    dummy_config: dict, shared_memory_frame: tuple[shared_memory.SharedMemory, np.ndarray]
) -> None:
    shm, frame_np = shared_memory_frame
    stream = CameraStream(dummy_config, shm.name, MagicMock())

    mock_cap = MagicMock()
    # Create a uniform BGR test frame (all blue: 255, 0, 0)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[:, :, 0] = 255  # Blue channel in BGR

    # We want to run the loop once, then stop
    def mock_read() -> tuple[bool, np.ndarray]:
        stream._running = False  # Set running to false to stop the loop
        return True, test_frame

    mock_cap.read.side_effect = mock_read
    stream._cap = mock_cap
    stream._running = True

    stream._capture_loop()

    # Verify that the frame in SharedMemory is preprocessed:
    # 1. Resized to 640x480 (already 640x480)
    # 2. Converted to RGB (BGR blue [255, 0, 0] becomes RGB blue [0, 0, 255])
    # 3. Flipped horizontally (uniform, so doesn't change layout)
    from gesture_controller.vision.double_buffer import DoubleFrameBuffer

    db_reader = DoubleFrameBuffer(shm.name, create=False)
    read_bytes = db_reader.read()
    assert read_bytes is not None
    read_frame = np.frombuffer(read_bytes, dtype=np.uint8).reshape((480, 640, 3))

    expected_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    expected_frame[:, :, 2] = 255  # Red channel in RGB (due to conversion)

    np.testing.assert_array_equal(read_frame, expected_frame)


def test_camera_watchdog_timeout(
    dummy_config: dict, shared_memory_frame: tuple[shared_memory.SharedMemory, np.ndarray]
) -> None:
    shm, _ = shared_memory_frame
    stream = CameraStream(dummy_config, shm.name, MagicMock())

    mock_cap = MagicMock()
    # read() returns (False, None) to simulate temporary frame drop
    mock_cap.read.return_value = (False, None)
    stream._cap = mock_cap
    stream._running = True

    # We expect RuntimeError to be raised when the frame timeout exceeds watchdog_timeout_ms (200ms)
    start_time = time.monotonic()
    with pytest.raises(RuntimeError, match="Camera frame timeout"):
        stream._capture_loop()

    elapsed = time.monotonic() - start_time
    assert elapsed >= 0.2  # Watchdog should wait at least 200ms


def test_start_camera_process(dummy_config: dict) -> None:
    with patch("multiprocessing.Process") as mock_process_class:
        from gesture_controller.vision.camera_stream import start_camera_process

        proc = start_camera_process(dummy_config, "shm_name", MagicMock())
        mock_process_class.assert_called_once()


def test_camera_stream_run_loop(dummy_config: dict) -> None:
    stream = CameraStream(dummy_config, "shm_name", MagicMock())

    # We want run() to execute _connect_camera and capture once, then exit when _running becomes False
    with (
        patch.object(stream, "_connect_camera") as mock_connect,
        patch.object(stream, "_capture_loop") as mock_capture,
    ):

        def stop_running() -> None:
            stream._running = False

        mock_capture.side_effect = stop_running

        stream.run()
        mock_connect.assert_called_once()
        mock_capture.assert_called_once()
