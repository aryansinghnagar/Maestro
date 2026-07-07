from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass(frozen=True, slots=True)
class Landmark3D:
    """Single landmark point. Coordinates normalized [0,1] for x,y; z relative depth."""

    x: float
    y: float
    z: float
    visibility: float = 1.0


@dataclass(frozen=True, slots=True)
class Hand:
    """One detected hand with 21 landmarks."""

    landmarks: tuple[Landmark3D, ...]  # Exactly 21
    handedness: str  # "Left" or "Right"
    confidence: float
    wrist: Landmark3D = field(init=False)
    palm_center: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        assert len(self.landmarks) == 21, f"Expected 21 landmarks, got {len(self.landmarks)}"
        object.__setattr__(self, "wrist", self.landmarks[0])
        pc = np.array(
            [
                (self.landmarks[0].x + self.landmarks[5].x + self.landmarks[17].x) / 3.0,
                (self.landmarks[0].y + self.landmarks[5].y + self.landmarks[17].y) / 3.0,
                (self.landmarks[0].z + self.landmarks[5].z + self.landmarks[17].z) / 3.0,
            ],
            dtype=np.float32,
        )
        object.__setattr__(self, "palm_center", pc)


@dataclass
class FeatureVector:
    """Computed features from one frame of one hand."""

    # Finger states
    thumb_extended: bool
    index_extended: bool
    middle_extended: bool
    ring_extended: bool
    pinky_extended: bool
    thumb_curl: float
    index_curl: float
    middle_curl: float
    ring_curl: float
    pinky_curl: float
    # Hand-level
    hand_openness: float
    pinch_distance: float
    palm_normal: np.ndarray
    palm_center: np.ndarray
    index_tip: np.ndarray
    # Motion
    palm_velocity: np.ndarray
    palm_velocity_magnitude: float
    palm_acceleration: np.ndarray
    index_tip_velocity: np.ndarray
    # Metadata
    handedness: str = "Right"
    confidence: float = 1.0
    timestamp: float = 0.0
    frame_number: int = 0
    # Accumulated deltas (for dynamic gestures)
    index_tip_delta_y: float = 0.0
    palm_center_delta_x: float = 0.0
    palm_center_delta_y: float = 0.0
    palm_delta_y: float = 0.0


@dataclass
class GestureEvent:
    """Emitted when a gesture is recognized."""

    gesture_name: str
    gesture_type: str  # "static", "dynamic", "continuous", "custom"
    action: str
    confidence: float
    hand: str
    timestamp: float
    app_profile: Optional[str] = None
    gesture_source: str = "fsm"
    metadata: dict[str, str | float | int | bool] = field(default_factory=dict)


class CameraEvent:
    DISCONNECTED = "camera_disconnected"
    RECOVERED = "camera_recovered"
    RECONNECTING = "camera_reconnecting"


class SystemEvent:
    CONFIG_CHANGED = "config_changed"
    PAUSE_TOGGLED = "pause_toggled"
    SHUTDOWN = "shutdown"
