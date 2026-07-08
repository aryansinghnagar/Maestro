import json
from pathlib import Path


def get_open_palm_coords():
    return [
        (0.5, 0.8, 0.0),  # 0: WRIST
        (0.45, 0.65, 0.0),  # 1: THUMB_CMC
        (0.4, 0.5, 0.0),  # 2: THUMB_MCP
        (0.37, 0.4, 0.0),  # 3: THUMB_IP
        (0.35, 0.3, 0.0),  # 4: THUMB_TIP
        (0.42, 0.55, 0.0),  # 5: INDEX_MCP
        (0.4, 0.4, 0.0),  # 6: INDEX_PIP
        (0.39, 0.3, 0.0),  # 7: INDEX_DIP
        (0.38, 0.22, 0.0),  # 8: INDEX_TIP
        (0.5, 0.53, 0.0),  # 9: MIDDLE_MCP
        (0.5, 0.38, 0.0),  # 10: MIDDLE_PIP
        (0.5, 0.28, 0.0),  # 11: MIDDLE_DIP
        (0.5, 0.2, 0.0),  # 12: MIDDLE_TIP
        (0.57, 0.55, 0.0),  # 13: RING_MCP
        (0.58, 0.42, 0.0),  # 14: RING_PIP
        (0.58, 0.33, 0.0),  # 15: RING_DIP
        (0.58, 0.26, 0.0),  # 16: RING_TIP
        (0.63, 0.58, 0.0),  # 17: PINKY_MCP
        (0.64, 0.47, 0.0),  # 18: PINKY_PIP
        (0.64, 0.39, 0.0),  # 19: PINKY_DIP
        (0.65, 0.33, 0.0),  # 20: PINKY_TIP
    ]


