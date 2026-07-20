"""Hand skeleton bone connections — single source of truth.

Replaces 2 copies across:
  gui/overlay.py, gui/gesture_recorder.py

Based on MediaPipe Hand Landmark model:
  https://developers.google.com/mediapipe/solutions/vision/hand_landmarker
"""

from __future__ import annotations

# 21 landmarks: 0=WRIST, 1-4=THUMB, 5-8=INDEX, 9-12=MIDDLE,
#               13-16=RING, 17-20=PINKY

# Bone connections as (start, end) index pairs
CONNECTIONS: list[tuple[int, int]] = [
    # Thumb
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    # Index finger
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    # Middle finger
    (9, 10),
    (10, 11),
    (11, 12),
    # Ring finger
    (13, 14),
    (14, 15),
    (15, 16),
    # Pinky
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    # Palm connections
    (5, 9),
    (9, 13),
    (13, 17),
]

# Finger groupings (landmark indices per finger)
FINGER_LANDMARKS: dict[str, list[int]] = {
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}

# MCP (metacarpophalangeal) joint indices
FINGER_MCP: dict[str, int] = {
    "thumb": 2,
    "index": 5,
    "middle": 9,
    "ring": 13,
    "pinky": 17,
}

# Fingertip indices
FINGERTIPS: dict[str, int] = {
    "thumb": 4,
    "index": 8,
    "middle": 12,
    "ring": 16,
    "pinky": 20,
}

# Key landmark indices
WRIST: int = 0
INDEX_MCP: int = 5
PINKY_MCP: int = 17
INDEX_TIP: int = 8
THUMB_TIP: int = 4
