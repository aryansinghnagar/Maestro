from gesture_controller.models import hand_topology


def test_hand_topology() -> None:
    assert len(hand_topology.CONNECTIONS) > 0
    assert "thumb" in hand_topology.FINGER_LANDMARKS
    assert hand_topology.WRIST == 0
    assert hand_topology.INDEX_TIP == 8
