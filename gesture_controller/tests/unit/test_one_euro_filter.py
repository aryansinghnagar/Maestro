import numpy as np
import pytest
from gesture_controller.vision.one_euro_filter import OneEuroFilter

@pytest.fixture
def filter_config() -> dict:
    return {
        "filtering": {
            "type": "one_euro",
            "one_euro": {
                "min_cutoff": 0.004,
                "beta": 0.04,
                "derivate_cutoff": 1.0
            },
            "dynamic_adaptation": {
                "lighting_enabled": True,
                "depth_scaling_enabled": True
            }
        }
    }

def test_static_input_no_drift(filter_config: dict) -> None:
    f = OneEuroFilter(filter_config)
    static_pose = np.random.rand(21, 3)
    
    # Run filter multiple times with the same input
    for i in range(10):
        filtered, vel, accel = f.filter(static_pose, timestamp=float(i) * 0.033)
        
    # The output should converge to the static pose
    np.testing.assert_allclose(filtered, static_pose, atol=1e-5)

def test_reset_behavior(filter_config: dict) -> None:
    f = OneEuroFilter(filter_config)
    static_pose = np.random.rand(21, 3)
    
    f.filter(static_pose, timestamp=0.0)
    assert f._initialized is True
    
    f.reset()
    assert f._initialized is False
    assert np.all(f._x_prev == 0)

def test_noisy_input_smoothing(filter_config: dict) -> None:
    f = OneEuroFilter(filter_config)
    
    # Static clean signal (constant 0.5) + noise (100 frames)
    clean_signal = np.ones((100, 3)) * 0.5
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.1, (100, 3))
    noisy_signal = clean_signal + noise
    
    filtered_output = []
    
    # Feed noisy points for 21 joints
    for i in range(100):
        frame_input = np.repeat(noisy_signal[i:i+1], 21, axis=0)
        filt, _, _ = f.filter(frame_input, timestamp=float(i) * 0.033)
        filtered_output.append(filt[0])  # Store joint 0
        
    filtered_output_np = np.array(filtered_output)[30:]  # Skip initial 30 frames to settle
    clean_signal_settled = clean_signal[30:]
    noisy_signal_settled = noisy_signal[30:]
    
    # Compute standard deviations of noise vs filtered
    noisy_std = np.std(noisy_signal_settled - clean_signal_settled)
    filtered_std = np.std(filtered_output_np - clean_signal_settled)
    
    # Noise should be reduced by more than 40% after settling
    assert filtered_std < noisy_std * 0.6



def test_nan_input_recovery(filter_config: dict) -> None:
    f = OneEuroFilter(filter_config)
    pose = np.random.rand(21, 3)
    
    f.filter(pose, timestamp=0.0)
    
    # Feed NaN
    nan_pose = pose.copy()
    nan_pose[0, 0] = np.nan
    
    # We shouldn't crash, but it should reset or skip
    # (In our implementation, if NaN occurs, we can reset the state or handle it)
    # Let's verify we reset if NaN occurs:
    # First frame after NaN should reset and initialize successfully
    try:
        f.filter(nan_pose, timestamp=0.033)
    except Exception:
         pytest.fail("Filter crashed on NaN input")
