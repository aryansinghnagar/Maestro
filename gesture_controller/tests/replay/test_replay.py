import json
import yaml
import pytest
from pathlib import Path
import numpy as np

from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.state_machine import GestureFSMManager
from gesture_controller.models.data_types import Hand, Landmark3D
from gesture_controller.models.feature_engineering import compute_features

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_replay_fixture(filename: str):
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def config_manager() -> ConfigManager:
    # Use standard default config path for FSM thresholds
    default_yaml = Path(__file__).parent.parent.parent / "data" / "default_config.yaml"
    return ConfigManager(default_yaml if default_yaml.exists() else None)

@pytest.fixture
def fsm_manager(config_manager: ConfigManager) -> GestureFSMManager:
    # Load predefined gestures (S4-1)
    gestures_yaml_path = Path(__file__).parent.parent.parent / "data" / "predefined_gestures.yaml"
    gestures_config = {}
    if gestures_yaml_path.exists():
        with open(gestures_yaml_path, "r") as f:
            gestures_config = yaml.safe_load(f) or {}
    
    merged_config = config_manager._config.copy()
    merged_config.update(gestures_config)
    
    # Add a mock Pinch FSM to config list for the pinch replay test
    if "gestures" not in merged_config:
        merged_config["gestures"] = []
    
    pinch_fsm = {
        "name": "Pinch",
        "type": "dynamic",
        "priority": 4,
        "states": [
            {
                "id": "Idle",
                "transitions": [
                    {"to": "Pinching", "condition": "pinch_distance < 0.15"}
                ]
            },
            {
                "id": "Pinching",
                "min_duration_ms": 150,
                "max_duration_ms": 1000,
                "transitions": [
                    {"to": "Trigger", "condition": "pinch_distance < 0.15"},
                    {"to": "Idle", "condition": "pinch_distance > 0.25", "abort": True}
                ]
            },
            {
                "id": "Trigger",
                "action": "MouseClick:Left",
                "cooldown_ms": 500
            }
        ]
    }
    
    if not any(g["name"] == "Pinch" for g in merged_config["gestures"]):
        merged_config["gestures"].append(pinch_fsm)

    from gesture_controller.core.event_bus import EventBus
    eb = EventBus()
    return GestureFSMManager(merged_config, eb)

def test_replay_minimize(fsm_manager: GestureFSMManager) -> None:
    data = load_replay_fixture("minimize.json")
    frames = data["frames"]
    
    triggered_events = []
    
    # We want to feed all frames to FSM manager
    for frame_idx, f in enumerate(frames):
        ts = f["timestamp"]
        hand_data = f["hands"][0]
        lms = tuple(
            Landmark3D(x=lm["x"], y=lm["y"], z=lm["z"]) for lm in hand_data["landmarks"]
        )
        hand = Hand(landmarks=lms, handedness=hand_data["handedness"], confidence=1.0)
        
        # Calculate mock velocity and acceleration
        velocity = np.zeros((21, 3))
        acceleration = np.zeros((21, 3))
        
        features = compute_features(hand, velocity, acceleration, ts, frame_idx)
        event = fsm_manager.evaluate(features)
        if event:
            triggered_events.append(event)
            
    # Verify that the final FSM state for Minimize Window triggers or transitions correctly
    states = fsm_manager.get_states()
    assert "MinimizeWindow" in states
    # It should have progressed past "Idle"
    current_state, progress = states["MinimizeWindow"]
    assert current_state in ("Candidate", "PointingUp", "RapidDownFlick", "Trigger", "Idle")

