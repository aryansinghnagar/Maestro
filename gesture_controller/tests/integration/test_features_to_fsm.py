import numpy as np
import pytest
from unittest.mock import MagicMock
from pathlib import Path
import yaml

from gesture_controller.core.state_machine import GestureFSMManager
from gesture_controller.models.data_types import FeatureVector, GestureEvent
from gesture_controller.core.event_bus import EventBus

@pytest.fixture
def test_config() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "predefined_gestures.yaml"
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    
    # Merge default thresholds and config keys
    config = {
        "engine": {
            "global_cooldown_ms": 200.0
        },
        "config": {
            "default_thresholds": data.get("config", {}).get("default_thresholds", {})
        },
        "gestures": data.get("gestures", [])
    }
    return config

def test_minimize_gesture_integration_flow(test_config: dict) -> None:
    event_bus = EventBus()
    
    # Track emitted gestures
    triggered_events = []
    event_bus.subscribe("gesture_triggered", lambda e: triggered_events.append(e))
    
    manager = GestureFSMManager(test_config, event_bus)
    
    # Define a helper to construct a generic FeatureVector
    def make_fv(
        timestamp: float,
        index_extended: bool = False,
        index_tip_velocity_y: float = 0.0,
        index_tip_y: float = 0.5,
        palm_velocity_magnitude: float = 0.0
    ) -> FeatureVector:
        return FeatureVector(
            thumb_extended=False,
            index_extended=index_extended,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
            thumb_curl=0.0,
            index_curl=0.0,
            middle_curl=0.9,
            ring_curl=0.9,
            pinky_curl=0.9,
            hand_openness=0.2,
            pinch_distance=0.5,
            palm_normal=np.array([0.0, 0.0, 1.0]),
            palm_center=np.array([0.5, 0.5, 0.5]),
            index_tip=np.array([0.5, index_tip_y, 0.2]),
            palm_velocity=np.zeros(3),
            palm_velocity_magnitude=palm_velocity_magnitude,
            palm_acceleration=np.zeros(3),
            index_tip_velocity=np.array([0.0, index_tip_velocity_y, 0.0]),
            handedness="Right",
            confidence=1.0,
            timestamp=timestamp,
            frame_number=0
        )

    # Sequence of frames to simulate a MinimizeWindow gesture:
    # 1. Start in Idle, index finger becomes extended (Transition Idle -> PointingUp)
    manager.evaluate(make_fv(timestamp=0.0, index_extended=True))
    
    # 2. Stay pointing up for 250ms (satisfies PointingUp min_duration of 200ms)
    manager.evaluate(make_fv(timestamp=0.1, index_extended=True))
    manager.evaluate(make_fv(timestamp=0.25, index_extended=True))
    
    # 3. Simulate down flick: index_tip_velocity_y > 0.5 (Transition PointingUp -> RapidDownFlick)
    manager.evaluate(make_fv(timestamp=0.26, index_extended=True, index_tip_velocity_y=0.7))
    
    # 4. In RapidDownFlick state: feed movement where index_tip moves down by 0.2 (which is > 0.15 index_tip_delta_y)
    # The state entry y-coordinate at timestamp 0.26 was 0.5, now we move index_tip_y to 0.75
    # Transition RapidDownFlick -> Trigger -> emit GestureEvent -> Reset to Idle
    event = manager.evaluate(make_fv(timestamp=0.35, index_extended=True, index_tip_y=0.75))
    
    assert event is not None
    assert event.gesture_name == "MinimizeWindow"
    assert event.action == "OS:MinimizeActiveWindow"
