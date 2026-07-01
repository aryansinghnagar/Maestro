import numpy as np
import pytest
from gesture_controller.core.state_machine import compile_condition
from gesture_controller.models.data_types import FeatureVector

@pytest.fixture
def dummy_fv() -> FeatureVector:
    return FeatureVector(
        thumb_extended=True,
        index_extended=True,
        middle_extended=False,
        ring_extended=False,
        pinky_extended=False,
        thumb_curl=0.1,
        index_curl=0.0,
        middle_curl=0.9,
        ring_curl=0.9,
        pinky_curl=0.9,
        hand_openness=0.2,
        pinch_distance=0.5,
        palm_normal=np.array([0.0, 0.0, 1.0], dtype=np.float64),
        palm_center=np.array([0.5, 0.5, 0.5], dtype=np.float64),
        index_tip=np.array([0.5, 0.3, 0.2], dtype=np.float64),
        palm_velocity=np.array([0.1, -0.4, 0.05], dtype=np.float64),
        palm_velocity_magnitude=0.41,
        palm_acceleration=np.array([0.0, 0.0, 0.0], dtype=np.float64),
        index_tip_velocity=np.array([0.0, 1.2, -0.1], dtype=np.float64),
        handedness="Right",
        confidence=1.0,
        timestamp=0.0,
        frame_number=0
    )

def test_simple_boolean_conditions(dummy_fv: FeatureVector) -> None:
    # Test equality
    fn = compile_condition("index_extended == True", {})
    assert fn(dummy_fv) is True
    
    fn2 = compile_condition("middle_extended == True", {})
    assert fn2(dummy_fv) is False

def test_logical_operators(dummy_fv: FeatureVector) -> None:
    # Test 'and'
    fn = compile_condition("index_extended == True and middle_extended == False", {})
    assert fn(dummy_fv) is True
    
    # Test 'or'
    fn2 = compile_condition("middle_extended == True or pinky_extended == True", {})
    assert fn2(dummy_fv) is False
    
    # Test 'not'
    fn3 = compile_condition("not middle_extended", {})
    assert fn3(dummy_fv) is True

def test_numeric_comparisons(dummy_fv: FeatureVector) -> None:
    # Test vector components
    fn = compile_condition("index_tip_velocity_y > 1.0", {})
    assert fn(dummy_fv) is True
    
    fn2 = compile_condition("index_tip_velocity_z < 0.0", {})
    assert fn2(dummy_fv) is True
    
    fn3 = compile_condition("palm_velocity_magnitude <= 0.5", {})
    assert fn3(dummy_fv) is True

def test_threshold_constants(dummy_fv: FeatureVector) -> None:
    thresholds = {"FLICK_VEL": 1.0, "PALM_STABLE": 0.2}
    fn = compile_condition("index_tip_velocity_y > FLICK_VEL", thresholds)
    assert fn(dummy_fv) is True
    
    fn2 = compile_condition("palm_velocity_magnitude < PALM_STABLE", thresholds)
    assert fn2(dummy_fv) is False

def test_abs_function_support(dummy_fv: FeatureVector) -> None:
    fn = compile_condition("abs(palm_velocity_y) > 0.3", {})
    assert fn(dummy_fv) is True

def test_injection_security_raises() -> None:
    # Attempting eval/exec or import inside conditions should raise ValueError
    with pytest.raises(ValueError):
        compile_condition("eval('1+1')", {})
        
    with pytest.raises(ValueError):
        compile_condition("__import__('os').system('dir')", {})

    with pytest.raises((ValueError, SyntaxError)):
        compile_condition("index_extended == True; import sys", {})

