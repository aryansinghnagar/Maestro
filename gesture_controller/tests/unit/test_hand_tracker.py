import pytest
from gesture_controller.core.hand_tracker import HandTracker
from gesture_controller.models.data_types import Hand, Landmark3D


def _create_hand(x: float, y: float, z: float, handedness: str = "Right") -> Hand:
    landmarks = tuple(
        [
            Landmark3D(x=x, y=y, z=z),
            Landmark3D(x=x + 0.05, y=y, z=z),
        ]
        + [Landmark3D(x=0.0, y=0.0, z=0.0) for _ in range(19)]
    )
    return Hand(landmarks=landmarks, handedness=handedness, confidence=0.9)


def test_hand_tracker_new_id() -> None:
    tracker = HandTracker()
    hand = _create_hand(0.1, 0.2, 0.3)
    res = tracker.update([hand])
    assert len(res) == 1
    assert res[0][1] == 0


def test_hand_tracker_stable_id() -> None:
    tracker = HandTracker()
    hand1 = _create_hand(0.1, 0.2, 0.3)
    res1 = tracker.update([hand1])
    assert res1[0][1] == 0

    hand2 = _create_hand(0.12, 0.22, 0.28)
    res2 = tracker.update([hand2])
    assert len(res2) == 1
    assert res2[0][1] == 0


def test_hand_tracker_multiple_hands() -> None:
    tracker = HandTracker()
    h1 = _create_hand(0.1, 0.2, 0.3)
    h2 = _create_hand(0.6, 0.7, 0.8)

    res = tracker.update([h1, h2])
    assert len(res) == 2
    ids = {r[1] for r in res}
    assert ids == {0, 1}


def test_hand_tracker_swap() -> None:
    tracker = HandTracker()
    h1 = _create_hand(0.1, 0.2, 0.3)
    h2 = _create_hand(0.6, 0.7, 0.8)
    tracker.update([h1, h2])

    # Swap positions in next frame
    h1_next = _create_hand(0.61, 0.71, 0.79)
    h2_next = _create_hand(0.09, 0.21, 0.31)

    res = tracker.update([h1_next, h2_next])
    assert len(res) == 2

    # Verify ID 0 tracks the hand near (0.1, 0.2, 0.3)
    # and ID 1 tracks the hand near (0.6, 0.7, 0.8)
    for hand, track_id in res:
        if track_id == 0:
            assert abs(hand.landmarks[0].x - 0.09) < 0.01
        elif track_id == 1:
            assert abs(hand.landmarks[0].x - 0.61) < 0.01


def test_hand_tracker_retirement() -> None:
    tracker = HandTracker(max_missing_frames=2)
    h = _create_hand(0.1, 0.2, 0.3)
    tracker.update([h])

    # Missing for 2 frames
    tracker.update([])
    tracker.update([])

    # Still tracked on frame 2? Let's check missing frames limit.
    # At max_missing_frames=2:
    # Frame 1: missing count = 1
    # Frame 2: missing count = 2
    # Frame 3: missing count = 3 -> retired
    tracker.update([])

    h_new = _create_hand(0.1, 0.2, 0.3)
    res = tracker.update([h_new])
    assert len(res) == 1
    assert res[0][1] == 1  # ID 0 retired, new ID 1 assigned


def test_hand_tracker_movement_threshold() -> None:
    tracker = HandTracker(max_distance=0.1)
    h1 = _create_hand(0.1, 0.2, 0.3)
    tracker.update([h1])

    # Moves too far (0.15 distance > 0.1 threshold)
    h2 = _create_hand(0.3, 0.2, 0.3)
    res = tracker.update([h2])
    assert len(res) == 1
    assert res[0][1] == 1  # Exceeds threshold, gets new ID 1


def test_hand_tracker_handedness_flip() -> None:
    tracker = HandTracker()
    h1 = _create_hand(0.1, 0.2, 0.3, handedness="Right")
    tracker.update([h1])

    # Handedness label flips, but position is close
    h2 = _create_hand(0.11, 0.21, 0.29, handedness="Left")
    res = tracker.update([h2])
    assert len(res) == 1
    assert res[0][1] == 0  # Still ID 0


def test_hand_tracker_reset() -> None:
    tracker = HandTracker()
    h = _create_hand(0.1, 0.2, 0.3)
    tracker.update([h])
    tracker.reset()

    h_new = _create_hand(0.1, 0.2, 0.3)
    res = tracker.update([h_new])
    assert len(res) == 1
    assert res[0][1] == 0  # Reset makes next ID 0 again
