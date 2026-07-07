import pytest
import numpy as np
from gesture_controller.models.data_types import Hand, Landmark3D


def test_landmark_creation() -> None:
    lm = Landmark3D(x=0.1, y=0.2, z=0.3, visibility=0.9)
    assert lm.x == 0.1
    assert lm.y == 0.2
    assert lm.z == 0.3
    assert lm.visibility == 0.9


def test_landmark_default_visibility() -> None:
    lm = Landmark3D(x=0.1, y=0.2, z=0.3)
    assert lm.visibility == 1.0


def test_hand_creation_and_palm_center() -> None:
    landmarks = tuple(Landmark3D(x=float(i) / 21.0, y=float(i) / 21.0, z=0.0) for i in range(21))
    hand = Hand(landmarks=landmarks, handedness="Left", confidence=0.85)

    assert hand.handedness == "Left"
    assert hand.confidence == 0.85
    assert len(hand.landmarks) == 21
    assert hand.wrist == landmarks[0]

    # Palm center calculation is: (wrist [0] + index_mcp [5] + pinky_mcp [17]) / 3
    expected_x = (landmarks[0].x + landmarks[5].x + landmarks[17].x) / 3.0
    expected_y = (landmarks[0].y + landmarks[5].y + landmarks[17].y) / 3.0
    expected_z = (landmarks[0].z + landmarks[5].z + landmarks[17].z) / 3.0

    np.testing.assert_allclose(
        hand.palm_center, np.array([expected_x, expected_y, expected_z], dtype=np.float32)
    )


def test_hand_invalid_landmarks_count() -> None:
    landmarks = tuple(Landmark3D(x=0.0, y=0.0, z=0.0) for _ in range(20))
    with pytest.raises(AssertionError):
        Hand(landmarks=landmarks, handedness="Left", confidence=0.85)


def test_frozen_dataclass_landmark() -> None:
    lm = Landmark3D(x=0.1, y=0.2, z=0.3)
    with pytest.raises(AttributeError):
        # type ignore is to bypass mypy error since dataclass is frozen
        lm.x = 0.5  # type: ignore


def test_frozen_dataclass_hand() -> None:
    landmarks = tuple(Landmark3D(x=float(i) / 21.0, y=float(i) / 21.0, z=0.0) for i in range(21))
    hand = Hand(landmarks=landmarks, handedness="Left", confidence=0.85)
    with pytest.raises(AttributeError):
        hand.handedness = "Right"  # type: ignore
