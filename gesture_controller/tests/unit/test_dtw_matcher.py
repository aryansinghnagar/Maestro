import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from gesture_controller.models.data_types import Hand, Landmark3D
from gesture_controller.models.dtw_matcher import (
    DTWMatcher,
    CustomGestureMatcher,
    fast_dtw_distance,
    dtw_distance_batch,
    to_hand_frame,
    normalize_sequence
)

def test_fast_dtw_distance() -> None:
    # Identical sequences should result in 0 distance
    s1 = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    assert fast_dtw_distance(s1, s1) == 0.0
    
    # Distant sequences
    s2 = np.array([[1.0, 2.0], [5.0, 6.0]], dtype=np.float64)
    assert fast_dtw_distance(s1, s2) > 0.0
    
    # Test symmetry: dtw(a, b) == dtw(b, a)
    assert fast_dtw_distance(s1, s2) == pytest.approx(fast_dtw_distance(s2, s1), abs=1e-7)

def test_dtw_distance_batch() -> None:
    query = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    templates = np.array([
        [[10.0, 20.0], [30.0, 40.0]], # Index 0: very distant
        [[1.0, 2.0], [3.1, 4.1]],     # Index 1: close
    ], dtype=np.float64)
    thresholds = np.array([0.15, 0.15], dtype=np.float64)
    
    best_idx, best_dist = dtw_distance_batch(query, templates, thresholds)
    assert best_idx == 1
    assert best_dist < 0.15

def test_to_hand_frame() -> None:
    landmarks = [Landmark3D(x=float(i), y=float(i), z=float(i)) for i in range(21)]
    res = to_hand_frame(landmarks, "Right")
    assert len(res) == 21
    # Wrist should be translated to 0
    assert res[0].x == 0.0
    assert res[0].y == 0.0
    assert res[0].z == 0.0

def test_normalize_sequence() -> None:
    seq = [np.array([float(i)] * 63) for i in range(10)]
    res = normalize_sequence(seq, target_len=60)
    assert res.shape == (60, 63)

def test_custom_gesture_matcher_empty_buffer_returns_none(tmp_path: Path) -> None:
    matcher = CustomGestureMatcher()
    matcher._template_dir = tmp_path
    matcher.load_templates(tmp_path)
    
    assert matcher.match(0.0) is None

def test_custom_gesture_matcher_matching(tmp_path: Path) -> None:
    # 1. Create a dummy template file
    template_data = np.zeros((60, 63), dtype=np.float64)
    # Fill first landmark coord of template with simple ramp
    for i in range(60):
        template_data[i, 0] = float(i) / 60.0
        
    template_json = {
        "name": "RampGesture",
        "action": "KeyPress:Right",
        "threshold": 0.15,
        "template": template_data.tolist()
    }
    
    template_file = tmp_path / "ramp.json"
    with open(template_file, "w", encoding="utf-8") as f:
        json.dump(template_json, f)
        
    matcher = CustomGestureMatcher()
    matcher._template_dir = tmp_path
    matcher.load_templates(tmp_path)
    
    # Check loaded
    assert "RampGesture" in matcher._templates
    
    # 2. Feed matching landmarks into buffer
    matcher._buffer_full = True
    matcher._buffer = template_data.copy()
    
    event = matcher.match(0.0)
    assert event is not None
    assert event.gesture_name == "RampGesture"
    assert event.action == "KeyPress:Right"
    assert event.confidence > 0.8

def test_custom_gesture_matcher_cooldown(tmp_path: Path) -> None:
    template_data = np.zeros((60, 63), dtype=np.float64)
    template_json = {
        "name": "RampGesture",
        "action": "KeyPress:Right",
        "threshold": 0.15,
        "template": template_data.tolist()
    }
    with open(tmp_path / "ramp.json", "w", encoding="utf-8") as f:
        json.dump(template_json, f)
        
    config = {
        "dtw": {
            "cooldown_ms": 100.0,
            "refractory_ms": 200.0
        }
    }
    matcher = CustomGestureMatcher(config)
    matcher._template_dir = tmp_path
    matcher.load_templates(tmp_path)
    
    matcher._buffer_full = True
    matcher._buffer = template_data.copy()
    
    # First match succeeds
    event = matcher.match(0.0)
    assert event is not None
    
    # Refill buffer as it is reset on success
    matcher._buffer_full = True
    matcher._buffer = template_data.copy()
    
    # Global cooldown fails
    event = matcher.match(0.05)
    assert event is None
    
    # Same gesture refractory fails
    event = matcher.match(0.15)
    assert event is None
    
    # Cooldown & refractory passed succeeds
    event = matcher.match(0.25)
    assert event is not None

def test_custom_gesture_matcher_reset() -> None:
    matcher = CustomGestureMatcher()
    matcher._buffer_full = True
    matcher._buffer_idx = 10
    matcher._frame_count = 100
    
    matcher.reset()
    assert matcher._buffer_full is False
    assert matcher._buffer_idx == 0
    assert matcher._frame_count == 0
    assert np.all(matcher._buffer == 0.0)
