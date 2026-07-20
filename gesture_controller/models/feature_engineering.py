import numpy as np

from gesture_controller.models.data_types import Hand, Landmark3D, FeatureVector
from gesture_controller.models.hand_topology import FINGER_LANDMARKS


def compute_features(
    hand: Hand,
    velocity: np.ndarray,
    acceleration: np.ndarray,
    timestamp: float,
    frame_number: int,
    arr_buf: np.ndarray | None = None,
    centered_buf: np.ndarray | None = None,
) -> FeatureVector:
    """Compute full FeatureVector from a Hand and its motion data.

    Args:
        hand: Hand dataclass with 21 Landmark3D
        velocity: (21, 3) velocity array from One-Euro filter
        acceleration: (21, 3) acceleration array from One-Euro filter
        timestamp: current time
        frame_number: frame counter
        arr_buf: pre-allocated (21, 3) buffer for raw coordinates
        centered_buf: pre-allocated (21, 3) buffer for normalized coordinates

    Returns:
        FeatureVector with all fields populated
    """
    lms = hand.landmarks  # tuple of Landmark3D

    if arr_buf is None:
        arr = np.empty((21, 3), dtype=np.float64)
    else:
        arr = arr_buf

    for i, l in enumerate(lms):
        arr[i, 0] = l.x
        arr[i, 1] = l.y
        arr[i, 2] = l.z

    # 1. Normalize landmarks (Translate, scale and mirror left hand)
    if centered_buf is None:
        centered = np.empty((21, 3), dtype=np.float64)
    else:
        centered = centered_buf

    from gesture_controller.models.hand_normalization import normalize_landmarks_inplace

    normalize_landmarks_inplace(arr, centered, hand.handedness)

    # Preserve scale and mirror for velocity/acceleration calculations below
    # We do a fast norm between landmark 5 and 6
    dx = arr[5, 0] - arr[6, 0]
    dy = arr[5, 1] - arr[6, 1]
    dz = arr[5, 2] - arr[6, 2]
    scale = float(np.sqrt(dx * dx + dy * dy + dz * dz))
    if scale < 1e-6:
        scale = 0.05
    mirror = -1.0 if hand.handedness == "Left" else 1.0

    # 3. Finger extension calculations
    finger_extended = {}
    for name, joints in FINGER_LANDMARKS.items():
        # Fast norm for tip_wrist_dist and mcp_wrist_dist
        j3 = joints[3]
        j0 = joints[0]

        twd_x = centered[j3, 0] - centered[0, 0]
        twd_y = centered[j3, 1] - centered[0, 1]
        twd_z = centered[j3, 2] - centered[0, 2]
        tip_wrist_dist = float(np.sqrt(twd_x * twd_x + twd_y * twd_y + twd_z * twd_z))

        mwd_x = centered[j0, 0] - centered[0, 0]
        mwd_y = centered[j0, 1] - centered[0, 1]
        mwd_z = centered[j0, 2] - centered[0, 2]
        mcp_wrist_dist = float(np.sqrt(mwd_x * mwd_x + mwd_y * mwd_y + mwd_z * mwd_z))

        # A finger is extended if tip is significantly further from wrist than MCP
        finger_extended[name] = bool(tip_wrist_dist > mcp_wrist_dist * 1.15)

    # Override for thumb: thumb extension is lateral spread (distance from MCP 5 to thumb tip)
    ts_x = centered[4, 0] - centered[5, 0]
    ts_y = centered[4, 1] - centered[5, 1]
    ts_z = centered[4, 2] - centered[5, 2]
    thumb_spread = float(np.sqrt(ts_x * ts_x + ts_y * ts_y + ts_z * ts_z))

    ms_x = centered[2, 0] - centered[5, 0]
    ms_y = centered[2, 1] - centered[5, 1]
    ms_z = centered[2, 2] - centered[5, 2]
    mcp_spread = float(np.sqrt(ms_x * ms_x + ms_y * ms_y + ms_z * ms_z))

    finger_extended["thumb"] = bool(thumb_spread > mcp_spread * 1.1)

    # 4. Finger curl (0 = fully extended, 1 = fully curled)
    finger_curl = {}
    for name in FINGER_LANDMARKS:
        joints = FINGER_LANDMARKS[name]

        # Distance between tip (joint 3) and MCP (joint 0)
        j3 = joints[3]
        j0 = joints[0]
        tmd_x = centered[j3, 0] - centered[j0, 0]
        tmd_y = centered[j3, 1] - centered[j0, 1]
        tmd_z = centered[j3, 2] - centered[j0, 2]
        tip_mcp_dist = float(np.sqrt(tmd_x * tmd_x + tmd_y * tmd_y + tmd_z * tmd_z))

        # Calculate full length of finger bone segments
        full_reach = 0.0
        for i in range(1, len(joints)):
            ji = joints[i]
            ji_prev = joints[i - 1]
            seg_x = centered[ji, 0] - centered[ji_prev, 0]
            seg_y = centered[ji, 1] - centered[ji_prev, 1]
            seg_z = centered[ji, 2] - centered[ji_prev, 2]
            full_reach += float(np.sqrt(seg_x * seg_x + seg_y * seg_y + seg_z * seg_z))

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
    pt_x = thumb_tip[0] - index_tip[0]
    pt_y = thumb_tip[1] - index_tip[1]
    pt_z = thumb_tip[2] - index_tip[2]
    pinch_dist = float(np.sqrt(pt_x * pt_x + pt_y * pt_y + pt_z * pt_z))

    # 7. Palm normal (vector perpendicular to palm plane)
    v1_x = centered[5, 0] - centered[0, 0]
    v1_y = centered[5, 1] - centered[0, 1]
    v1_z = centered[5, 2] - centered[0, 2]

    v2_x = centered[17, 0] - centered[0, 0]
    v2_y = centered[17, 1] - centered[0, 1]
    v2_z = centered[17, 2] - centered[0, 2]

    # Cross product
    palm_norm_x = v1_y * v2_z - v1_z * v2_y
    palm_norm_y = v1_z * v2_x - v1_x * v2_z
    palm_norm_z = v1_x * v2_y - v1_y * v2_x

    norm_mag = float(
        np.sqrt(palm_norm_x * palm_norm_x + palm_norm_y * palm_norm_y + palm_norm_z * palm_norm_z)
    )
    if norm_mag < 1e-8:
        palm_normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    else:
        palm_normal = np.array(
            [palm_norm_x / norm_mag, palm_norm_y / norm_mag, palm_norm_z / norm_mag],
            dtype=np.float64,
        )

    # 8. Palm center (mean of wrist, index MCP, and pinky MCP)
    palm_center = np.array(
        [
            (centered[0, 0] + centered[5, 0] + centered[17, 0]) / 3.0,
            (centered[0, 1] + centered[5, 1] + centered[17, 1]) / 3.0,
            (centered[0, 2] + centered[5, 2] + centered[17, 2]) / 3.0,
        ],
        dtype=np.float64,
    )

    # 9. Transform velocity and acceleration to normalized hand scale
    # Hand-mirrored wrist velocity
    palm_vel = np.array(
        [
            velocity[0, 0] / scale * mirror,
            velocity[0, 1] / scale,
            velocity[0, 2] / scale,
        ],
        dtype=np.float64,
    )

    palm_accel = np.array(
        [
            acceleration[0, 0] / scale * mirror,
            acceleration[0, 1] / scale,
            acceleration[0, 2] / scale,
        ],
        dtype=np.float64,
    )

    index_tip_vel = np.array(
        [
            velocity[8, 0] / scale * mirror,
            velocity[8, 1] / scale,
            velocity[8, 2] / scale,
        ],
        dtype=np.float64,
    )

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
