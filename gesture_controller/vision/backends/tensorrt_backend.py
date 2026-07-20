import os
import onnxruntime as ort
from pathlib import Path
from typing import Any

from gesture_controller.vision.backends.base_backend import BaseONNXBackend
from gesture_controller.core.paths import user_cache_dir


class TensorRTBackend(BaseONNXBackend):
    """ONNX Runtime with TensorRT EP for NVIDIA GPUs."""

    def __init__(self, config: dict[str, Any]) -> None:
        available = ort.get_available_providers()
        if "TensorrtExecutionProvider" not in available:
            raise RuntimeError("TensorrtExecutionProvider is not available on this system")

        cache_dir = user_cache_dir() / "tensorrt_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        providers = [
            ("TensorrtExecutionProvider", {
                "trt_max_workspace_size": 4 << 30,  # 4 GB
                "trt_fp16_enable": True,            # Use FP16
                "trt_engine_cache_enable": True,
                "trt_engine_cache_path": str(cache_dir),
                "trt_max_partition_iterations": 1000,
                "trt_min_subgraph_size": 5,
            }),
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]

        super().__init__(config, providers, use_int8=False)

    @property
    def name(self) -> str:
        return "tensorrt"
