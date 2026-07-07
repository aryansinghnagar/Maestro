import numpy as np
import pytest
from hypothesis import given, strategies as st, settings
from hypothesis.extra.numpy import arrays

from gesture_controller.models.data_types import Hand, Landmark3D, FeatureVector
from gesture_controller.vision.one_euro_filter import OneEuroFilter
from gesture_controller.models.feature_engineering import compute_features
from gesture_controller.models.dtw_matcher import fast_dtw_distance
from gesture_controller.core.state_machine import (
    GestureFSM,
    FSMState,
    FSMTransition,
    compile_condition,
)


# -----------------------------------------------------------------------------
# 1. DTW Symmetry Property Test
# -----------------------------------------------------------------------------
@settings(deadline=None)  # Disable deadline to allow Numba compilation on first run
@given(
    s1=arrays(
        np.float64,
        (5, 3),
        elements=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    ),
    s2=arrays(
        np.float64,
        (6, 3),
        elements=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    ),
)
def test_dtw_symmetry(s1: np.ndarray, s2: np.ndarray) -> None:
    dist1 = fast_dtw_distance(s1, s2)
    dist2 = fast_dtw_distance(s2, s1)
    assert pytest.approx(dist1, abs=1e-7) == dist2


# -----------------------------------------------------------------------------
# 2. One-Euro Monotonic Convergence Property Test
# -----------------------------------------------------------------------------
@given(
    initial_val=st.floats(min_value=-50.0, max_value=50.0),
    target_val=st.floats(min_value=-50.0, max_value=50.0),
)
def test_one_euro_monotonic_convergence(initial_val: float, target_val: float) -> None:
    # Filter configuration
    config = {
        "filtering": {
            "one_euro": {"min_cutoff": 1.0, "beta": 0.007, "derivate_cutoff": 1.0},
            "dynamic_adaptation": {"lighting_enabled": False, "depth_scaling_enabled": False},
        }
    }
    filt = OneEuroFilter(config)

    # Pre-allocate inputs (21 landmarks x 3 axes)
    initial_lms = np.full((21, 3), initial_val, dtype=np.float64)
    target_lms = np.full((21, 3), target_val, dtype=np.float64)

    # Step 0: Initialize
    filtered, _, _ = filt.filter(initial_lms, timestamp=0.0)

    # Feed target repeatedly at steady 30 FPS steps
    prev_dist = np.linalg.norm(filtered - target_lms)

    for i in range(1, 20):
        filtered, _, _ = filt.filter(target_lms, timestamp=i * (1.0 / 30.0))
        curr_dist = np.linalg.norm(filtered - target_lms)
        # Verify that distance is non-increasing (moving monotonically closer)
        assert curr_dist <= prev_dist + 1e-9
        prev_dist = curr_dist


# -----------------------------------------------------------------------------
# 3. Feature Engineering Scale & Translation Invariance
# -----------------------------------------------------------------------------
# Generate 21 landmarks where index MCP (5) and index PIP (6) have a non-zero distance
@st.composite
def generate_landmarks(draw):
    points = []
    for i in range(21):
        x = draw(st.floats(min_value=-10.0, max_value=10.0))
        y = draw(st.floats(min_value=-10.0, max_value=10.0))
        z = draw(st.floats(min_value=-10.0, max_value=10.0))
        points.append(np.array([x, y, z]))

    # Enforce non-zero distance between 5 and 6
    if np.linalg.norm(points[5] - points[6]) < 1e-3:
        points[6] += np.array([0.1, 0.1, 0.1])

    return [Landmark3D(x=float(p[0]), y=float(p[1]), z=float(p[2])) for p in points]


