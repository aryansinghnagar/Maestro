import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from gesture_controller.vision.landmark_extractor import LandmarkExtractor
from gesture_controller.vision.onnx_backend import ONNXHandLandmarker


def test_onnx_backend_fallback_on_missing_files() -> None:
    config = {
        "engine": {
            "use_onnx": True,
            "max_hands": 1,
            "min_detection_confidence": 0.7,
            "min_tracking_confidence": 0.5,
        }
    }

    with (
        patch(
            "gesture_controller.vision.onnx_backend.ONNXHandLandmarker",
            side_effect=FileNotFoundError("ONNX models not found"),
        ),
        patch("mediapipe.tasks.python.vision.HandLandmarker.create_from_options") as mock_mp,
    ):
        extractor = LandmarkExtractor(config)
        assert extractor._is_onnx is False
        mock_mp.assert_called_once()


def test_onnx_backend_detect_success() -> None:
    config = {
        "engine": {
            "use_onnx": True,
            "max_hands": 1,
            "min_detection_confidence": 0.7,
            "min_tracking_confidence": 0.5,
        }
    }

    # Mock the internal detector and handpose models to simulate inference
    mock_palm_det = MagicMock()
    mock_hand_pose = MagicMock()

    # Palm: [bbox (4), landmarks (14), score (1)]
    dummy_palm = np.zeros(19)
    dummy_palm[-1] = 0.95
    mock_palm_det.infer.return_value = [dummy_palm]

    # Handpose: [bbox (4), screen_lms (63), world_lms (63), handedness (1), score (1)]
    dummy_pose = np.zeros(132)
    # Put some dummy screen landmarks: index 4 to 67
    for i in range(21):
        offset = 4 + i * 3
        dummy_pose[offset] = 320.0  # x (centered)
        dummy_pose[offset + 1] = 240.0  # y (centered)
        dummy_pose[offset + 2] = 10.0  # z
    dummy_pose[130] = 0.8  # Right hand
    dummy_pose[131] = 0.98  # Confidence
    mock_hand_pose.infer.return_value = dummy_pose

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("gesture_controller.vision.onnx_backend.PalmDetector", return_value=mock_palm_det),
        patch("gesture_controller.vision.onnx_backend.HandPoseEstimator", return_value=mock_hand_pose),
    ):
        landmarker = ONNXHandLandmarker(config)

        # Create a dummy image
        dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
        result = landmarker.detect_hands(dummy_image, timestamp_ms=100)

        assert len(result.hand_landmarks) == 1
        assert len(result.handedness) == 1

        landmarks = result.hand_landmarks[0]
        assert len(landmarks) == 21
        # Check normalization: 320 / 640 = 0.5, 240 / 480 = 0.5
        assert landmarks[0].x == 0.5
        assert landmarks[0].y == 0.5

        handedness = result.handedness[0][0]
        assert handedness.category_name == "Right"
        assert handedness.score == 0.8
