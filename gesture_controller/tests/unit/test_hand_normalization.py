import numpy as np
import pytest
from gesture_controller.models.hand_normalization import (
    normalize_landmarks,
    landmarks_to_flat_vector,
    palm_center,
    palm_normal_vector,
)


def test_normalize_landmarks_validation() -> None:
    with pytest.raises(ValueError):
        normalize_landmarks(np.zeros((20, 3)))


def test_normalize_landmarks_right_hand() -> None:
    # 21 landmarks
    landmarks = np.zeros((21, 3))
    # landmark 5 is index MCP, landmark 6 is index PIP
    landmarks[5] = np.array([1.0, 0.0, 0.0])
    landmarks[6] = np.array([2.0, 0.0, 0.0])

    norm = normalize_landmarks(landmarks, handedness="Right")
    assert norm[0][0] == 0.0  # Wrist at origin
    assert norm[0][1] == 0.0
    assert norm[0][2] == 0.0


def test_normalize_landmarks_left_hand() -> None:
    # Left hand x values should be mirrored
    landmarks = np.zeros((21, 3))
    landmarks[5] = np.array([1.0, 0.0, 0.0])
    landmarks[6] = np.array([2.0, 0.0, 0.0])
    # Set custom point at index 1
    landmarks[1] = np.array([5.0, 2.0, 1.0])

    norm_right = normalize_landmarks(landmarks, handedness="Right")
    norm_left = normalize_landmarks(landmarks, handedness="Left")

    # Left x should be opposite of right x
    assert norm_left[1][0] == -norm_right[1][0]
    # y and z should remain identical
    assert norm_left[1][1] == norm_right[1][1]
    assert norm_left[1][2] == norm_right[1][2]


def test_landmarks_to_flat_vector() -> None:
    landmarks = np.zeros((21, 3))
    flat = landmarks_to_flat_vector(landmarks)
    assert flat.shape == (63,)


def test_palm_center() -> None:
    landmarks = np.zeros((21, 3))
    landmarks[0] = np.array([0.0, 0.0, 0.0])
    landmarks[5] = np.array([3.0, 0.0, 0.0])
    landmarks[17] = np.array([0.0, 3.0, 0.0])

    pc = palm_center(landmarks)
    assert np.allclose(pc, np.array([1.0, 1.0, 0.0]))


def test_palm_normal_vector() -> None:
    landmarks = np.zeros((21, 3))
    landmarks[0] = np.array([0.0, 0.0, 0.0])
    landmarks[5] = np.array([1.0, 0.0, 0.0])
    landmarks[17] = np.array([0.0, 1.0, 0.0])

    normal = palm_normal_vector(landmarks)
    # cross product of (1,0,0) and (0,1,0) is (0,0,1)
    assert np.allclose(normal, np.array([0.0, 0.0, 1.0]))
