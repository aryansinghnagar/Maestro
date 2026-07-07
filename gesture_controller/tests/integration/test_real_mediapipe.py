import os
import pytest
import numpy as np
from pathlib import Path
from multiprocessing import shared_memory

from gesture_controller.vision.landmark_extractor import LandmarkExtractor

MODEL_PATH = Path("gesture_controller/data/hand_landmarker.task")


@pytest.mark.real_mediapipe
@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Real MediaPipe model file not found")
def test_real_mediapipe_initialization_and_extraction(shared_memory_frame) -> None:
    """Verify that the real MediaPipe HandLandmarker loads and runs inference
    on a blank frame without raising exceptions."""
    shm, frame_np = shared_memory_frame

    # Fill shared memory with a black frame (no hand present)
    frame_np.fill(0)

    # Real configuration pointing to the real model
    config = {
        "engine": {"max_hands": 2, "min_detection_confidence": 0.5, "min_tracking_confidence": 0.5}
    }

    # Initialize the extractor (it loads the actual hand_landmarker.task model file)
    extractor = LandmarkExtractor(config)

    # Extract landmarks from the blank frame (should return None or empty list)
    hands = extractor.extract(shm.name, timestamp_ms=10)

    # Verify inference ran successfully without crash and detected no hands on black frame
    assert hands is None or len(hands) == 0

    # Clean up landmarker
    if hasattr(extractor, "_landmarker") and extractor._landmarker is not None:
        extractor._landmarker.close()
