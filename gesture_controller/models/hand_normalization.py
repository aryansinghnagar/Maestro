"""Hand landmark normalization utilities — single source of truth.

Replaces 2 copies across:
  models/feature_engineering.py, models/dtw_matcher.py
"""
from __future__ import annotations

import numpy as np


def normalize_landmarks(
    landmarks: np.ndarray,
    handedness: str = "Right",
) -> np.ndarray:
    """Normalize hand landmarks to wrist-centered, scale-invariant, mirrored space.

    1. Center on wrist (landmark 0)
    2. Scale by index MCP→PIP distance (landmarks 5→6)
    3. Mirror x-axis for Left hand (map to Right coordinate space)

    Args:
        landmarks: (21, 3) array of raw landmark coordinates
        handedness: "Left" or "Right"

    Returns:
        (21, 3) normalized landmark array
    """
    if landmarks.shape != (21, 3):
        raise ValueError(f"Expected shape (21, 3), got {landmarks.shape}")

    wrist = landmarks[0]
    centered = landmarks - wrist

    mcp5 = centered[5]
    pip6 = centered[6]
    scale = float(np.linalg.norm(mcp5 - pip6))
    if scale < 1e-6:
        scale = 0.05

    normalized = centered / scale

    if handedness == "Left":
        normalized[:, 0] *= -1.0

    return normalized


def normalize_landmarks_inplace(
    landmarks: np.ndarray,
    out: np.ndarray,
    handedness: str = "Right",
) -> np.ndarray:
    """Normalize hand landmarks to wrist-centered, scale-invariant, mirrored space in-place."""
    if landmarks.shape != (21, 3):
        raise ValueError(f"Expected shape (21, 3), got {landmarks.shape}")
    if out.shape != (21, 3):
        raise ValueError(f"Expected shape (21, 3) for out, got {out.shape}")

    # 1. Center on wrist (landmark 0)
    wrist = landmarks[0]
    np.subtract(landmarks, wrist, out=out)

    # 2. Scale by index MCP->PIP distance (landmarks 5->6)
    mcp5 = out[5]
    pip6 = out[6]
    scale = float(np.linalg.norm(mcp5 - pip6))
    if scale < 1e-6:
        scale = 0.05

    out /= scale

    # 3. Mirror x-axis for Left hand
    if handedness == "Left":
        out[:, 0] *= -1.0

    return out


def landmarks_to_flat_vector(
    landmarks: np.ndarray,
    handedness: str = "Right",
) -> np.ndarray:
    """Normalize landmarks and flatten to (63,) vector for DTW."""
    normalized = normalize_landmarks(landmarks, handedness)
    return normalized.flatten()


def palm_center(landmarks: np.ndarray) -> np.ndarray:
    """Compute palm center as mean of wrist, index MCP, pinky MCP."""
    return (landmarks[0] + landmarks[5] + landmarks[17]) / 3.0


def palm_normal_vector(landmarks: np.ndarray) -> np.ndarray:
    """Compute palm normal vector via cross product."""
    wrist = landmarks[0]
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]

    v1 = index_mcp - wrist
    v2 = pinky_mcp - wrist
    normal = np.cross(v1, v2)

    magnitude = float(np.linalg.norm(normal))
    if magnitude < 1e-8:
        return np.array([0.0, 0.0, 1.0])

    return normal / magnitude
