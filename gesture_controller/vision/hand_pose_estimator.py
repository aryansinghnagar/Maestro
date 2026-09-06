# mypy: ignore-errors
import os

import numpy as np
import cv2 as cv
import onnxruntime as ort


def _default_ort_session_options():
    """Performance optimization (P1): see ``palm_detector._default_ort_session_options``."""
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        cpu = os.cpu_count() or 4
        opts.intra_op_num_threads = max(1, min(cpu, 4))
        opts.inter_op_num_threads = 1
    except Exception:
        pass
    return opts


class HandPoseEstimator:
    def __init__(
        self,
        modelPath,
        confThreshold=0.8,
        backendId=0,
        targetId=0,
        providers=None,
        sess_options=None,
    ):
        self.model_path = modelPath
        self.conf_threshold = confThreshold
        self.backend_id = backendId
        self.target_id = targetId

        self.input_size = np.array([224, 224])  # wh
        self.PALM_LANDMARK_IDS = [0, 5, 9, 13, 17, 1, 2]
        self.PALM_LANDMARKS_INDEX_OF_PALM_BASE = 0
        self.PALM_LANDMARKS_INDEX_OF_MIDDLE_FINGER_BASE = 2
        self.PALM_BOX_PRE_SHIFT_VECTOR = [0, 0]
        self.PALM_BOX_PRE_ENLARGE_FACTOR = 4
        self.PALM_BOX_SHIFT_VECTOR = [0, -0.4]
        self.PALM_BOX_ENLARGE_FACTOR = 3
        self.HAND_BOX_SHIFT_VECTOR = [0, -0.1]
        self.HAND_BOX_ENLARGE_FACTOR = 1.65

        # Initialize onnxruntime session (DirectML preferred on Windows).
        if providers is None:
            import sys as _sys

            available = set(ort.get_available_providers())
            providers = ["CPUExecutionProvider"]
            if _sys.platform == "darwin":
                if "CoreMLExecutionProvider" in available:
                    providers.insert(0, "CoreMLExecutionProvider")
            elif _sys.platform == "win32":
                if "CUDAExecutionProvider" in available:
                    providers.insert(0, "CUDAExecutionProvider")
                if "DirectMLExecutionProvider" in available:
                    providers.insert(0, "DirectMLExecutionProvider")
            else:
                if "DirectMLExecutionProvider" in available:
                    providers.insert(0, "DirectMLExecutionProvider")
                if "CUDAExecutionProvider" in available:
                    providers.insert(0, "CUDAExecutionProvider")
        # Performance optimization (P1): default to graph-optimized session
        # options when the caller didn't supply their own.
        if sess_options is None:
            sess_options = _default_ort_session_options()

        self.session = ort.InferenceSession(
            self.model_path, sess_options=sess_options, providers=providers
        )

    @property
    def name(self):
        return self.__class__.__name__

    def close(self) -> None:
        """Release the native ORT session handle."""
        try:
            if getattr(self, "session", None) is not None:
                self.session = None  # type: ignore[assignment]
        except Exception:
            pass

    def __del__(self):  # pragma: no cover
        try:
            self.close()
        except Exception:
            pass

    def set_backend_and_target(self, backendId, targetId):
        self.backend_id = backendId
        self.target_id = targetId

    def _crop_and_pad_from_palm(self, image, palm_bbox, for_rotation=False):
        # ReAct fix: guard degenerate/empty crops that crashed copyMakeBorder/resize.
        if image is None or getattr(image, "size", 0) == 0:
            raise ValueError("Empty image passed to _crop_and_pad_from_palm")
        try:
            palm_bbox = __import__("numpy").asarray(palm_bbox, dtype=__import__("numpy").float64)
        except Exception:
            raise ValueError("Invalid palm_bbox")
        if palm_bbox.shape != (2, 2) or not __import__("numpy").isfinite(palm_bbox).all():
            raise ValueError("Invalid palm_bbox shape/values")
        # shift bounding box
        wh_palm_bbox = np.maximum(palm_bbox[1] - palm_bbox[0], 1.0)
        if for_rotation:
            shift_vector = self.PALM_BOX_PRE_SHIFT_VECTOR
        else:
            shift_vector = self.PALM_BOX_SHIFT_VECTOR
        shift_vector = shift_vector * wh_palm_bbox
        palm_bbox = palm_bbox + shift_vector
        # enlarge bounding box
        center_palm_bbox = np.sum(palm_bbox, axis=0) / 2
        wh_palm_bbox = np.maximum(palm_bbox[1] - palm_bbox[0], 1.0)
        if for_rotation:
            enlarge_scale = self.PALM_BOX_PRE_ENLARGE_FACTOR
        else:
            enlarge_scale = self.PALM_BOX_ENLARGE_FACTOR
        new_half_size = wh_palm_bbox * enlarge_scale / 2
        palm_bbox = np.array([center_palm_bbox - new_half_size, center_palm_bbox + new_half_size])
        palm_bbox = palm_bbox.astype(np.int32)
        palm_bbox[:, 0] = np.clip(palm_bbox[:, 0], 0, image.shape[1])
        palm_bbox[:, 1] = np.clip(palm_bbox[:, 1], 0, image.shape[0])
        # crop to the size of interest
        x1, y1 = int(palm_bbox[0][0]), int(palm_bbox[0][1])
        x2, y2 = int(palm_bbox[1][0]), int(palm_bbox[1][1])
        if x2 <= x1:
            if x1 < image.shape[1]:
                x2 = min(image.shape[1], x1 + 1)
            else:
                x1 = max(0, x2 - 1)
        if y2 <= y1:
            if y1 < image.shape[0]:
                y2 = min(image.shape[0], y1 + 1)
            else:
                y1 = max(0, y2 - 1)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Degenerate palm crop (zero area)")
        image = image[y1:y2, x1:x2, :]
        if image.size == 0 or min(image.shape[:2]) <= 0:
            raise ValueError("Empty palm crop after clipping")
        # pad to ensure conner pixels won't be cropped
        if for_rotation:
            side_len = np.linalg.norm(image.shape[:2])
        else:
            side_len = max(image.shape[:2])

        side_len = int(side_len)
        pad_h = side_len - image.shape[0]
        pad_w = side_len - image.shape[1]
        left = pad_w // 2
        top = pad_h // 2
        right = pad_w - left
        bottom = pad_h - top
        image = cv.copyMakeBorder(
            image, top, bottom, left, right, cv.BORDER_CONSTANT, None, (0, 0, 0)
        )
        bias = palm_bbox[0] - [left, top]
        return image, palm_bbox, bias

    def _preprocess(self, image, palm):
        """
        Rotate input for inference.
        Parameters:
          image - input image of BGR channel order
          palm_bbox - palm bounding box found in image of format [[x1, y1], [x2, y2]] (top-left and bottom-right points)
          palm_landmarks - 7 landmarks (5 finger base points, 2 palm base points) of shape [7, 2]
        Returns:
          rotated_hand - rotated hand image for inference
          rotate_palm_bbox - palm box of interest range
          angle - rotate angle for hand
          rotation_matrix - matrix for rotation and de-rotation
          pad_bias - pad pixels of interest range
        """
        # crop and pad image to interest range
        pad_bias = np.array([0, 0], dtype=np.int32)  # left, top
        palm_bbox = palm[0:4].reshape(2, 2)
        image, palm_bbox, bias = self._crop_and_pad_from_palm(image, palm_bbox, True)
        image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        pad_bias += bias

        # Rotate input to have vertically oriented hand image
        # compute rotation
        palm_bbox -= pad_bias
        palm_landmarks = palm[4:18].reshape(7, 2) - pad_bias
        p1 = palm_landmarks[self.PALM_LANDMARKS_INDEX_OF_PALM_BASE]
        p2 = palm_landmarks[self.PALM_LANDMARKS_INDEX_OF_MIDDLE_FINGER_BASE]
        radians = np.pi / 2 - np.arctan2(-(p2[1] - p1[1]), p2[0] - p1[0])
        radians = radians - 2 * np.pi * np.floor((radians + np.pi) / (2 * np.pi))
        angle = np.rad2deg(radians)
        #  get bbox center
        center_palm_bbox = np.sum(palm_bbox, axis=0) / 2
        #  get rotation matrix
        rotation_matrix = cv.getRotationMatrix2D(center_palm_bbox, angle, 1.0)
        #  get rotated image
        rotated_image = cv.warpAffine(image, rotation_matrix, (image.shape[1], image.shape[0]))
        #  get bounding boxes from rotated palm landmarks
        homogeneous_coord = np.c_[palm_landmarks, np.ones(palm_landmarks.shape[0])]
        rotated_palm_landmarks = np.array(
            [
                np.dot(homogeneous_coord, rotation_matrix[0]),
                np.dot(homogeneous_coord, rotation_matrix[1]),
            ]
        )
        #  get landmark bounding box
        rotated_palm_bbox = np.array(
            [np.amin(rotated_palm_landmarks, axis=1), np.amax(rotated_palm_landmarks, axis=1)]
        )  # [top-left, bottom-right]

        crop, rotated_palm_bbox, _ = self._crop_and_pad_from_palm(rotated_image, rotated_palm_bbox)
        blob = cv.resize(crop, dsize=self.input_size, interpolation=cv.INTER_AREA).astype(
            np.float32
        )
        blob = blob / 255.0

        return blob[np.newaxis, :, :, :], rotated_palm_bbox, angle, rotation_matrix, pad_bias

    def infer(self, image, palm):
        # Preprocess
        input_blob, rotated_palm_bbox, angle, rotation_matrix, pad_bias = self._preprocess(
            image, palm
        )

        # Forward via ONNX Runtime
        input_name = self.session.get_inputs()[0].name
        output_blob = self.session.run(None, {input_name: input_blob})

        # Postprocess
        results = self._postprocess(
            output_blob, rotated_palm_bbox, angle, rotation_matrix, pad_bias
        )
        return results  # [bbox_coords, landmarks_coords, conf]

    def _postprocess(self, blob, rotated_palm_bbox, angle, rotation_matrix, pad_bias):
        landmarks, conf, handedness, landmarks_word = blob

        conf = conf[0][0]
        if conf < self.conf_threshold:
            return None

        landmarks = landmarks[0].reshape(-1, 3)  # shape: (1, 63) -> (21, 3)
        landmarks_word = landmarks_word[0].reshape(-1, 3)  # shape: (1, 63) -> (21, 3)

        # transform coords back to the input coords
        wh_rotated_palm_bbox = rotated_palm_bbox[1] - rotated_palm_bbox[0]
        scale_factor = wh_rotated_palm_bbox / self.input_size
        landmarks[:, :2] = (landmarks[:, :2] - self.input_size / 2) * max(scale_factor)
        landmarks[:, 2] = landmarks[:, 2] * max(scale_factor)  # depth scaling
        coords_rotation_matrix = cv.getRotationMatrix2D((0, 0), angle, 1.0)
        rotated_landmarks = np.dot(landmarks[:, :2], coords_rotation_matrix[:, :2])
        rotated_landmarks = np.c_[rotated_landmarks, landmarks[:, 2]]
        rotated_landmarks_world = np.dot(landmarks_word[:, :2], coords_rotation_matrix[:, :2])
        rotated_landmarks_world = np.c_[rotated_landmarks_world, landmarks_word[:, 2]]
        #  invert rotation
        rotation_component = np.array(
            [
                [rotation_matrix[0][0], rotation_matrix[1][0]],
                [rotation_matrix[0][1], rotation_matrix[1][1]],
            ]
        )
        translation_component = np.array([rotation_matrix[0][2], rotation_matrix[1][2]])
        inverted_translation = np.array(
            [
                -np.dot(rotation_component[0], translation_component),
                -np.dot(rotation_component[1], translation_component),
            ]
        )
        inverse_rotation_matrix = np.c_[rotation_component, inverted_translation]
        #  get box center
        center = np.append(np.sum(rotated_palm_bbox, axis=0) / 2, 1)
        original_center = np.array(
            [np.dot(center, inverse_rotation_matrix[0]), np.dot(center, inverse_rotation_matrix[1])]
        )
        landmarks[:, :2] = rotated_landmarks[:, :2] + original_center + pad_bias

        # get bounding box from rotated_landmarks
        bbox = np.array(
            [np.amin(landmarks[:, :2], axis=0), np.amax(landmarks[:, :2], axis=0)]
        )  # [top-left, bottom-right]
        # shift bounding box
        wh_bbox = bbox[1] - bbox[0]
        shift_vector = self.HAND_BOX_SHIFT_VECTOR * wh_bbox
        bbox = bbox + shift_vector
        # enlarge bounding box
        center_bbox = np.sum(bbox, axis=0) / 2
        wh_bbox = bbox[1] - bbox[0]
        new_half_size = wh_bbox * self.HAND_BOX_ENLARGE_FACTOR / 2
        bbox = np.array([center_bbox - new_half_size, center_bbox + new_half_size])

        # [0: 4]: hand bounding box found in image of format [x1, y1, x2, y2] (top-left and bottom-right points)
        # [4: 67]: screen landmarks with format [x1, y1, z1, x2, y2 ... x21, y21, z21], z value is relative to WRIST
        # [67: 130]: world landmarks with format [x1, y1, z1, x2, y2 ... x21, y21, z21], 3D metric x, y, z coordinate
        # [130]: handedness, (left)[0, 1](right) hand
        # [131]: confidence
        return np.r_[
            bbox.reshape(-1),
            landmarks.reshape(-1),
            rotated_landmarks_world.reshape(-1),
            handedness[0][0],
            conf,
        ]