def generate_fixtures():
    fixtures_dir = Path("gesture_controller/tests/replay/fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Minimize Gesture (Open palm curling to Fist)
    minimize_frames = []
    open_coords = get_open_palm_coords()
    fist_coords = [
        (0.5, 0.8, 0.0),
        (0.45, 0.68, -0.03),
        (0.47, 0.72, -0.02),
        (0.48, 0.74, -0.02),
        (0.47, 0.72, -0.02),
        (0.46, 0.68, 0.0),
        (0.47, 0.72, 0.0),
        (0.47, 0.74, 0.0),
        (0.46, 0.72, 0.0),
        (0.50, 0.68, 0.0),
        (0.50, 0.72, 0.0),
        (0.50, 0.74, 0.0),
        (0.50, 0.72, 0.0),
        (0.53, 0.68, 0.0),
        (0.54, 0.72, 0.0),
        (0.54, 0.74, 0.0),
        (0.53, 0.72, 0.0),
        (0.56, 0.69, 0.0),
        (0.57, 0.72, 0.0),
        (0.57, 0.74, 0.0),
        (0.56, 0.72, 0.0),
    ]
    for i in range(20):
        t = i / 19.0
        frame_lms = []
        for start, end in zip(open_coords, fist_coords):
            # Interpolate coordinates
            x = start[0] + t * (end[0] - start[0])
            y = start[1] + t * (end[1] - start[1])
            z = start[2] + t * (end[2] - start[2])
            frame_lms.append({"x": x, "y": y, "z": z})
        minimize_frames.append(
            {
                "timestamp": 1718000000.0 + i * 0.033,
                "hands": [{"handedness": "Right", "landmarks": frame_lms}],
            }
        )
    with open(fixtures_dir / "minimize.json", "w") as f:
        json.dump({"gesture_name": "Minimize", "frames": minimize_frames}, f, indent=2)

    # 2. Swipe Gesture (Pointing hand moving right-to-left horizontally)
    swipe_frames = []
    pointing_coords = [
        (0.5, 0.8, 0.0),  # 0: WRIST
        (0.45, 0.65, -0.02),
        (0.47, 0.7, -0.01),
        (0.48, 0.73, -0.01),
        (0.47, 0.7, -0.01),
        (0.44, 0.6, 0.0),
        (0.43, 0.45, 0.0),
        (0.42, 0.33, 0.0),
        (0.41, 0.22, 0.0),  # Index extended
        (0.5, 0.62, 0.0),
        (0.51, 0.68, 0.0),
        (0.51, 0.72, 0.0),
        (0.50, 0.7, 0.0),
        (0.55, 0.63, 0.0),
        (0.56, 0.68, 0.0),
        (0.56, 0.72, 0.0),
        (0.55, 0.7, 0.0),
        (0.59, 0.64, 0.0),
        (0.60, 0.68, 0.0),
        (0.60, 0.71, 0.0),
        (0.59, 0.69, 0.0),
    ]
    for i in range(20):
        # Shift all coordinates horizontally by delta_x
        delta_x = 0.2 - (i / 19.0) * 0.4  # moves leftwards
        frame_lms = [{"x": x + delta_x, "y": y, "z": z} for x, y, z in pointing_coords]
        swipe_frames.append(
            {
                "timestamp": 1718000000.0 + i * 0.033,
                "hands": [{"handedness": "Right", "landmarks": frame_lms}],
            }
        )
    with open(fixtures_dir / "swipe.json", "w") as f:
        json.dump({"gesture_name": "SwipeLeft", "frames": swipe_frames}, f, indent=2)

    # 3. Pinch Gesture (Open tips contracting close together)
    pinch_frames = []
    # Base coords where index and thumb tips are far
    base_coords = get_open_palm_coords()
    for i in range(20):
        t = i / 19.0
        frame_lms = [dict(zip(["x", "y", "z"], c)) for c in base_coords]
        # Gradually move index tip and thumb tip close together
        # Thumb tip index: 4, Index tip index: 8
        # Start: thumb (0.35, 0.3), index (0.38, 0.22)
        # End: thumb (0.375, 0.26), index (0.375, 0.26)
        frame_lms[4]["x"] = 0.35 + t * (0.375 - 0.35)
        frame_lms[4]["y"] = 0.30 + t * (0.26 - 0.30)
        frame_lms[8]["x"] = 0.38 + t * (0.375 - 0.38)
        frame_lms[8]["y"] = 0.22 + t * (0.26 - 0.22)
        pinch_frames.append(
            {
                "timestamp": 1718000000.0 + i * 0.033,
                "hands": [{"handedness": "Right", "landmarks": frame_lms}],
            }
        )
    with open(fixtures_dir / "pinch.json", "w") as f:
        json.dump({"gesture_name": "Pinch", "frames": pinch_frames}, f, indent=2)

    # 4. Scroll Gesture (Pointing hand moving vertically downwards)
    scroll_frames = []
    for i in range(20):
        # Shift all coordinates vertically by delta_y
        delta_y = -0.15 + (i / 19.0) * 0.3  # moves down
        frame_lms = [{"x": x, "y": y + delta_y, "z": z} for x, y, z in pointing_coords]
        scroll_frames.append(
            {
                "timestamp": 1718000000.0 + i * 0.033,
                "hands": [{"handedness": "Right", "landmarks": frame_lms}],
            }
        )
    with open(fixtures_dir / "scroll.json", "w") as f:
        json.dump({"gesture_name": "Scroll", "frames": scroll_frames}, f, indent=2)

    # 5. Custom Wave Gesture (Sequence of palm centers shifting back and forth)
    custom_frames = []
    for i in range(20):
        import math

        # Simulate small waving oscillation
        delta_x = 0.1 * math.sin(i * 0.5)
        frame_lms = [{"x": x + delta_x, "y": y, "z": z} for x, y, z in open_coords]
        custom_frames.append(
            {
                "timestamp": 1718000000.0 + i * 0.033,
                "hands": [{"handedness": "Right", "landmarks": frame_lms}],
            }
        )
    with open(fixtures_dir / "custom.json", "w") as f:
        json.dump({"gesture_name": "CustomWave", "frames": custom_frames}, f, indent=2)

    print("All replay fixtures generated successfully!")


if __name__ == "__main__":
    generate_fixtures()