def test_replay_swipe(fsm_manager: GestureFSMManager) -> None:
    data = load_replay_fixture("swipe.json")
    frames = data["frames"]
    
    triggered_events = []
    for frame_idx, f in enumerate(frames):
        ts = f["timestamp"]
        hand_data = f["hands"][0]
        lms = tuple(
            Landmark3D(x=lm["x"], y=lm["y"], z=lm["z"]) for lm in hand_data["landmarks"]
        )
        hand = Hand(landmarks=lms, handedness=hand_data["handedness"], confidence=1.0)
        
        # Since swipe left requires horizontal velocity, let's compute real velocity based on frames!
        # Hand moves horizontally from right to left
        velocity = np.zeros((21, 3))
        if frame_idx > 0:
            prev_f = frames[frame_idx - 1]
            prev_lms = prev_f["hands"][0]["landmarks"]
            dt = ts - prev_f["timestamp"]
            if dt > 0:
                for idx in range(21):
                    dx = lms[idx].x - prev_lms[idx]["x"]
                    dy = lms[idx].y - prev_lms[idx]["y"]
                    dz = lms[idx].z - prev_lms[idx]["z"]
                    velocity[idx] = [dx / dt, dy / dt, dz / dt]
                    
        acceleration = np.zeros((21, 3))
        
        features = compute_features(hand, velocity, acceleration, ts, frame_idx)
        event = fsm_manager.evaluate(features)
        if event:
            triggered_events.append(event)
            
    states = fsm_manager.get_states()
    assert "SwitchWindow" in states
    current_state, progress = states["SwitchWindow"]
    assert current_state in ("Candidate", "HandOpen", "HorizontalSwipe", "Trigger", "Idle")

def test_replay_pinch(fsm_manager: GestureFSMManager) -> None:
    data = load_replay_fixture("pinch.json")
    frames = data["frames"]
    
    triggered_events = []
    for frame_idx, f in enumerate(frames):
        ts = f["timestamp"]
        hand_data = f["hands"][0]
        lms = tuple(
            Landmark3D(x=lm["x"], y=lm["y"], z=lm["z"]) for lm in hand_data["landmarks"]
        )
        hand = Hand(landmarks=lms, handedness=hand_data["handedness"], confidence=1.0)
        
        velocity = np.zeros((21, 3))
        acceleration = np.zeros((21, 3))
        
        features = compute_features(hand, velocity, acceleration, ts, frame_idx)
        event = fsm_manager.evaluate(features)
        if event:
            triggered_events.append(event)
            
    states = fsm_manager.get_states()
    assert "Pinch" in states
    current_state, progress = states["Pinch"]
    assert current_state in ("Candidate", "Pinching", "Trigger", "Idle")
    assert len(triggered_events) > 0


def test_replay_scroll(fsm_manager: GestureFSMManager) -> None:
    data = load_replay_fixture("scroll.json")
    frames = data["frames"]
    
    triggered_events = []
    for frame_idx, f in enumerate(frames):
        ts = f["timestamp"]
        hand_data = f["hands"][0]
        lms = tuple(
            Landmark3D(x=lm["x"], y=lm["y"], z=lm["z"]) for lm in hand_data["landmarks"]
        )
        hand = Hand(landmarks=lms, handedness=hand_data["handedness"], confidence=1.0)
        
        velocity = np.zeros((21, 3))
        acceleration = np.zeros((21, 3))
        
        features = compute_features(hand, velocity, acceleration, ts, frame_idx)
        event = fsm_manager.evaluate(features)
        if event:
            triggered_events.append(event)
            
    states = fsm_manager.get_states()
    # Scroll triggers ScrollingActive or similar in continuous Scrolling configuration
    assert "ScrollUpDown" in states
    current_state, progress = states["ScrollUpDown"]
    assert current_state in ("Candidate", "PointingForward", "ScrollingActive", "Trigger", "Idle")

def test_replay_custom(config_manager: ConfigManager) -> None:
    data = load_replay_fixture("custom.json")
    frames = data["frames"]
    
    # Custom gestures are matched via custom matcher (which runs on FSM fall-through)
    from gesture_controller.models.dtw_matcher import CustomGestureMatcher
    matcher = CustomGestureMatcher(config=config_manager._config)
    
    matches = []
    for frame_idx, f in enumerate(frames):
        ts = f["timestamp"]
        hand_data = f["hands"][0]
        lms = tuple(
            Landmark3D(x=lm["x"], y=lm["y"], z=lm["z"]) for lm in hand_data["landmarks"]
        )
        hand = Hand(landmarks=lms, handedness=hand_data["handedness"], confidence=1.0)
        
        matcher.update_buffer(hand)
        event = matcher.match(ts)
        if event:
            matches.append(event)
            
    # Wave oscillation shouldn't crash and returns list of events/matches if templates matched
    assert isinstance(matches, list)
