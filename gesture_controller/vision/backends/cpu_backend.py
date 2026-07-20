import psutil
import onnxruntime as ort  # type: ignore[import-untyped]
from typing import Any

from gesture_controller.vision.backends.base_backend import BaseONNXBackend


class CPUBackend(BaseONNXBackend):
    """ONNX Runtime with CPU EP + optional INT8 quantization."""

    def __init__(self, config: dict[str, Any]) -> None:
        quantization = config.get("engine", {}).get("quantization", "int8")
        use_int8 = quantization == "int8"

        num_threads = min(psutil.cpu_count(logical=False) or 4, 8)
        providers = [
            (
                "CPUExecutionProvider",
                {
                    "intra_op_num_threads": num_threads,
                    "inter_op_num_threads": 1,
                },
            ),
        ]

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        super().__init__(config, providers, use_int8=use_int8, sess_options=sess_options)

    @property
    def name(self) -> str:
        return "cpu-int8" if self.use_int8 else "cpu"
