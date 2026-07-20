import numpy as np
import structlog
from typing import Any

from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.models.data_types import Hand, Landmark3D
from gesture_controller.core.hand_tracker import HandTracker
from gesture_controller.vision.one_euro_filter import OneEuroFilter

logger = structlog.get_logger(__name__)


class InferencePipeline:
    """Manages landmark extraction, tracking, and filtering."""

    def __init__(self, config: ConfigManager, landmark_extractor_cls: Any = None, compute_features_fn: Any = None) -> None:
        self._config = config
        
        if landmark_extractor_cls is None:
            from gesture_controller.vision.landmark_extractor import LandmarkExtractor as default_cls
            self._extractor = default_cls(config._config)
        else:
            self._extractor = landmark_extractor_cls(config._config)
            
        self._compute_features_fn = compute_features_fn
        self._hand_tracker = HandTracker()
        self._filters: dict[int, OneEuroFilter] = {}
        self._active_track_ids: set[int] = set()

        max_hands = config.get("engine.max_hands", 2)
        self._raw_bufs = [np.empty((21, 3), dtype=np.float64) for _ in range(max_hands)]
        self._arr_bufs = [np.empty((21, 3), dtype=np.float64) for _ in range(max_hands)]
        self._centered_bufs = [np.empty((21, 3), dtype=np.float64) for _ in range(max_hands)]

    def process(self, shm_name: str, timestamp: float, frame_count: int) -> tuple[list[Hand], list[Hand], list[tuple[int, Any]]]:
        """Run landmark extraction, tracking, filtering, and feature extraction."""
        raw_hands = self._extractor.extract(shm_name, int(timestamp * 1000))
        if not raw_hands:
            # Reset tracker/filters when hand is lost
            self.reset()
            return [], [], []

        # Resolve compute_features dynamically to support late patching in tests
        if self._compute_features_fn is not None:
            compute_features_fn = self._compute_features_fn
        else:
            try:
                from gesture_controller.core.engine import compute_features as engine_compute_features
                compute_features_fn = engine_compute_features
            except ImportError:
                from gesture_controller.models.feature_engineering import compute_features as default_compute_features
                compute_features_fn = default_compute_features

        tracked_assignments = self._hand_tracker.update(raw_hands)
        smoothed_hands = []
        features_list = []

        for idx, (hand, track_id) in enumerate(tracked_assignments):
            # Safe boundary check for pre-allocated buffers length
            if idx >= len(self._raw_bufs):
                break

            # Convert hand landmarks to numpy coordinates without list comprehensions/allocations
            lm_array = self._raw_bufs[idx]
            if len(hand.landmarks) < 21:
                continue

            for i, l in enumerate(hand.landmarks):
                lm_array[i, 0] = l.x
                lm_array[i, 1] = l.y
                lm_array[i, 2] = l.z

            # Get or create One-Euro filter per hand track ID
            filt = self._filters.get(track_id)
            if filt is None:
                filt = OneEuroFilter(self._config._config)
                self._filters[track_id] = filt

            # Depth metric: Wrist to Index MCP length using fast scalar math
            dm_x = lm_array[5, 0] - lm_array[0, 0]
            dm_y = lm_array[5, 1] - lm_array[0, 1]
            dm_z = lm_array[5, 2] - lm_array[0, 2]
            depth_metric = float(np.sqrt(dm_x*dm_x + dm_y*dm_y + dm_z*dm_z))

            # Apply One-Euro filter
            filtered, velocity, acceleration = filt.filter(
                lm_array, timestamp, lighting_metric=None, depth_metric=depth_metric
            )

            # Reconstruct Hand with filtered positions
            smoothed_landmarks = tuple(
                Landmark3D(x=f[0], y=f[1], z=f[2]) for f in filtered
            )
            smoothed_hand = Hand(
                landmarks=smoothed_landmarks,
                handedness=hand.handedness,
                confidence=hand.confidence,
            )
            smoothed_hands.append(smoothed_hand)

            # Compute invariant features with pre-allocated buffer injection
            try:
                features = compute_features_fn(
                    smoothed_hand,
                    velocity,
                    acceleration,
                    timestamp,
                    frame_count,
                    arr_buf=self._arr_bufs[idx],
                    centered_buf=self._centered_bufs[idx],
                )
            except TypeError:
                features = compute_features_fn(
                    smoothed_hand, velocity, acceleration, timestamp, frame_count
                )
            features_list.append((track_id, features))

        # Identify and clean up retired track IDs
        current_track_ids = {track_id for _, track_id in tracked_assignments}
        retired_track_ids = self._active_track_ids - current_track_ids
        for retired_id in retired_track_ids:
            self._filters.pop(retired_id, None)
        self._active_track_ids = current_track_ids

        return raw_hands, smoothed_hands, features_list

    def reset(self) -> None:
        for f in self._filters.values():
            f.reset()
        self._filters.clear()
        self._active_track_ids.clear()
        self._hand_tracker.reset()

    def close(self) -> None:
        self._extractor.close()
