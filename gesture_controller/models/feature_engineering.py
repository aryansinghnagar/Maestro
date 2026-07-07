import numpy as np
from typing import Any

from gesture_controller.models.data_types import Hand, Landmark3D, FeatureVector

FINGER_LANDMARKS = {
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}

FINGER_MCP = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}


def compute_features(
    hand: Hand, velocity: np.ndarray, acceleration: np.ndarray, timestamp: float, frame_number: int
) -> FeatureVector:
    """Compute full FeatureVector from a Hand and its motion data.

    Args:
        hand: Hand dataclass with 21 Landmark3D
        velocity: (21, 3) velocity array from One-Euro filter
        acceleration: (21, 3) acceleration array from One-Euro filter
        timestamp: current time
        frame_number: frame counter

    Returns:
        FeatureVector with all fields populated
    """
    lms = hand.landmarks  # tuple of Landmark3D
    arr = np.array([[l.x, l.y, l.z] for l in lms], dtype=np.float64)  # (21, 3)

    # 1. Translate to hand-centric coordinates (wrist as origin)
    wrist = arr[0]

    # 2. Scale coordinate system by index MCP to PIP length (finger scale)
    mcp5 = arr[5]
    pip6 = arr[6]
    scale = float(np.linalg.norm(mcp5 - pip6))
    if scale < 1e-6:
        scale = 0.05

    # Mirror x-coordinates for Left-hand modes so gestures are hand-agnostic
    mirror = -1.0 if hand.handedness == "Left" else 1.0
    centered = (arr - wrist) / scale
    centered[:, 0] *= mirror  # Mirror x for left hand

    # 3. Finger extension calculations
    finger_extended = {}
    for name, joints in FINGER_LANDMARKS.items():
        tip_wrist_dist = np.linalg.norm(centered[joints[3]] - centered[0])
        mcp_wrist_dist = np.linalg.norm(centered[joints[0]] - centered[0])
        # A finger is extended if tip is significantly further from wrist than MCP
        finger_extended[name] = bool(tip_wrist_dist > mcp_wrist_dist * 1.15)

    # Override for thumb: thumb extension is lateral spread (distance from MCP 5 to thumb tip)
    thumb_spread = np.linalg.norm(centered[4] - centered[5])
    mcp_spread = np.linalg.norm(centered[2] - centered[5])
    finger_extended["thumb"] = bool(thumb_spread > mcp_spread * 1.1)

    # 4. Finger curl (0 = fully extended, 1 = fully curled)
    finger_curl = {}
    for name in FINGER_LANDMARKS:
        joints = FINGER_LANDMARKS[name]
        tip_mcp_dist = np.linalg.norm(centered[joints[3]] - centered[joints[0]])
        # Calculate full length of finger bone segments
        full_reach = sum(
            np.linalg.norm(centered[joints[i]] - centered[joints[i - 1]])
            for i in range(1, len(joints))
        )
        if full_reach < 1e-6:
            finger_curl[name] = 0.0
        else:
            finger_curl[name] = float(np.clip(1.0 - (tip_mcp_dist / full_reach), 0.0, 1.0))

    # 5. Hand openness (average extension ratio of non-thumb fingers)
    openness_values = [1.0 - finger_curl[f] for f in ["index", "middle", "ring", "pinky"]]
    hand_openness = float(np.mean(openness_values))

    # 6. Pinch distance (distance between thumb tip and index tip)
    thumb_tip = centered[4]
    index_tip = centered[8]
    pinch_dist = float(np.linalg.norm(thumb_tip - index_tip))

    # 7. Palm normal (vector perpendicular to palm plane)
    v1 = centered[5] - centered[0]  # Wrist -> Index MCP
    v2 = centered[17] - centered[0]  # Wrist -> Pinky MCP
    palm_norm = np.cross(v1, v2)
    norm_mag = np.linalg.norm(palm_norm)
    if norm_mag < 1e-8:
        palm_normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    else:
        palm_normal = palm_norm / norm_mag

    # 8. Palm center (mean of wrist, index MCP, and pinky MCP)
    palm_center = (centered[0] + centered[5] + centered[17]) / 3.0

    # 9. Transform velocity and acceleration to normalized hand scale
    # Hand-mirrored wrist velocity
    palm_vel = velocity[0].copy() / scale
    palm_vel[0] *= mirror

    palm_accel = acceleration[0].copy() / scale
    palm_accel[0] *= mirror

    index_tip_vel = velocity[8].copy() / scale
    index_tip_vel[0] *= mirror

    return FeatureVector(
        thumb_extended=finger_extended["thumb"],
        index_extended=finger_extended["index"],
        middle_extended=finger_extended["middle"],
        ring_extended=finger_extended["ring"],
        pinky_extended=finger_extended["pinky"],
        thumb_curl=finger_curl["thumb"],
        index_curl=finger_curl["index"],
        middle_curl=finger_curl["middle"],
        ring_curl=finger_curl["ring"],
        pinky_curl=finger_curl["pinky"],
        hand_openness=hand_openness,
        pinch_distance=pinch_dist,
        palm_normal=palm_normal,
        palm_center=palm_center,
        index_tip=index_tip,
        palm_velocity=palm_vel,
        palm_acceleration=palm_accel,
        index_tip_velocity=index_tip_vel,
        palm_velocity_magnitude=float(np.linalg.norm(palm_vel)),
        handedness="Right",  # Mirroring maps Left hand poses onto Right coordinate space
        confidence=hand.confidence,
        timestamp=timestamp,
        frame_number=frame_number,
    )
