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

        # Clamp max_hands strictly between 1 and 2 (inclusive) to prevent collisions (SC-01)
        raw_max_hands = config.get("engine", {}).get("max_hands", 2)
        max_hands = max(1, min(2, raw_max_hands))
        if raw_max_hands != max_hands:
            logger.warning(
                "max_hands config capped to prevent FSM/filter collisions",
                original=raw_max_hands,
                capped=max_hands,
            )

        # Configure Tasks HandLandmarker options
        base_options = python.BaseOptions(model_asset_path=model_path_str)
        self._options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=config.get("engine", {}).get(
                "min_detection_confidence", 0.7
            ),
            min_hand_presence_confidence=config.get("engine", {}).get(
                "min_tracking_confidence", 0.5
            ),
        )

        backend_name = config.get("engine", {}).get("inference_backend", "mediapipe")
        if config.get("engine", {}).get("use_onnx", False) and backend_name == "mediapipe":
            backend_name = "auto"

        self._is_onnx = backend_name != "mediapipe"
        if self._is_onnx:
            try:
                from gesture_controller.vision.backends.factory import create_backend

                self._landmarker = create_backend(config)
                logger.info(
                    "ONNX Runtime backend loaded successfully using factory",
                    backend=self._landmarker.name,
                )
            except Exception as e:
                logger.warning(
                    "ONNX Runtime initialization failed, falling back to MediaPipe Tasks API",
                    error=str(e),
                )
                self._landmarker = vision.HandLandmarker.create_from_options(self._options)
                self._is_onnx = False
        else:
            self._landmarker = vision.HandLandmarker.create_from_options(self._options)

        from gesture_controller.vision.double_buffer import DoubleFrameBuffer

        self._db: DoubleFrameBuffer | None = None
        logger.info("Inference backend initialized successfully")

    def extract(self, shm_name: str, timestamp_ms: int | None = None) -> list[Hand] | None:
        """Read frame from DoubleFrameBuffer, extract landmarks, return list[Hand].
        Returns None if no hands detected."""
        if timestamp_ms is None:
            timestamp_ms = int(time.monotonic() * 1000)

        # Lazy attachment and caching of DoubleFrameBuffer
        from gesture_controller.vision.double_buffer import DoubleFrameBuffer

        if self._db is None or self._db.name != shm_name:
            if self._db:
                self._db.close()
            try:
                self._db = DoubleFrameBuffer(name=shm_name, create=False)
            except Exception as e:
                logger.error(
                    "Failed to attach to DoubleFrameBuffer during extraction",
                    name=shm_name,
                    error=str(e),
                )
                return None

        try:
            frame_bytes = self._db.read()
            if frame_bytes is None:
                logger.warning("Failed to read frame atomically from DoubleFrameBuffer")
                return None

            rgb_frame = (
                np.frombuffer(frame_bytes, dtype=np.uint8)
                .reshape((FRAME_HEIGHT, FRAME_WIDTH, FRAME_CHANNELS))
                .copy()
            )
        except Exception as e:
            logger.error("Error reading frame from DoubleFrameBuffer", error=str(e))
            return None

        # Wrap NumPy array into MediaPipe Image object
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        try:
            results = self._landmarker.detect_hands(mp_image, timestamp_ms)
        except Exception as e:
            logger.error("HandLandmarker inference failed", error=str(e))
            return None

        if results is None:
            return None

        if isinstance(results, list):
            return results

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
        """Close HandLandmarker and DoubleFrameBuffer resources."""
        if self._db:
            try:
                self._db.close()
            except Exception as e:
                logger.debug("Error closing DoubleFrameBuffer handle", error=str(e))
        try:
            self._landmarker.close()
            logger.info("MediaPipe HandLandmarker closed")
        except Exception as e:
            logger.debug("Error closing MediaPipe HandLandmarker", error=str(e))
