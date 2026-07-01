import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from multiprocessing import shared_memory

from gesture_controller.vision.landmark_extractor import LandmarkExtractor
from gesture_controller.models.data_types import Hand, Landmark3D

@pytest.fixture
def dummy_config() -> dict:
    return {
        "engine": {
            "max_hands": 1,
            "min_detection_confidence": 0.7,
            "min_tracking_confidence": 0.5
        }
    }

def test_landmark_extractor_loads_mediapipe(dummy_config: dict) -> None:
    mock_landmarker = MagicMock()
    
    with patch("mediapipe.tasks.python.vision.HandLandmarker.create_from_options", return_value=mock_landmarker) as mock_create:
        extractor = LandmarkExtractor(dummy_config)
        assert extractor._landmarker is mock_landmarker
        mock_create.assert_called_once()

def test_landmark_extractor_extracts_hands(
    dummy_config: dict, 
    shared_memory_frame: tuple[shared_memory.SharedMemory, np.ndarray]
) -> None:
    shm, frame_np = shared_memory_frame
    frame_np[:] = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    mock_landmarker = MagicMock()
    mock_results = MagicMock()
    mock_landmarker.detect.return_value = mock_results
    
    # Mock output landmarks (21 points)
    mock_lm = MagicMock(x=0.1, y=0.2, z=0.3, visibility=0.95)
    mock_results.hand_landmarks = [[mock_lm] * 21]
    
    # Mock category handedness
    mock_category = MagicMock(category_name="Left", score=0.98)
    mock_results.handedness = [[mock_category]]
    
    with patch("mediapipe.tasks.python.vision.HandLandmarker.create_from_options", return_value=mock_landmarker):
        extractor = LandmarkExtractor(dummy_config)
        hands = extractor.extract(shm.name)
        
        assert hands is not None
        assert len(hands) == 1
        hand = hands[0]
        assert hand.handedness == "Left"
        assert hand.confidence == 0.98
        assert len(hand.landmarks) == 21
        assert hand.landmarks[0].x == 0.1
        assert hand.landmarks[0].y == 0.2
        assert hand.landmarks[0].z == 0.3
        assert hand.landmarks[0].visibility == 0.95

def test_landmark_extractor_returns_none_if_no_hands(
    dummy_config: dict, 
    shared_memory_frame: tuple[shared_memory.SharedMemory, np.ndarray]
) -> None:
    shm, _ = shared_memory_frame
    
    mock_landmarker = MagicMock()
    mock_results = MagicMock()
    mock_results.hand_landmarks = []
    mock_landmarker.detect.return_value = mock_results
    
    with patch("mediapipe.tasks.python.vision.HandLandmarker.create_from_options", return_value=mock_landmarker):
        extractor = LandmarkExtractor(dummy_config)
        hands = extractor.extract(shm.name)
        assert hands is None

def test_landmark_extractor_missing_shm(dummy_config: dict) -> None:
    mock_landmarker = MagicMock()
    with patch("mediapipe.tasks.python.vision.HandLandmarker.create_from_options", return_value=mock_landmarker):
        extractor = LandmarkExtractor(dummy_config)
        hands = extractor.extract("nonexistent_shm_name")
        assert hands is None
