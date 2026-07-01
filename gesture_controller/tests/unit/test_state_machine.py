import numpy as np
import pytest
from unittest.mock import MagicMock
from gesture_controller.core.state_machine import (
    GestureFSM, FSMState, FSMTransition, GestureFSMManager, compile_condition
)
from gesture_controller.models.data_types import FeatureVector

@pytest.fixture
def test_fsm() -> GestureFSM:
    # State transitions:
    # Idle -> Active (if index_extended == True)
    # Active -> Trigger (if index_curl > 0.8)
    # Trigger (action: OS:MinimizeActiveWindow, cooldown_ms: 500)
    
    cond_active = compile_condition("index_extended == True", {})
    cond_trigger = compile_condition("index_curl > 0.8", {})
    cond_abort = compile_condition("index_extended == False", {})
    
    idle_state = FSMState(
        id="Idle",
        transitions=[FSMTransition("Active", "index_extended == True", cond_active)]
    )
    active_state = FSMState(
        id="Active",
        min_duration_ms=100.0,
        max_duration_ms=1000.0,
        transitions=[
            FSMTransition("Trigger", "index_curl > 0.8", cond_trigger),
            FSMTransition("Idle", "index_extended == False", cond_abort, is_abort=True)
        ]
    )
    trigger_state = FSMState(
        id="Trigger",
        is_terminal=True,
        action="OS:MinimizeActiveWindow",
        cooldown_ms=500.0
    )
    
    states = {"Idle": idle_state, "Active": active_state, "Trigger": trigger_state}
    return GestureFSM("MinimizeWindow", 1, "dynamic", states)

@pytest.fixture
def fv_idle() -> FeatureVector:
    return FeatureVector(
        thumb_extended=False, index_extended=False, middle_extended=False, ring_extended=False, pinky_extended=False,
        thumb_curl=0.0, index_curl=0.0, middle_curl=0.0, ring_curl=0.0, pinky_curl=0.0,
        hand_openness=0.0, pinch_distance=0.5, palm_normal=np.zeros(3), palm_center=np.zeros(3), index_tip=np.zeros(3),
        palm_velocity=np.zeros(3), palm_velocity_magnitude=0.0, palm_acceleration=np.zeros(3), index_tip_velocity=np.zeros(3),
        timestamp=0.0
    )

@pytest.fixture
def fv_active() -> FeatureVector:
    return FeatureVector(
        thumb_extended=False, index_extended=True, middle_extended=False, ring_extended=False, pinky_extended=False,
        thumb_curl=0.0, index_curl=0.0, middle_curl=0.0, ring_curl=0.0, pinky_curl=0.0,
        hand_openness=0.2, pinch_distance=0.5, palm_normal=np.zeros(3), palm_center=np.zeros(3), index_tip=np.zeros(3),
        palm_velocity=np.zeros(3), palm_velocity_magnitude=0.0, palm_acceleration=np.zeros(3), index_tip_velocity=np.zeros(3),
        timestamp=0.0
    )

@pytest.fixture
def fv_curled() -> FeatureVector:
    return FeatureVector(
        thumb_extended=False, index_extended=True, middle_extended=False, ring_extended=False, pinky_extended=False,
        thumb_curl=0.0, index_curl=0.9, middle_curl=0.0, ring_curl=0.0, pinky_curl=0.0,
        hand_openness=0.2, pinch_distance=0.5, palm_normal=np.zeros(3), palm_center=np.zeros(3), index_tip=np.zeros(3),
        palm_velocity=np.zeros(3), palm_velocity_magnitude=0.0, palm_acceleration=np.zeros(3), index_tip_velocity=np.zeros(3),
        timestamp=0.0
    )

def test_fsm_initial_state(test_fsm: GestureFSM) -> None:
    assert test_fsm.current_state == "Idle"

def test_fsm_transition_to_active(test_fsm: GestureFSM, fv_active: FeatureVector) -> None:
    event = test_fsm.evaluate(fv_active, timestamp=1.0)
    assert event is None
    assert test_fsm.current_state == "Active"
    assert test_fsm.state_entered_at == 1.0

def test_fsm_min_duration_guard(test_fsm: GestureFSM, fv_active: FeatureVector, fv_curled: FeatureVector) -> None:
    # 1. Idle -> Active
    test_fsm.evaluate(fv_active, timestamp=0.0)
    assert test_fsm.current_state == "Active"
    
    # 2. Try to transition to Trigger immediately (50ms elapsed, min_duration_ms is 100ms)
    fv_curled.timestamp = 0.05
    event = test_fsm.evaluate(fv_curled, timestamp=0.05)
    assert event is None
    assert test_fsm.current_state == "Active"  # Stays active because duration < min_duration

    # 3. Transition after min_duration (150ms elapsed)
    fv_curled.timestamp = 0.15
    event = test_fsm.evaluate(fv_curled, timestamp=0.15)
    assert event is not None
    assert event.gesture_name == "MinimizeWindow"
    assert event.action == "OS:MinimizeActiveWindow"
    assert test_fsm.current_state == "Idle"  # Resets to Idle after terminal trigger
    assert test_fsm.is_in_cooldown is True

def test_fsm_state_timeout(test_fsm: GestureFSM, fv_active: FeatureVector) -> None:
    # 1. Idle -> Active
    test_fsm.evaluate(fv_active, timestamp=0.0)
    assert test_fsm.current_state == "Active"
    
    # 2. Frame after 1100ms (max_duration is 1000ms)
    fv_active.timestamp = 1.1
    event = test_fsm.evaluate(fv_active, timestamp=1.1)
    assert event is None
    assert test_fsm.current_state == "Idle"  # Timeout reset

def test_fsm_cooldown_guard(test_fsm: GestureFSM, fv_active: FeatureVector, fv_curled: FeatureVector) -> None:
    # 1. Trigger gesture
    test_fsm.evaluate(fv_active, timestamp=0.0)
    test_fsm.evaluate(fv_curled, timestamp=0.15)
    assert test_fsm.is_in_cooldown is True
    
    # 2. Try to re-trigger during cooldown (200ms elapsed, cooldown is 500ms)
    event = test_fsm.evaluate(fv_active, timestamp=0.2)
    assert event is None
    assert test_fsm.is_in_cooldown is True
    
    # 3. Exited cooldown (600ms elapsed)
    event2 = test_fsm.evaluate(fv_active, timestamp=0.75)
    assert event2 is None
    assert test_fsm.is_in_cooldown is False
    assert test_fsm.current_state == "Active"  # Successfully processed active transition again

def test_fsm_abort(test_fsm: GestureFSM, fv_active: FeatureVector, fv_idle: FeatureVector) -> None:
    # 1. Idle -> Active
    test_fsm.evaluate(fv_active, timestamp=0.0)
    assert test_fsm.current_state == "Active"
    
    # 2. Feed abort condition after min duration
    fv_idle.timestamp = 0.15
    event = test_fsm.evaluate(fv_idle, timestamp=0.15)
    assert event is None
    assert test_fsm.current_state == "Idle"  # Aborted to Idle
