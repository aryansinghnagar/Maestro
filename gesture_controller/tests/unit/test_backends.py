import pytest
from unittest.mock import MagicMock, patch

from gesture_controller.vision.backends.factory import create_backend
from gesture_controller.vision.backends.cpu_backend import CPUBackend


def test_factory_cpu_backend() -> None:
    config = {
        "engine": {
            "inference_backend": "cpu",
            "quantization": "fp32",
        }
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("gesture_controller.vision.backends.base_backend.PalmDetector") as mock_palm, \
             patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator") as mock_pose:
            backend = create_backend(config)
            assert isinstance(backend, CPUBackend)
            assert backend.name == "cpu"
            mock_palm.assert_called_once()
            mock_pose.assert_called_once()


def test_factory_cpu_int8_backend() -> None:
    config = {
        "engine": {
            "inference_backend": "cpu-int8",
            "quantization": "int8",
        }
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("gesture_controller.vision.backends.base_backend.PalmDetector"), \
             patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator"):
            backend = create_backend(config)
            assert isinstance(backend, CPUBackend)
            assert backend.name == "cpu-int8"


def test_factory_auto_fallback_to_cpu() -> None:
    config = {
        "engine": {
            "inference_backend": "auto",
        }
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("onnxruntime.get_available_providers", return_value=["CPUExecutionProvider"]):
            with patch("gesture_controller.vision.backends.base_backend.PalmDetector"), \
                 patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator"):
                backend = create_backend(config)
                assert isinstance(backend, CPUBackend)


@patch("onnxruntime.get_available_providers")
def test_factory_coreml_creation(mock_providers) -> None:
    mock_providers.return_value = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    config = {
        "engine": {
            "inference_backend": "coreml",
        }
    }
    with patch("platform.system", return_value="Darwin"):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("gesture_controller.vision.backends.base_backend.PalmDetector"), \
                 patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator"):
                from gesture_controller.vision.backends.coreml_backend import CoreMLBackend
                backend = create_backend(config)
                assert isinstance(backend, CoreMLBackend)
                assert backend.name == "coreml"


@patch("onnxruntime.get_available_providers")
def test_factory_directml_creation(mock_providers) -> None:
    mock_providers.return_value = ["DmlExecutionProvider", "CPUExecutionProvider"]
    config = {
        "engine": {
            "inference_backend": "directml",
        }
    }
    with patch("platform.system", return_value="Windows"):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("gesture_controller.vision.backends.base_backend.PalmDetector"), \
                 patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator"):
                from gesture_controller.vision.backends.directml_backend import DirectMLBackend
                backend = create_backend(config)
                assert isinstance(backend, DirectMLBackend)
                assert backend.name == "directml"


@patch("onnxruntime.get_available_providers")
def test_factory_tensorrt_creation(mock_providers) -> None:
    mock_providers.return_value = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
    config = {
        "engine": {
            "inference_backend": "tensorrt",
        }
    }
    with patch("platform.system", return_value="Linux"):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("gesture_controller.vision.backends.base_backend.PalmDetector"), \
                 patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator"):
                from gesture_controller.vision.backends.tensorrt_backend import TensorRTBackend
                backend = create_backend(config)
                assert isinstance(backend, TensorRTBackend)
                assert backend.name == "tensorrt"
