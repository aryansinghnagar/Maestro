from gesture_controller.core import protocols


def test_protocols_exist() -> None:
    # Just verify that the protocols can be imported and resolved
    assert hasattr(protocols, "FrameSource")
    assert hasattr(protocols, "InferenceBackend")
    assert hasattr(protocols, "GestureRecognizer")
    assert hasattr(protocols, "InputEmitter")
