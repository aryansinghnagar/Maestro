from typing import Any
import onnxruntime as ort

from gesture_controller.vision.backends.base_backend import BaseONNXBackend


class CoreMLBackend(BaseONNXBackend):
    """CoreML execution provider backend for macOS Apple Silicon."""

    def __init__(self, config: dict[str, Any]) -> None:
        if "CoreMLExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("CoreMLExecutionProvider is not available on this system")

        providers = [
            ("CoreMLExecutionProvider", {
                "coreml_flags": 0,  # MLComputeUnits_All
            }),
            "CPUExecutionProvider",
        ]

        super().__init__(config, providers, use_int8=False)

    @property
    def name(self) -> str:
        return "coreml"
