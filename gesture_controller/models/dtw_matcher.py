import os
import sys
import time
import json
import platform
import numba
import numpy as np
from pathlib import Path
from typing import Any, Sequence
import structlog

from gesture_controller.models.data_types import Hand, Landmark3D, GestureEvent

logger = structlog.get_logger(__name__)


@numba.jit(nopython=True)
def fast_dtw_distance(s1: np.ndarray, s2: np.ndarray) -> float:
    """Numba-compiled Dynamic Time Warping distance between two feature sequences.

    Args:
        s1: Array of shape (N, F)
        s2: Array of shape (M, F)

    Returns:
        DTW distance score (float)
    """
    n = len(s1)
    m = len(s2)

    # Cost matrix
    dtw_matrix = np.zeros((n + 1, m + 1), dtype=np.float64)

    # Initialize boundary conditions
    for i in range(1, n + 1):
        dtw_matrix[i, 0] = 1e9  # Use large number instead of inf for Numba compatibility
    for j in range(1, m + 1):
        dtw_matrix[0, j] = 1e9

    dtw_matrix[0, 0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            # Compute Euclidean distance
            diff = s1[i - 1] - s2[j - 1]
            dist = np.sqrt(np.sum(diff * diff))

            # Recurrence relation
            dtw_matrix[i, j] = dist + min(
                dtw_matrix[i - 1, j],  # insertion
                dtw_matrix[i, j - 1],  # deletion
                dtw_matrix[i - 1, j - 1],  # match
            )

    # Normalize by path length (N + M)
    return float(dtw_matrix[n, m] / (n + m))


@numba.jit(nopython=True)
def dtw_distance_batch(
    query: np.ndarray, templates: np.ndarray, thresholds: np.ndarray
) -> tuple[int, float]:
    """Compare one buffer against a batch of templates.

    Returns:
        Index of the best template matching the query, and its distance.
        If no template is under its threshold, returns (-1, 1e9).
    """
    best_idx = -1
    best_dist = 1e9

    for i in range(len(templates)):
        template = templates[i]
        threshold = thresholds[i]

        dist = fast_dtw_distance(query, template)
        if dist < threshold and dist < best_dist:
            best_dist = dist
            best_idx = i

    return best_idx, best_dist


def to_hand_frame(landmarks: Sequence[Landmark3D], handedness: str) -> list[Landmark3D]:
    """Normalize hand landmarks relative to the wrist origin and index finger scale."""
    arr = np.array([[l.x, l.y, l.z] for l in landmarks], dtype=np.float64)
    wrist = arr[0]
    mcp5 = arr[5]
    pip6 = arr[6]
    scale = float(np.linalg.norm(mcp5 - pip6))
    if scale < 1e-6:
        scale = 0.05
    mirror = -1.0 if handedness == "Left" else 1.0
    centered = (arr - wrist) / scale
    centered[:, 0] *= mirror
    return [Landmark3D(x=float(row[0]), y=float(row[1]), z=float(row[2])) for row in centered]


def normalize_sequence(sequence: list[np.ndarray], target_len: int = 60) -> np.ndarray:
    """Resample landmark sequences to a fixed target length using linear interpolation."""
    seq_arr = np.array(sequence)
    L = len(seq_arr)
    if L == target_len:
        return seq_arr
    x_old = np.linspace(0, 1, L)
    x_new = np.linspace(0, 1, target_len)
    resampled = np.zeros((target_len, seq_arr.shape[1]), dtype=np.float64)
    for col in range(seq_arr.shape[1]):
        resampled[:, col] = np.interp(x_new, x_old, seq_arr[:, col])
    return resampled


class DTWMatcher:
    """Handles loading gesture templates and matching rolling buffer sequences using DTW."""

    def __init__(self, templates: dict[str, np.ndarray] | None = None) -> None:
        """
        Args:
            templates: Dict mapping gesture names to template arrays of shape (T, F).
        """
        self.templates = templates or {}
        # Warm up the JIT compiler with dummy data to prevent first-frame lag
        self._warmup()

    def _warmup(self) -> None:
        """Trigger JIT compilation on initialization to avoid first-run stutters."""
        try:
            s1 = np.zeros((10, 3), dtype=np.float64)
            s2 = np.zeros((10, 3), dtype=np.float64)
            fast_dtw_distance(s1, s2)
        except Exception:
            pass

    def add_template(self, name: str, template: np.ndarray) -> None:
        """Add or update a gesture template."""
        self.templates[name] = template

    def match(self, sequence: np.ndarray, threshold: float = 0.15) -> tuple[str, float]:
        """Match sequence against all templates.

        Args:
            sequence: Input sequence of shape (T, F) to check.
            threshold: Match rejection distance cutoff.

        Returns:
            Tuple of (gesture_name, score). If no match passes threshold, returns ("", inf).
        """
        best_name = ""
        best_score = float("inf")

        for name, template in self.templates.items():
            try:
                seq_f64 = sequence.astype(np.float64)
                temp_f64 = template.astype(np.float64)
                score = fast_dtw_distance(seq_f64, temp_f64)

                if score < best_score:
                    best_score = score
                    best_name = name
            except Exception:
                continue

        if best_score <= threshold:
            return best_name, best_score
        return "", best_score


class CustomGestureMatcher:
    """Rolling window matcher for custom, user-defined gestures recorded by the GUI."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._templates: dict[str, dict[str, Any]] = {}
        self._buffer: np.ndarray = np.zeros((60, 63), dtype=np.float64)
        self._buffer_idx: int = 0
        self._buffer_full: bool = False
        self._frame_count: int = 0
        self._last_match_monotonic: float = 0.0
        self._last_matched_name: str | None = None
        cfg = config or {}
        self._cooldown_s: float = cfg.get("dtw", {}).get("cooldown_ms", 1000.0) / 1000.0
        self._refractory_s: float = cfg.get("dtw", {}).get("refractory_ms", 2000.0) / 1000.0
        self._precomputed_templates: np.ndarray | None = None
        self._precomputed_thresholds: np.ndarray | None = None
        self._precomputed_names: list[str] | None = None

        # Determine custom template directories
        sys_name = platform.system()
        if sys_name == "Windows":
            self._template_dir = (
                Path(os.environ.get("APPDATA", "")) / "gesture_controller" / "custom_templates"
            )
        elif sys_name == "Darwin":
            self._template_dir = (
                Path.home()
                / "Library"
                / "Application Support"
                / "gesture_controller"
                / "custom_templates"
            )
        else:
            self._template_dir = Path.home() / ".config" / "gesture_controller" / "custom_templates"

        self.load_templates(self._template_dir)
        self._warmup()

    def _warmup(self) -> None:
        """JIT compiler pre-warmer."""
        try:
            q = np.zeros((60, 63), dtype=np.float64)
            t = np.zeros((1, 60, 63), dtype=np.float64)
            th = np.array([0.15], dtype=np.float64)
            dtw_distance_batch(q, t, th)
        except Exception:
            pass

    def load_templates(self, template_dir: Path) -> None:
        """Load all custom gesture templates (.json files) from template_dir."""
        self._templates = {}
        if not template_dir.exists():
            try:
                template_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return

        for path in template_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                template = np.array(data["template"], dtype=np.float64)
                self._templates[data["name"]] = {
                    "template": template,
                    "threshold": data.get("threshold", 0.15),
                    "action": data["action"],
                }
            except Exception as e:
                logger.error("Failed loading template from json", path=str(path), error=str(e))
        logger.info("Custom gesture templates loaded", count=len(self._templates))
        self._precomputed_names = None  # Force rebuild

    def reset(self) -> None:
        """Reset the rolling buffer and frames counter on hand loss."""
        self.clear_buffer()
        self._last_match_monotonic = 0.0
        self._last_matched_name = None

    def clear_buffer(self) -> None:
        """Clear the rolling buffer state."""
        self._buffer.fill(0.0)
        self._buffer_idx = 0
        self._buffer_full = False
        self._frame_count = 0

    def update_buffer(self, hand: Hand) -> None:
        """Push current frame to landmark-centric circular rolling buffer."""
        normalized = to_hand_frame(hand.landmarks, hand.handedness)
        flat = np.array(
            [l.x for l in normalized] + [l.y for l in normalized] + [l.z for l in normalized],
            dtype=np.float64,
        )
        self._buffer[self._buffer_idx] = flat
        self._buffer_idx = (self._buffer_idx + 1) % 60
        self._frame_count += 1
        if self._frame_count >= 60:
            self._buffer_full = True

    def match(self, timestamp_s: float, correlation_id: str = "") -> GestureEvent | None:
        """Returns GestureEvent if a template matches AND per-gesture cooldown
        has elapsed. A matched gesture enters a refractory period during which
        the SAME gesture cannot re-trigger, followed by a global cooldown
        during which NO custom gesture can trigger."""
        if not self._buffer_full or not self._templates:
            return None

        # Global cooldown
        if (
            self._last_matched_name is not None
            and (timestamp_s - self._last_match_monotonic) < self._cooldown_s
        ):
            return None

        # Lazily (re)build the stacked template array
        if self._precomputed_names is None or self._precomputed_names != list(
            self._templates.keys()
        ):
            self._rebuild_precomputed()

        if (
            self._precomputed_templates is None
            or self._precomputed_thresholds is None
            or self._precomputed_names is None
            or self._precomputed_templates.shape[0] == 0
        ):
            return None

        # Align rolling buffer so that the oldest frame is first
        if self._buffer_idx == 0:
            query = self._buffer
        else:
            query = np.roll(self._buffer, -self._buffer_idx, axis=0)

        best_idx, best_dist = dtw_distance_batch(
            query,
            self._precomputed_templates,
            self._precomputed_thresholds,
        )

        if best_idx >= 0:
            name = self._precomputed_names[best_idx]
            # Per-gesture refractory
            if (
                name == self._last_matched_name
                and (timestamp_s - self._last_match_monotonic) < self._refractory_s
            ):
                return None

            self._last_match_monotonic = timestamp_s
            self._last_matched_name = name
            confidence = float(np.clip(1.0 - best_dist, 0.0, 1.0))

            # Reset buffer on successful match to prevent duplicate triggers from overlapping windows
            self.clear_buffer()

            return GestureEvent(
                gesture_name=name,
                gesture_type="custom",
                action=self._templates[name]["action"],
                confidence=confidence,
                hand="Right",  # TODO: plumb real handedness
                timestamp=timestamp_s,
                gesture_source="dtw",
                metadata={"correlation_id": correlation_id},
            )
        return None

    def _rebuild_precomputed(self) -> None:
        names = list(self._templates.keys())
        if not names:
            self._precomputed_templates = np.zeros((0, 60, 63), dtype=np.float64)
            self._precomputed_thresholds = np.zeros((0,), dtype=np.float64)
            self._precomputed_names = []
            return
        self._precomputed_templates = np.stack(
            [self._templates[n]["template"] for n in names],
            axis=0,
        ).astype(np.float64, copy=False)
        self._precomputed_thresholds = np.array(
            [self._templates[n]["threshold"] for n in names],
            dtype=np.float64,
        )
        self._precomputed_names = names
