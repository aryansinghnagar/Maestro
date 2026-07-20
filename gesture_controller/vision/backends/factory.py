import platform
import structlog
from typing import Any

from gesture_controller.core.protocols import InferenceBackend

logger = structlog.get_logger(__name__)


def create_backend(config: dict[str, Any]) -> InferenceBackend:
    """Create the best available inference backend."""
    preferred = config.get("engine", {}).get("inference_backend", "auto")

    if preferred != "auto":
        try:
            return _create_specific(preferred, config)
        except Exception as e:
            logger.warning(
                "Failed to create preferred backend, falling back to auto-detect",
                preferred=preferred,
                error=str(e),
            )

    return _auto_detect(config)


def _create_specific(name: str, config: dict[str, Any]) -> InferenceBackend:
    if name == "coreml":
        from gesture_controller.vision.backends.coreml_backend import CoreMLBackend

        return CoreMLBackend(config)
    elif name == "tensorrt":
        from gesture_controller.vision.backends.tensorrt_backend import TensorRTBackend

        return TensorRTBackend(config)
    elif name == "directml":
        from gesture_controller.vision.backends.directml_backend import DirectMLBackend

        return DirectMLBackend(config)
    elif name in ("cpu", "cpu-int8"):
        from gesture_controller.vision.backends.cpu_backend import CPUBackend

        return CPUBackend(config)
    else:
        raise ValueError(f"Unknown specific backend: {name}")


def _auto_detect(config: dict[str, Any]) -> InferenceBackend:
    system = platform.system()
    backend: InferenceBackend

    if system == "Darwin":
        try:
            from gesture_controller.vision.backends.coreml_backend import CoreMLBackend

            backend = CoreMLBackend(config)
            logger.info("Using CoreML backend", name=backend.name)
            return backend
        except Exception as e:
            logger.debug("CoreML backend unavailable, falling back", error=str(e))

    elif system == "Windows":
        try:
            from gesture_controller.vision.backends.tensorrt_backend import TensorRTBackend

            backend = TensorRTBackend(config)
            logger.info("Using TensorRT backend", name=backend.name)
            return backend
        except Exception as e:
            logger.debug("TensorRT backend unavailable, falling back", error=str(e))

        try:
            from gesture_controller.vision.backends.directml_backend import DirectMLBackend

            backend = DirectMLBackend(config)
            logger.info("Using DirectML backend", name=backend.name)
            return backend
        except Exception as e:
            logger.debug("DirectML backend unavailable, falling back", error=str(e))

    elif system == "Linux":
        try:
            from gesture_controller.vision.backends.tensorrt_backend import TensorRTBackend

            backend = TensorRTBackend(config)
            logger.info("Using TensorRT backend", name=backend.name)
            return backend
        except Exception as e:
            logger.debug("TensorRT backend unavailable, falling back", error=str(e))

    # CPU Fallback
    from gesture_controller.vision.backends.cpu_backend import CPUBackend

    backend = CPUBackend(config)
    logger.info("Using CPU fallback backend", name=backend.name)
    return backend