@given(
    landmarks=generate_landmarks(),
    dx=st.floats(min_value=-100.0, max_value=100.0),
    dy=st.floats(min_value=-100.0, max_value=100.0),
    dz=st.floats(min_value=-100.0, max_value=100.0),
    scale=st.floats(min_value=0.01, max_value=100.0),
)
def test_feature_invariance(
    landmarks: list[Landmark3D], dx: float, dy: float, dz: float, scale: float
) -> None:
    # 1. Original hand
    hand_orig = Hand(landmarks=tuple(landmarks), handedness="Right", confidence=0.95)

    # 2. Translated & scaled hand
    lms_transformed = [
        Landmark3D(x=(l.x + dx) * scale, y=(l.y + dy) * scale, z=(l.z + dz) * scale)
        for l in landmarks
    ]
    hand_transformed = Hand(landmarks=tuple(lms_transformed), handedness="Right", confidence=0.95)

    # Empty velocity/acceleration
    vel = np.zeros((21, 3))
    acc = np.zeros((21, 3))

    fv_orig = compute_features(hand_orig, vel, acc, timestamp=0.0, frame_number=0)
    fv_trans = compute_features(hand_transformed, vel, acc, timestamp=0.0, frame_number=0)

    # Assert invariances
    assert fv_orig.thumb_extended == fv_trans.thumb_extended
    assert fv_orig.index_extended == fv_trans.index_extended
    assert fv_orig.middle_extended == fv_trans.middle_extended
    assert fv_orig.ring_extended == fv_trans.ring_extended
    assert fv_orig.pinky_extended == fv_trans.pinky_extended

    assert pytest.approx(fv_orig.thumb_curl, abs=1e-4) == fv_trans.thumb_curl
    assert pytest.approx(fv_orig.index_curl, abs=1e-4) == fv_trans.index_curl
    assert pytest.approx(fv_orig.middle_curl, abs=1e-4) == fv_trans.middle_curl
    assert pytest.approx(fv_orig.ring_curl, abs=1e-4) == fv_trans.ring_curl
    assert pytest.approx(fv_orig.pinky_curl, abs=1e-4) == fv_trans.pinky_curl

    assert pytest.approx(fv_orig.hand_openness, abs=1e-4) == fv_trans.hand_openness
    assert pytest.approx(fv_orig.pinch_distance, abs=1e-4) == fv_trans.pinch_distance


# -----------------------------------------------------------------------------
# 4. FSM Never Single Frame Trigger Property Test
# -----------------------------------------------------------------------------
@given(index_ext=st.booleans(), index_curl_val=st.floats(min_value=0.0, max_value=1.0))
def test_fsm_never_single_frame_trigger(index_ext: bool, index_curl_val: float) -> None:
    # Set up FSM that requires Active state (min 100ms) before terminal Trigger state
    cond_active = compile_condition("index_extended == True", {})
    cond_trigger = compile_condition("index_curl > 0.8", {})
    cond_abort = compile_condition("index_extended == False", {})

    idle_state = FSMState(
        id="Idle", transitions=[FSMTransition("Active", "index_extended == True", cond_active)]
    )
    active_state = FSMState(
        id="Active",
        min_duration_ms=100.0,
        max_duration_ms=1000.0,
        transitions=[
            FSMTransition("Trigger", "index_curl > 0.8", cond_trigger),
            FSMTransition("Idle", "index_extended == False", cond_abort, is_abort=True),
        ],
    )
    trigger_state = FSMState(
        id="Trigger", is_terminal=True, action="OS:MinimizeActiveWindow", cooldown_ms=500.0
    )

    states = {"Idle": idle_state, "Active": active_state, "Trigger": trigger_state}
    fsm = GestureFSM("MinimizeWindow", 1, "dynamic", states)

    # Create FeatureVector for frame 1 (eval 1)
    fv = FeatureVector(
        thumb_extended=False,
        index_extended=index_ext,
        middle_extended=False,
        ring_extended=False,
        pinky_extended=False,
        thumb_curl=0.0,
        index_curl=index_curl_val,
        middle_curl=0.0,
        ring_curl=0.0,
        pinky_curl=0.0,
        hand_openness=0.0,
        pinch_distance=0.5,
        palm_normal=np.zeros(3),
        palm_center=np.zeros(3),
        index_tip=np.zeros(3),
        palm_velocity=np.zeros(3),
        palm_velocity_magnitude=0.0,
        palm_acceleration=np.zeros(3),
        index_tip_velocity=np.zeros(3),
        timestamp=1.0,
    )

    event = fsm.evaluate(fv, timestamp=1.0)

    # Assert FSM did not trigger
    assert event is None
    assert fsm.current_state != "Trigger"
