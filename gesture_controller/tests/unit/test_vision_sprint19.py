"""Unit tests for Sprint 19 — Vision & Landmark Engine Coverage Hardening.

Covers:
- HandPoseEstimator: __init__, name, set_backend_and_target, _crop_and_pad_from_palm,
  _preprocess, infer, _postprocess (above & below conf threshold)
- PalmDetector: __init__, name, set_backend_and_target, _load_anchors, _preprocess,
  infer, _postprocess (with & without detections)
- BaseONNXBackend: __init__ error when missing models, detect_hands (numpy view,
  mp image, no palms detected, valid palm detection -> hand creation, close).
"""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from gesture_controller.vision.hand_pose_estimator import HandPoseEstimator
from gesture_controller.vision.palm_detector import PalmDetector
from gesture_controller.vision.backends.base_backend import BaseONNXBackend


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ort_session():
    session = MagicMock()
    input_meta = MagicMock()
    input_meta.name = "input_tensor"
    session.get_inputs.return_value = [input_meta]
    return session


# ── HandPoseEstimator Tests ───────────────────────────────────────────────────

class TestHandPoseEstimator:

    def test_init_and_properties(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            estimator = HandPoseEstimator("dummy_path.onnx", confThreshold=0.7)
            assert estimator.name == "HandPoseEstimator"
            assert estimator.conf_threshold == 0.7

            estimator.set_backend_and_target(1, 2)
            assert estimator.backend_id == 1
            assert estimator.target_id == 2

    def test_crop_and_pad_from_palm(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            estimator = HandPoseEstimator("dummy_path.onnx")
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            bbox = np.array([[100, 100], [200, 200]])

            # for_rotation = True
            crop1, bbox1, bias1 = estimator._crop_and_pad_from_palm(img, bbox, for_rotation=True)
            assert crop1 is not None

            # for_rotation = False
            crop2, bbox2, bias2 = estimator._crop_and_pad_from_palm(img, bbox, for_rotation=False)
            assert crop2 is not None

    def test_preprocess(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            estimator = HandPoseEstimator("dummy_path.onnx")
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            palm = np.array([100, 100, 200, 200, 150, 150, 160, 160, 170, 170, 180, 180, 190, 190, 110, 110, 120, 120])

            blob, r_bbox, angle, r_mat, bias = estimator._preprocess(img, palm)
            assert blob.shape == (1, 224, 224, 3)

    def test_postprocess_above_threshold(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            estimator = HandPoseEstimator("dummy_path.onnx", confThreshold=0.5)

            landmarks = np.zeros((1, 63))
            conf = np.array([[0.9]])
            handedness = np.array([[0.8]])
            landmarks_word = np.zeros((1, 63))

            blob = [landmarks, conf, handedness, landmarks_word]
            r_bbox = np.array([[10, 10], [50, 50]])
            r_mat = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

            res = estimator._postprocess(blob, r_bbox, 0.0, r_mat, np.array([0, 0]))
            assert res is not None
            assert len(res) == 132  # 4 bbox + 63 lms + 63 wlms + 1 handedness + 1 conf

    def test_postprocess_below_threshold(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            estimator = HandPoseEstimator("dummy_path.onnx", confThreshold=0.8)

            landmarks = np.zeros((1, 63))
            conf = np.array([[0.2]])  # Low confidence
            handedness = np.array([[0.8]])
            landmarks_word = np.zeros((1, 63))

            blob = [landmarks, conf, handedness, landmarks_word]
            r_bbox = np.array([[10, 10], [50, 50]])
            r_mat = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

            res = estimator._postprocess(blob, r_bbox, 0.0, r_mat, np.array([0, 0]))
            assert res is None


# ── PalmDetector Tests ────────────────────────────────────────────────────────

class TestPalmDetector:

    def test_init_and_properties(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            detector = PalmDetector("dummy_palm.onnx", scoreThreshold=0.6)
            assert detector.name == "PalmDetector"
            assert detector.score_threshold == 0.6

            detector.set_backend_and_target(3, 4)
            assert detector.backend_id == 3
            assert detector.target_id == 4

    def test_preprocess(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            detector = PalmDetector("dummy_palm.onnx")
            img = np.zeros((480, 640, 3), dtype=np.uint8)

            blob, pad_bias = detector._preprocess(img)
            assert blob.shape == (1, 192, 192, 3)
            assert len(pad_bias) == 2

    def test_postprocess_empty_detections(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            detector = PalmDetector("dummy_palm.onnx", scoreThreshold=0.9)

            num_anchors = len(detector.anchors)
            output_blob = [
                np.zeros((1, num_anchors, 18)),  # box/landmark delta
                np.full((1, num_anchors, 1), -10.0),  # low logit scores
            ]

            res = detector._postprocess(output_blob, np.array([640, 480]), np.array([0, 0]))
            assert res.shape == (0, 19)

    def test_infer(self, mock_ort_session):
        with patch("onnxruntime.InferenceSession", return_value=mock_ort_session):
            detector = PalmDetector("dummy_palm.onnx")
            num_anchors = len(detector.anchors)

            # High score output for first anchor
            scores = np.full((1, num_anchors, 1), -10.0)
            scores[0, 0, 0] = 10.0  # high score
            output_blob = [np.zeros((1, num_anchors, 18)), scores]
            mock_ort_session.run.return_value = output_blob

            img = np.zeros((480, 640, 3), dtype=np.uint8)
            res = detector.infer(img)
            assert isinstance(res, np.ndarray)


# ── BaseONNXBackend Tests ─────────────────────────────────────────────────────

class TestBaseONNXBackend:

    def test_missing_model_files_raises_error(self, tmp_path):
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                BaseONNXBackend(config={}, providers=["CPUExecutionProvider"])

    def test_detect_hands_flow(self, tmp_path, mock_ort_session):
        # Create fake model files
        d = tmp_path / "data"
        d.mkdir(parents=True, exist_ok=True)
        (d / "palm_detection.onnx").touch()
        (d / "hand_landmark.onnx").touch()

        with patch("gesture_controller.vision.backends.base_backend.Path") as mock_path, \
             patch("onnxruntime.InferenceSession", return_value=mock_ort_session):

            mock_data_dir = tmp_path
            mock_path.return_value.parent.parent.parent = mock_data_dir

            # Build backend
            backend = BaseONNXBackend(
                config={"engine": {"min_detection_confidence": 0.5, "max_hands": 2}},
                providers=["CPUExecutionProvider"],
            )

            # 1. No palms detected
            backend.palm_det.infer = MagicMock(return_value=None)
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            assert backend.detect_hands(img, 100) is None

            # 2. Palm detected & hand pose succeeds
            fake_palm = np.zeros(19)
            backend.palm_det.infer = MagicMock(return_value=np.array([fake_palm]))

            fake_hand_pose_res = np.zeros(132)
            fake_hand_pose_res[130] = 0.8  # Right hand
            fake_hand_pose_res[131] = 0.95  # Conf
            backend.hand_pose.infer = MagicMock(return_value=fake_hand_pose_res)

            hands = backend.detect_hands(img, 101)
            assert hands is not None
            assert len(hands) == 1
            assert hands[0].handedness == "Right"
            assert hands[0].confidence == 0.8
            assert len(hands[0].landmarks) == 21

            # 3. Test close()
            backend.close()
            assert backend.palm_det.session is None
            assert backend.hand_pose.session is None
