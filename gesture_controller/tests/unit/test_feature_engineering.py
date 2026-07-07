import numpy as np
import pytest
from gesture_controller.models.feature_engineering import compute_features
from gesture_controller.models.data_types import Hand, Landmark3D


def test_feature_engineering_open_palm(open_palm_hand: Hand) -> None:
    velocity = np.zeros((21, 3))
    acceleration = np.zeros((21, 3))
    features = compute_features(
        open_palm_hand, velocity, acceleration, timestamp=0.0, frame_number=0
    )

    assert features.hand_openness > 0.8
    assert features.index_extended is True
    assert features.middle_extended is True
    assert features.ring_extended is True
    assert features.pinky_extended is True
    assert features.thumb_extended is True


def test_feature_engineering_fist(fist_hand: Hand) -> None:
    velocity = np.zeros((21, 3))
    acceleration = np.zeros((21, 3))
    features = compute_features(fist_hand, velocity, acceleration, timestamp=0.0, frame_number=0)

    assert features.hand_openness < 0.6
    assert features.index_extended is False
    assert features.middle_extended is False
    assert features.ring_extended is False
    assert features.pinky_extended is False


def test_feature_engineering_pointing(pointing_hand: Hand) -> None:
    velocity = np.zeros((21, 3))
    acceleration = np.zeros((21, 3))
    features = compute_features(
        pointing_hand, velocity, acceleration, timestamp=0.0, frame_number=0
    )

    assert features.index_extended is True
    assert features.middle_extended is False
    assert features.ring_extended is False
    assert features.pinky_extended is False


def test_feature_engineering_pinch(pinch_hand: Hand) -> None:
    velocity = np.zeros((21, 3))
    acceleration = np.zeros((21, 3))
    features = compute_features(pinch_hand, velocity, acceleration, timestamp=0.0, frame_number=0)

    assert features.pinch_distance < 0.25


def test_scale_invariance(open_palm_hand: Hand) -> None:
    velocity = np.zeros((21, 3))
    acceleration = np.zeros((21, 3))

    features1 = compute_features(
        open_palm_hand, velocity, acceleration, timestamp=0.0, frame_number=0
    )

    # Scale coordinates by 2x
    scaled_landmarks = tuple(
        Landmark3D(x=lm.x * 2.0, y=lm.y * 2.0, z=lm.z * 2.0) for lm in open_palm_hand.landmarks
    )
    scaled_hand = Hand(
        landmarks=scaled_landmarks,
        handedness=open_palm_hand.handedness,
        confidence=open_palm_hand.confidence,
    )

    features2 = compute_features(scaled_hand, velocity, acceleration, timestamp=0.0, frame_number=0)

    assert features1.hand_openness == pytest.approx(features2.hand_openness, abs=1e-5)
    assert features1.index_curl == pytest.approx(features2.index_curl, abs=1e-5)
    assert features1.pinch_distance == pytest.approx(features2.pinch_distance, abs=1e-5)
    np.testing.assert_allclose(features1.palm_normal, features2.palm_normal, atol=1e-5)


def test_hand_mirroring_left_to_right(open_palm_hand: Hand) -> None:
    velocity = np.zeros((21, 3))
    acceleration = np.zeros((21, 3))

    # Create left hand by flipping x-coordinates
    left_landmarks = tuple(Landmark3D(x=-lm.x, y=lm.y, z=lm.z) for lm in open_palm_hand.landmarks)
    left_hand = Hand(
        landmarks=left_landmarks, handedness="Left", confidence=open_palm_hand.confidence
    )

    features_right = compute_features(
        open_palm_hand, velocity, acceleration, timestamp=0.0, frame_number=0
    )
    features_left = compute_features(
        left_hand, velocity, acceleration, timestamp=0.0, frame_number=0
    )

    # Both features should match since Left hand coordinates are mirrored to Right during feature extraction
    assert features_left.index_extended == features_right.index_extended
    assert features_left.middle_extended == features_right.middle_extended
    assert features_left.hand_openness == pytest.approx(features_right.hand_openness, abs=1e-5)
    assert features_left.pinch_distance == pytest.approx(features_right.pinch_distance, abs=1e-5)
