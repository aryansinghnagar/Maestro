import numpy as np
from typing import Any, Dict, List, Tuple
from gesture_controller.models.data_types import Hand, Landmark3D
import structlog

logger = structlog.get_logger(__name__)


class HandTracker:
    """Tracks hands across frames by assigning persistent integer IDs based on wrist positions."""

    def __init__(self, max_distance: float = 0.25, max_missing_frames: int = 5) -> None:
        self.max_distance = max_distance
        self.max_missing_frames = max_missing_frames
        self._next_id = 0
        self._tracks: Dict[int, Tuple[float, float, float]] = {}
        self._missing_frames: Dict[int, int] = {}

    def update(self, detected_hands: List[Hand]) -> List[Tuple[Hand, int]]:
        """Update tracked hands with new detections, returning (Hand, track_id) pairs."""
        assignments: List[Tuple[Hand, int]] = []
        if not detected_hands:
            for track_id in list(self._tracks.keys()):
                self._missing_frames[track_id] = self._missing_frames.get(track_id, 0) + 1
                if self._missing_frames[track_id] > self.max_missing_frames:
                    self._retire_track(track_id)
            return assignments

        new_wrists: List[Tuple[float, float, float]] = []
        for hand in detected_hands:
            if hand.landmarks and len(hand.landmarks) > 0:
                w = hand.landmarks[0]
                new_wrists.append((w.x, w.y, w.z))
            else:
                new_wrists.append((0.0, 0.0, 0.0))

        track_ids = list(self._tracks.keys())
        distances: List[Tuple[float, int, int]] = []

        for track_idx, track_id in enumerate(track_ids):
            t_wrist = self._tracks[track_id]
            for new_idx, n_wrist in enumerate(new_wrists):
                dist = float(
                    np.sqrt(
                        (t_wrist[0] - n_wrist[0]) ** 2
                        + (t_wrist[1] - n_wrist[1]) ** 2
                        + (t_wrist[2] - n_wrist[2]) ** 2
                    )
                )
                if dist <= self.max_distance:
                    distances.append((dist, track_idx, new_idx))

        distances.sort(key=lambda x: x[0])

        assigned_tracks: set[int] = set()
        assigned_news: set[int] = set()

        for dist, track_idx, new_idx in distances:
            track_id = track_ids[track_idx]
            if track_id not in assigned_tracks and new_idx not in assigned_news:
                assigned_tracks.add(track_id)
                assigned_news.add(new_idx)
                self._tracks[track_id] = new_wrists[new_idx]
                self._missing_frames[track_id] = 0
                assignments.append((detected_hands[new_idx], track_id))

        for track_id in track_ids:
            if track_id not in assigned_tracks:
                self._missing_frames[track_id] = self._missing_frames.get(track_id, 0) + 1
                if self._missing_frames[track_id] > self.max_missing_frames:
                    self._retire_track(track_id)

        for new_idx, hand in enumerate(detected_hands):
            if new_idx not in assigned_news:
                new_id = self._generate_id()
                self._tracks[new_id] = new_wrists[new_idx]
                self._missing_frames[new_id] = 0
                assignments.append((hand, new_id))

        return assignments

    def _generate_id(self) -> int:
        new_id = self._next_id
        self._next_id += 1
        return new_id

    def _retire_track(self, track_id: int) -> None:
        self._tracks.pop(track_id, None)
        self._missing_frames.pop(track_id, None)
        logger.debug("Retired hand track", track_id=track_id)

    def reset(self) -> None:
        """Reset the tracker state."""
        self._tracks.clear()
        self._missing_frames.clear()
        self._next_id = 0
