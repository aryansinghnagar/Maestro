import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from multiprocessing import shared_memory

pytestmark = pytest.mark.real_mediapipe

from gesture_controller.vision.camera_stream import CameraStream
from gesture_controller.vision.landmark_extractor import LandmarkExtractor


def test_camera_to_landmarks_integration(
    shared_memory_frame: tuple[shared_memory.SharedMemory, np.ndarray],
) -> None:
    shm, frame_np = shared_memory_frame

    config = {
        "camera": {
            "device_id": 0,
            "resolution": [640, 480],
            "fps_target": 30,
            "backend_preference": ["ANY"],
            "auto_reconnect": False,
            "reconnect_backoff_ms": [10],
            "watchdog_timeout_ms": 2000,
        },
        "engine": {"max_hands": 1, "min_detection_confidence": 0.7, "min_tracking_confidence": 0.5},
    }

    # 1. Setup mock camera
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[10, 20] = [100, 150, 200]  # Dummy color pixel (BGR)
    mock_cap.read.return_value = (True, test_frame)

    # 2. Setup mock MediaPipe HandLandmarker
    mock_landmarker = MagicMock()
    mock_results = MagicMock()
    mock_landmarker.detect_hands.return_value = mock_results

    # Mock landmark values (21 points)
    mock_lm = MagicMock(x=0.25, y=0.5, z=-0.1, visibility=1.0)
    mock_results.hand_landmarks = [[mock_lm] * 21]

    # Mock handedness
    mock_category = MagicMock(category_name="Right", score=0.99)
    mock_results.handedness = [[mock_category]]

    with (
        patch("cv2.VideoCapture", return_value=mock_cap),
        patch(
            "mediapipe.tasks.python.vision.HandLandmarker.create_from_options",
            return_value=mock_landmarker,
        ),
    ):

        # Instantiate both stages
        import multiprocessing as mp

        event = mp.Event()
        stream = CameraStream(config, shm.name, event)
        extractor = LandmarkExtractor(config)

        # Connect mock camera
        stream._connect_camera()
        assert stream._cap is mock_cap

        # We simulate capture loop running once and writing to SharedMemory
        def stop_after_one_read() -> tuple[bool, np.ndarray]:
            stream._running = False  # Shut down loop after reading
            return True, test_frame

        mock_cap.read.side_effect = stop_after_one_read
        stream._running = True
        stream._capture_loop()

        # Verify SharedMemory was populated (the frame should be BGR->RGB mirror-flipped)
        # BGR [100, 150, 200] at (10, 20) becomes RGB [200, 150, 100] at (10, 640 - 1 - 20) = (10, 619)
        from gesture_controller.vision.double_buffer import DoubleFrameBuffer

        db_reader = DoubleFrameBuffer(shm.name, create=False)
        read_bytes = db_reader.read()
        assert read_bytes is not None
        read_frame = np.frombuffer(read_bytes, dtype=np.uint8).reshape((480, 640, 3))

        assert read_frame[10, 619, 0] == 200
        assert read_frame[10, 619, 1] == 150
        assert read_frame[10, 619, 2] == 100

        # Extract landmarks from SharedMemory using the extractor
        hands = extractor.extract(shm.name)

        assert hands is not None
        assert len(hands) == 1
        hand = hands[0]
        assert hand.handedness == "Right"
        assert hand.confidence == 0.99
        assert len(hand.landmarks) == 21
        assert hand.landmarks[0].x == 0.25
        assert hand.landmarks[0].y == 0.5
        assert hand.landmarks[0].z == -0.1
        assert hand.landmarks[0].visibility == 1.0

        # Clean up
        extractor.close()
        stream.stop()
