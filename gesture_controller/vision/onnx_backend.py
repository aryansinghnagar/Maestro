from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
import numpy as np
import cv2
import structlog

from gesture_controller.vision.palm_detector import PalmDetector
from gesture_controller.vision.hand_pose_estimator import HandPoseEstimator

logger = structlog.get_logger(__name__)

try:
    from gesture_controller.vision.constants import FRAME_WIDTH as _DEFAULT_W
    from gesture_controller.vision.constants import FRAME_HEIGHT as _DEFAULT_H
except Exception:  # pragma: no cover
    _DEFAULT_W = 640
    _DEFAULT_H = 480
FRAME_WIDTH = _DEFAULT_W
FRAME_HEIGHT = _DEFAULT_H


@dataclass
class ONNXLandmark:
    x: float
    y: float
    z: float
    visibility: float = 1.0


@dataclass
class ONNXCategory:
    category_name: str
    score: float


@dataclass
class ONNXHandLandmarkerResult:
    hand_landmarks: List[List[ONNXLandmark]]
    handedness: List[List[ONNXCategory]]


class ONNXHandLandmarker:
    """ONNX Runtime based implementation of MediaPipe Hand Landmarker."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        data_dir = Path(__file__).parent.parent / "data"

        palm_model_path = data_dir / "palm_detection.onnx"
        landmark_model_path = data_dir / "hand_landmark.onnx"

        if not palm_model_path.exists() or not landmark_model_path.exists():
            raise FileNotFoundError(
                f"ONNX model files not found in {data_dir}. Run download script first."
            )

        conf_threshold = config.get("engine", {}).get("min_detection_confidence", 0.7)
        self.palm_det = PalmDetector(str(palm_model_path), scoreThreshold=conf_threshold)  # type: ignore[no-untyped-call]
        self.hand_pose = HandPoseEstimator(str(landmark_model_path), confThreshold=conf_threshold)  # type: ignore[no-untyped-call]
        logger.info("ONNX Runtime Hand Landmarker backend initialized successfully")

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def detect_hands(self, mp_image: Any, timestamp_ms: int) -> ONNXHandLandmarkerResult:
        """Run two-stage inference on input image and return landmark results."""
        # Extract raw numpy image from MediaPipe Image wrapper or numpy array
        if isinstance(mp_image, np.ndarray):
            image = mp_image
        elif hasattr(mp_image, "numpy_view"):
            try:
                image = mp_image.numpy_view()
            except Exception:
                image = getattr(mp_image, "data", mp_image)
        elif hasattr(mp_image, "_image"):
            image = mp_image._image
        else:
            image = getattr(mp_image, "data", mp_image)

        if not isinstance(image, np.ndarray) or image.size == 0:
            return ONNXHandLandmarkerResult(hand_landmarks=[], handedness=[])
        if image.ndim != 3 or image.shape[2] < 3:
            logger.warning("ONNX backend received non-RGB image; skipping frame")
            return ONNXHandLandmarkerResult(hand_landmarks=[], handedness=[])

        # Actual frame dims drive normalization (ReAct fix: was hardcoded 640x480).
        frame_h, frame_w = int(image.shape[0]), int(image.shape[1])
        if frame_h <= 0 or frame_w <= 0:
            return ONNXHandLandmarkerResult(hand_landmarks=[], handedness=[])

        # Convert RGB to BGR for OpenCV DNN preprocessing inside PalmDetector/HandPoseEstimator
        try:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.warning("cvtColor failed; skipping frame", error=str(e))
            return ONNXHandLandmarkerResult(hand_landmarks=[], handedness=[])

        # 1. Palm Detection
        palms = self.palm_det.infer(image_bgr)  # type: ignore[no-untyped-call]
        hand_landmarks_list = []
        handedness_list = []

        if palms is None or len(palms) == 0:
            return ONNXHandLandmarkerResult(hand_landmarks=[], handedness=[])

        # 2. Hand Landmark Inference per detected palm
        # MediaPipe max_hands config controls how many hands we process
        try:
            max_hands = int(self.config.get("engine", {}).get("max_hands", 2))
        except (TypeError, ValueError):
            max_hands = 2
        max_hands = max(1, min(max_hands, 4))
        # Sort palms by score (last column) so the best hands win when > max_hands.
        try:
            import numpy as _np

            if hasattr(palms, "shape") and palms.ndim == 2 and palms.shape[1] >= 19:
                order = _np.argsort(-palms[:, -1], kind="stable")
                palms = palms[order]
        except Exception:
            pass
        for palm in palms[:max_hands]:
            try:
                res = self.hand_pose.infer(image_bgr, palm)  # type: ignore[no-untyped-call]
            except Exception as e:
                logger.warning("Hand pose inference failed", error=str(e))
                continue
            if res is None:
                continue

            # Parse results
            # [0: 4] bounding box
            # [4: 67] screen landmarks (21 points * 3)
            # [67: 130] world landmarks (21 points * 3)
            # [130] handedness score
            # [131] confidence
            try:
                screen_lms_flat = res[4:67]
                handedness_val = res[130]
                conf = res[131]
            except Exception:
                continue

            # Reconstruct 21 landmarks and normalize to [0.0, 1.0]
            landmarks = []
            for i in range(21):
                offset = i * 3
                x = screen_lms_flat[offset]
                y = screen_lms_flat[offset + 1]
                z = screen_lms_flat[offset + 2]

                # Normalize pixel coordinates to 0.0-1.0 using ACTUAL dims.
                landmarks.append(
                    ONNXLandmark(
                        x=float(x / frame_w),
                        y=float(y / frame_h),
                        z=float(z / frame_w),
                    )
                )

            # Classify handedness: < 0.5 is Left, >= 0.5 is Right
            # In OpenCV model: 0 is Left, 1 is Right
            if handedness_val < 0.5:
                hand_type = "Left"
                score = float(1.0 - handedness_val)
            else:
                hand_type = "Right"
                score = float(handedness_val)

            hand_landmarks_list.append(landmarks)
            handedness_list.append([ONNXCategory(category_name=hand_type, score=score)])

        return ONNXHandLandmarkerResult(
            hand_landmarks=hand_landmarks_list, handedness=handedness_list
        )

    def close(self) -> None:
        """Close inference sessions (release native ORT handles)."""
        for sess_holder in (getattr(self, "palm_det", None), getattr(self, "hand_pose", None)):
            close_fn = getattr(sess_holder, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass
            elif sess_holder is not None:
                sess = getattr(sess_holder, "session", None)
                if sess is not None:
                    try:
                        setattr(sess_holder, "session", None)
                    except Exception:
                        pass
