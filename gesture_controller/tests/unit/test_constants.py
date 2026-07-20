from gesture_controller.vision import constants


def test_constants_definitions() -> None:
    assert constants.FRAME_WIDTH == 640
    assert constants.FRAME_HEIGHT == 480
    assert constants.FRAME_SIZE == 640 * 480 * 3
    assert constants.NUM_LANDMARKS == 21
    assert constants.DTW_FEATURE_DIMS == 63
