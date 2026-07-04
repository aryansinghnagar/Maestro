import time
import pytest
import numpy as np
from pathlib import Path

from gesture_controller.vision.one_euro_filter import OneEuroFilter
from gesture_controller.models.dtw_matcher import CustomGestureMatcher
from gesture_controller.models.data_types import Hand, Landmark3D
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.state_machine import GestureFSMManager
from gesture_controller.models.feature_engineering import compute_features

@pytest.fixture(scope="module")
def default_config() -> dict:
    default_yaml = Path(__file__).parent.parent.parent / "data" / "default_config.yaml"
    cfg = ConfigManager(default_yaml if default_yaml.exists() else None)
    
    # Merge predefined gestures
    import yaml
    gestures_yaml = Path(__file__).parent.parent.parent / "data" / "predefined_gestures.yaml"
    if gestures_yaml.exists():
        with open(gestures_yaml, "r") as f:
            gestures_config = yaml.safe_load(f) or {}
        cfg._config.update(gestures_config)
    return cfg._config

@pytest.fixture
def mock_hand() -> Hand:
    lms = tuple(Landmark3D(x=0.5, y=0.5, z=0.0) for _ in range(21))
    return Hand(landmarks=lms, handedness="Right", confidence=1.0)

def test_bench_one_euro(benchmark, default_config) -> None:
    filt = OneEuroFilter(default_config)
    coords = np.random.rand(21, 3)
    
    def run_update():
        filt.filter(coords, timestamp=time.monotonic())
        
    benchmark(run_update)

def test_bench_dtw(benchmark, default_config) -> None:
    matcher = CustomGestureMatcher(default_config)
    # Populate templates artificially to benchmark JIT distance computation
    template_seq = np.random.rand(20, 21, 3)
    matcher._templates["MockCustom"] = {
        "sequence": template_seq,
        "action": "KeyPress:A",
        "threshold": 5.0
    }
    
    # Fill rolling buffer
    for _ in range(25):
        lms = tuple(Landmark3D(x=x, y=y, z=z) for x, y, z in np.random.rand(21, 3))
        h = Hand(landmarks=lms, handedness="Right", confidence=1.0)
        matcher.update_buffer(h)
        
    def run_match():
        matcher.match(time.monotonic())
        
    benchmark(run_match)

def test_bench_fsm(benchmark, default_config) -> None:
    from gesture_controller.core.event_bus import EventBus
    eb = EventBus()
    fsm_mgr = GestureFSMManager(default_config, eb)
    
    h = Hand(landmarks=tuple(Landmark3D(x=0.5, y=0.5, z=0.0) for _ in range(21)), handedness="Right", confidence=1.0)
    features = compute_features(h, np.zeros((21, 3)), np.zeros((21, 3)), time.monotonic(), 0)
    
    def run_fsm():
        fsm_mgr.evaluate(features)
        
    benchmark(run_fsm)

def test_bench_full_pipeline(benchmark, default_config, mock_hand) -> None:
    from gesture_controller.core.event_bus import EventBus
    eb = EventBus()
    fsm_mgr = GestureFSMManager(default_config, eb)
    filt = OneEuroFilter(default_config)
    matcher = CustomGestureMatcher(default_config)
    
    latencies = []
    
    def run_pipeline():
        start_time = time.perf_counter()
        
        # 1. Smoothing
        lm_array = np.array([[l.x, l.y, l.z] for l in mock_hand.landmarks], dtype=np.float64)
        filtered, velocity, acceleration = filt.filter(lm_array, time.monotonic())
        
        smoothed_landmarks = tuple(Landmark3D(x=f[0], y=f[1], z=f[2]) for f in filtered)
        smoothed_hand = Hand(landmarks=smoothed_landmarks, handedness=mock_hand.handedness, confidence=1.0)
        
        # 2. Features
        features = compute_features(smoothed_hand, velocity, acceleration, time.monotonic(), 0)
        
        # 3. FSM
        event = fsm_mgr.evaluate(features)
        if not event:
            event = matcher.match(time.monotonic())
            
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        latencies.append(elapsed_ms)
        
    benchmark(run_pipeline)
    
    # S4-5: E2E processing latency must be < 50ms (usually < 2ms in Python-optimized/Numba pipeline)
    p95_latency = np.percentile(latencies, 95)
    assert p95_latency < 50.0, f"p95 latency is {p95_latency:.2f}ms, which exceeds 50ms limit!"
