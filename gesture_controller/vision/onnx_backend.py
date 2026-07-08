from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
import numpy as np
import cv2
import structlog

from gesture_controller.vision.mp_palmdet import MPPalmDet
from gesture_controller.vision.mp_handpose import MPHandPose

logger = structlog.get_logger(__name__)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480


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
        self.palm_det = MPPalmDet(str(palm_model_path), scoreThreshold=conf_threshold)  # type: ignore[no-untyped-call]
        self.hand_pose = MPHandPose(str(landmark_model_path), confThreshold=conf_threshold)  # type: ignore[no-untyped-call]
        logger.info("ONNX Runtime Hand Landmarker backend initialized successfully")

    def detect_for_video(self, mp_image: Any, timestamp_ms: int) -> ONNXHandLandmarkerResult:
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

        # Convert RGB to BGR for OpenCV DNN preprocessing inside MPPalmDet/MPHandPose
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # 1. Palm Detection
        palms = self.palm_det.infer(image_bgr)  # type: ignore[no-untyped-call]
        hand_landmarks_list = []
        handedness_list = []

        if palms is None or len(palms) == 0:
            return ONNXHandLandmarkerResult(hand_landmarks=[], handedness=[])

        # 2. Hand Landmark Inference per detected palm
        # MediaPipe max_hands config controls how many hands we process
        max_hands = self.config.get("engine", {}).get("max_hands", 2)
        for palm in palms[:max_hands]:
            res = self.hand_pose.infer(image_bgr, palm)  # type: ignore[no-untyped-call]
            if res is None:
                continue

            # Parse results
            # [0: 4] bounding box
            # [4: 67] screen landmarks (21 points * 3)
            # [67: 130] world landmarks (21 points * 3)
            # [130] handedness score
            # [131] confidence
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

                # Normalize pixel coordinates to 0.0-1.0
                landmarks.append(
                    ONNXLandmark(
                        x=float(x / FRAME_WIDTH),
                        y=float(y / FRAME_HEIGHT),
                        z=float(z / FRAME_WIDTH),
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
        """Close inference sessions."""
        pass
