import time
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from multiprocessing import shared_memory
import structlog
from pathlib import Path
from typing import Any

from gesture_controller.models.data_types import Hand, Landmark3D

logger = structlog.get_logger(__name__)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_CHANNELS = 3

MODEL_PATH = Path(__file__).parent.parent / "data" / "hand_landmarker.task"


class LandmarkExtractor:
    """Wraps MediaPipe HandLandmarker Tasks API.
    Reads from SharedMemory, outputs project Hand dataclasses.
    MediaPipe internal structures and objects NEVER leak outside this class."""

    def __init__(self, config: dict[str, Any]) -> None:
        model_path_str = str(MODEL_PATH)
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"MediaPipe Hand Landmarker model file not found at {model_path_str}"
            )

        # Verify SHA256 integrity unless disabled in config
        skip_verify = config.get("engine", {}).get("skip_model_verification", False)
        if not skip_verify:
            import hashlib

            expected_sha256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
            h = hashlib.sha256()
            try:
                with open(MODEL_PATH, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                file_hash = h.hexdigest().lower()
                if file_hash != expected_sha256:
                    raise RuntimeError(
                        f"MediaPipe Hand Landmarker model file integrity check failed! "
                        f"Expected hash: {expected_sha256}, got: {file_hash}."
                    )
            except Exception as e:
                if isinstance(e, (RuntimeError, FileNotFoundError)):
                    raise
                raise RuntimeError(f"Failed to calculate model file hash: {e}") from e

        # Configure Tasks HandLandmarker options
        base_options = python.BaseOptions(model_asset_path=model_path_str)
        self._options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=config.get("engine", {}).get("max_hands", 2),
            min_hand_detection_confidence=config.get("engine", {}).get(
                "min_detection_confidence", 0.7
            ),
            min_hand_presence_confidence=config.get("engine", {}).get(
                "min_tracking_confidence", 0.5
            ),
        )
        self._landmarker = vision.HandLandmarker.create_from_options(self._options)
        logger.info("MediaPipe HandLandmarker Tasks API initialized in VIDEO mode")

    def extract(self, shm_name: str, timestamp_ms: int | None = None) -> list[Hand] | None:
        """Read frame from SharedMemory, extract landmarks, return list[Hand].
        Returns None if no hands detected."""
        if timestamp_ms is None:
            timestamp_ms = int(time.monotonic() * 1000)

        try:
            shm = shared_memory.SharedMemory(name=shm_name)
            frame = np.ndarray(
                (FRAME_HEIGHT, FRAME_WIDTH, FRAME_CHANNELS),
                dtype=np.uint8,
                buffer=shm.buf,
            )
            rgb_frame = frame.copy()  # MediaPipe needs contiguous array
            shm.close()
        except FileNotFoundError:
            logger.warning("SharedMemory not found during landmark extraction")
            return None
        except Exception as e:
            logger.error("Error reading frame from SharedMemory", error=str(e))
            return None

        # Wrap NumPy array into MediaPipe Image object
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        try:
            results = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception as e:
            logger.error("MediaPipe HandLandmarker inference failed", error=str(e))
            return None

        if not results.hand_landmarks:
            return None

        hands = []
        for hand_landmarks, handedness in zip(
            results.hand_landmarks,
            results.handedness,
        ):
            landmarks = tuple(
                Landmark3D(
                    x=float(lm.x),
                    y=float(lm.y),
                    z=float(lm.z),
                    visibility=float(lm.visibility) if hasattr(lm, "visibility") else 1.0,
                )
                for lm in hand_landmarks
            )

            # handedness is a list of Category objects
            hand_type = handedness[0].category_name
            confidence = float(handedness[0].score)

            hand = Hand(
                landmarks=landmarks,
                handedness=hand_type,
                confidence=confidence,
            )
            hands.append(hand)

        return hands

    def close(self) -> None:
        """Close HandLandmarker resource."""
        try:
            self._landmarker.close()
            logger.info("MediaPipe HandLandmarker closed")
        except Exception as e:
            logger.debug("Error closing MediaPipe HandLandmarker", error=str(e))
