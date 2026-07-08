import time
import numpy as np
from gesture_controller.vision.one_euro_filter import OneEuroFilter
from gesture_controller.models.feature_engineering import compute_features
from gesture_controller.core.state_machine import GestureFSMManager
from gesture_controller.models.dtw_matcher import CustomGestureMatcher
from gesture_controller.models.data_types import Hand, Landmark3D, FeatureVector
from gesture_controller.core.event_bus import EventBus
from pathlib import Path
from typing import Any


def run_profile() -> None:
    print("=== Maestro Latency Profiling Harness ===")

    config = {
        "engine": {"global_cooldown_ms": 200.0, "max_hands": 2},
        "config": {"default_thresholds": {"pinch_distance": 0.05, "swipe_velocity": 0.5}},
        "gestures": [
            {
                "name": "DummySwipe",
                "type": "static",
                "priority": 1,
                "states": [
                    {
                        "id": "Idle",
                        "transitions": [{"to": "Active", "condition": "swipe_velocity > 0.5"}],
                    },
                    {"id": "Active", "is_terminal": True},
                ],
            }
        ],
    }

    event_bus = EventBus()
    filter_instance = OneEuroFilter(config)
    fsm_manager = GestureFSMManager(config, event_bus)
    custom_matcher = CustomGestureMatcher(config)

    # Pre-populate matcher with a dummy template to ensure match logic is executed
    custom_matcher._templates["dummy"] = {
        "template": np.zeros((60, 63), dtype=np.float64),
        "threshold": 0.15,
        "action": "KeyPress:Ctrl+C",
    }
    custom_matcher._buffer_full = True

    landmarks = tuple(Landmark3D(x=0.0, y=0.0, z=0.0) for _ in range(21))
    hand = Hand(landmarks=landmarks, handedness="Right", confidence=0.9)
    lm_array = np.zeros((21, 3), dtype=np.float64)

    iterations = 1000

    # Benchmark: np.array allocation
    alloc_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _arr = np.array([[l.x, l.y, l.z] for l in landmarks], dtype=np.float64)
        t1 = time.perf_counter()
        alloc_times.append((t1 - t0) * 1e6)

    # Benchmark: OneEuroFilter.filter
    filter_times = []
    for i in range(iterations):
        t0 = time.perf_counter()
        _filtered, _vel, _acc = filter_instance.filter(
            lm_array, float(i) / 30.0, lighting_metric=None, depth_metric=0.05
        )
        t1 = time.perf_counter()
        filter_times.append((t1 - t0) * 1e6)

    # Benchmark: compute_features
    vel = np.zeros((21, 3), dtype=np.float64)
    acc = np.zeros((21, 3), dtype=np.float64)
    feat_times = []
    for i in range(iterations):
        t0 = time.perf_counter()
        features = compute_features(hand, vel, acc, float(i) / 30.0, i)
        t1 = time.perf_counter()
        feat_times.append((t1 - t0) * 1e6)

    # Benchmark: FSM evaluate
    fsm_times = []
    feat_vector = compute_features(hand, vel, acc, 0.0, 0)
    for i in range(iterations):
        feat_vector.timestamp = float(i) / 30.0
        t0 = time.perf_counter()
        _event = fsm_manager.evaluate(feat_vector, correlation_id="", track_id=0)
        t1 = time.perf_counter()
        fsm_times.append((t1 - t0) * 1e6)

    # Benchmark: CustomGestureMatcher.match
    match_times = []
    for i in range(iterations):
        t0 = time.perf_counter()
        _event = custom_matcher.match(float(i) / 30.0)
        t1 = time.perf_counter()
        match_times.append((t1 - t0) * 1e6)

    def print_stats(name: str, times: list[float]) -> None:
        sorted_times = sorted(times)
        p50 = sorted_times[int(len(sorted_times) * 0.50)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        print(f"| {name:<30} | {p50:8.1f} | {p95:8.1f} | {p99:8.1f} |")

    print(f"\nProfiling results over {iterations} iterations:")
    print("-" * 65)
    print(
        f"| {'Component':<30} | {'P50 (\u00b5s)':<8} | {'P95 (\u00b5s)':<8} | {'P99 (\u00b5s)':<8} |"
    )
    print("-" * 65)
    print_stats("np.array allocation", alloc_times)
    print_stats("OneEuroFilter.filter()", filter_times)
    print_stats("compute_features()", feat_times)
    print_stats("GestureFSMManager.evaluate()", fsm_times)
    print_stats("CustomGestureMatcher.match()", match_times)
    print("-" * 65)


if __name__ == "__main__":
    run_profile()
