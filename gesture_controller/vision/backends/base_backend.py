import numpy as np
import cv2
import structlog
from pathlib import Path
from typing import Any

from gesture_controller.models.data_types import Hand, Landmark3D
from gesture_controller.vision.palm_detector import PalmDetector
from gesture_controller.vision.hand_pose_estimator import HandPoseEstimator
from gesture_controller.vision.constants import (
    FRAME_WIDTH,
    FRAME_HEIGHT,
    PALM_DETECTION_ONNX,
    HAND_LANDMARKER_ONNX,
    HAND_LANDMARKER_INT8_ONNX,
)

logger = structlog.get_logger(__name__)


class BaseONNXBackend:
    """Base class for all ONNX Runtime gesture inference backends."""

    def __init__(
        self,
        config: dict[str, Any],
        providers: list[Any],
        use_int8: bool = False,
        sess_options: Any = None,
    ) -> None:
        self.config = config
        self.providers = providers
        self.use_int8 = use_int8

        data_dir = Path(__file__).parent.parent.parent / "data"
        palm_model_path = data_dir / PALM_DETECTION_ONNX

        if use_int8:
            landmark_model_path = data_dir / HAND_LANDMARKER_INT8_ONNX
        else:
            landmark_model_path = data_dir / HAND_LANDMARKER_ONNX

        if not palm_model_path.exists():
            raise FileNotFoundError(f"Palm detection model not found: {palm_model_path}")
        if not landmark_model_path.exists():
            raise FileNotFoundError(f"Hand landmark model not found: {landmark_model_path}")

        conf_threshold = config.get("engine", {}).get("min_detection_confidence", 0.7)

        self.palm_det = PalmDetector(  # type: ignore[no-untyped-call]
            str(palm_model_path),
            scoreThreshold=conf_threshold,
            providers=providers,
            sess_options=sess_options,
        )
        self.hand_pose = HandPoseEstimator(  # type: ignore[no-untyped-call]
            str(landmark_model_path),
            confThreshold=conf_threshold,
            providers=providers,
            sess_options=sess_options,
        )

    def detect_hands(self, mp_image: Any, timestamp_ms: int) -> list[Hand] | None:
        """Run two-stage inference on input image and return landmark results."""
        # Extract raw numpy image from MediaPipe Image wrapper or numpy array
        if isinstance(mp_image, np.ndarray):
            image = mp_image
        elif hasattr(mp_image, "numpy_view"):
            image = mp_image.numpy_view()
        elif hasattr(mp_image, "_image"):
            image = mp_image._image
        else:
            image = getattr(mp_image, "data", mp_image)

        # Convert RGB to BGR for OpenCV DNN preprocessing inside PalmDetector/HandPoseEstimator
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # 1. Palm Detection
        palms = self.palm_det.infer(image_bgr)  # type: ignore[no-untyped-call]
        if palms is None or len(palms) == 0:
            return None

        # 2. Hand Landmark Inference per detected palm
        hands = []
        max_hands = self.config.get("engine", {}).get("max_hands", 2)
        for palm in palms[:max_hands]:
            res = self.hand_pose.infer(image_bgr, palm)  # type: ignore[no-untyped-call]
            if res is None:
                continue

            # Parse results
            screen_lms_flat = res[4:67]
            handedness_val = res[130]
            conf = res[131]

            # Reconstruct 21 landmarks and normalize to [0.0, 1.0]
            landmarks = []
            for i in range(21):
                offset = i * 3
                x = screen_lms_flat[offset]
                y = screen_lms_flat[offset + 1]
                z = screen_lms_flat[offset + 2]

                landmarks.append(
                    Landmark3D(
                        x=float(x / FRAME_WIDTH),
                        y=float(y / FRAME_HEIGHT),
                        z=float(z / FRAME_WIDTH),
                        visibility=1.0,
                    )
                )

            # Classify handedness: < 0.5 is Left, >= 0.5 is Right
            if handedness_val < 0.5:
                hand_type = "Left"
                score = float(1.0 - handedness_val)
            else:
                hand_type = "Right"
                score = float(handedness_val)

            hands.append(
                Hand(
                    landmarks=tuple(landmarks),
                    handedness=hand_type,
                    confidence=score,
                )
            )

        return hands if hands else None

    def close(self) -> None:
        """Release session resources."""
        if hasattr(self, "palm_det") and self.palm_det:
            self.palm_det.session = None
        if hasattr(self, "hand_pose") and self.hand_pose:
            self.hand_pose.session = None
