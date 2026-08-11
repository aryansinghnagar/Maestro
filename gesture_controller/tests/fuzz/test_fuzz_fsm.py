import numpy as np
import pytest
from hypothesis import given, strategies as st
from gesture_controller.core.state_machine import GestureFSM, FSMState, FSMTransition
from gesture_controller.models.data_types import FeatureVector


@given(
    pinch_dist=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    dt=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_fuzz_gesture_fsm(pinch_dist: float, dt: float) -> None:
    idle_state = FSMState(
        id="Idle",
        transitions=[
            FSMTransition(
                target_state="Pinched",
                condition="pinch_distance < 0.05",
                condition_fn=lambda fv: fv.pinch_distance < 0.05,
            )
        ],
    )
    pinched_state = FSMState(id="Pinched", is_terminal=True, action="click")

    fsm = GestureFSM(
        name="fuzz_pinch",
        priority=1,
        gesture_type="static",
        states={"Idle": idle_state, "Pinched": pinched_state},
        initial_state="Idle",
    )

    zero_vec3 = np.zeros(3, dtype=np.float32)
    fv = FeatureVector(
        thumb_extended=True,
        index_extended=True,
        middle_extended=False,
        ring_extended=False,
        pinky_extended=False,
        thumb_curl=0.1,
        index_curl=0.1,
        middle_curl=0.9,
        ring_curl=0.9,
        pinky_curl=0.9,
        hand_openness=0.5,
        pinch_distance=pinch_dist,
        palm_normal=zero_vec3,
        palm_center=zero_vec3,
        index_tip=zero_vec3,
        palm_velocity=zero_vec3,
        palm_velocity_magnitude=0.0,
        palm_acceleration=zero_vec3,
        index_tip_velocity=zero_vec3,
    )

    event = fsm.evaluate(fv, timestamp=1.0)
    assert event is None or hasattr(event, "gesture_name")
