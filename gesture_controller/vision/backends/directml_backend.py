from typing import Any
import onnxruntime as ort  # type: ignore[import-untyped]

from gesture_controller.vision.backends.base_backend import BaseONNXBackend


class DirectMLBackend(BaseONNXBackend):
    """DirectML execution provider backend for Windows GPUs."""

    def __init__(self, config: dict[str, Any]) -> None:
        available = ort.get_available_providers()
        dml_provider = None
        if "DmlExecutionProvider" in available:
            dml_provider = "DmlExecutionProvider"
        elif "DirectMLExecutionProvider" in available:
            dml_provider = "DirectMLExecutionProvider"

        if dml_provider is None:
            raise RuntimeError("DirectML execution provider is not available on this system")

        device_id = config.get("engine", {}).get("directml_device_id", 0)
        providers = [
            (
                dml_provider,
                {
                    "device_id": device_id,
                },
            ),
            "CPUExecutionProvider",
        ]

        super().__init__(config, providers, use_int8=False)

    @property
    def name(self) -> str:
        return "directml"
