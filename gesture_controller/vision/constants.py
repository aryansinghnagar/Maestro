"""Shared vision constants — single source of truth.

Replaces 4 copies across:
  camera_stream, double_buffer, landmark_extractor, onnx_backend
"""

from __future__ import annotations

# Frame dimensions (must match camera capture and SHM buffer)
FRAME_WIDTH: int = 640
FRAME_HEIGHT: int = 480
FRAME_CHANNELS: int = 3
FRAME_SIZE: int = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS  # 921,600 bytes
FRAME_DTYPE: str = "uint8"

# SharedMemory double-buffer layout
HEADER_SIZE: int = 64  # Cache-line aligned header
TOTAL_SHM_SIZE: int = HEADER_SIZE + FRAME_SIZE * 2  # 1,843,264 bytes

# MediaPipe model paths
MODEL_DIR: str = "data"
HAND_LANDMARKER_TASK: str = "hand_landmarker.task"
HAND_LANDMARKER_ONNX: str = "hand_landmark.onnx"
HAND_LANDMARKER_INT8_ONNX: str = "hand_landmark_int8.onnx"
PALM_DETECTION_ONNX: str = "palm_detection.onnx"

# Expected SHA256 hashes (update when models change)
HAND_LANDMARKER_SHA256: str = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"

# Hand topology
NUM_LANDMARKS: int = 21
LANDMARK_DIMS: int = 3
LANDMARK_ARRAY_SHAPE: tuple[int, int] = (NUM_LANDMARKS, LANDMARK_DIMS)
LANDMARK_ARRAY_DTYPE: str = "float64"

# Inference defaults
DEFAULT_MAX_HANDS: int = 2
DEFAULT_MIN_DETECTION_CONFIDENCE: float = 0.7
DEFAULT_MIN_TRACKING_CONFIDENCE: float = 0.5
DEFAULT_MAX_TRACK_DISTANCE: float = 0.25

# DTW defaults
DTW_BUFFER_FRAMES: int = 60
DTW_FEATURE_DIMS: int = 63  # 21 landmarks × 3 coords
DTW_DEFAULT_THRESHOLD: float = 0.15
DTW_DEFAULT_COOLDOWN_MS: int = 1000
DTW_DEFAULT_REFRACTORY_MS: int = 2000
