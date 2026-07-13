---
title: "DS-001: Inference Backend Spec"
---

## DS-001: Inference Backend Spec

**Confidence: High.** Full design spec for the inference backend abstraction.

### 96.1 Overview

The InferenceBackend Protocol abstracts hand landmark detection. Multiple backends implement the Protocol; a factory auto-detects the best available backend per platform.

### 96.2 Architecture

```
┌─────────────────────────────────────────┐
│         LandmarkExtractor               │
│  (reads SHM, calls backend, returns     │
│   list[Hand])                           │
└──────────────┬──────────────────────────┘
               │ uses
               ▼
┌──────────────────────────────────────────┐
│      InferenceBackend (Protocol)         │
│  detect_hands(frame, ts) -> Hands    │
│  close()                                 │
└──────────────┬───────────────────────────┘
               │ implemented by
       ┌───────┼───────┬───────┬───────┐
       ▼       ▼       ▼       ▼       ▼
   CoreML  TensorRT DirectML OpenVINO  CPU
   (macOS) (NVIDIA)(Win)   (Intel)  (fallback)
```

### 96.3 Protocol definition

```python
@runtime_checkable
class InferenceBackend(Protocol):
    @property
    def name(self) -> str: ...

    def detect_hands(
        self, frame: np.ndarray, timestamp_ms: int
    ) -> list[Hand] | None: ...

    def close(self) -> None: ...
```

### 96.4 Backend selection algorithm

```python
def create_backend(config: dict) -> InferenceBackend:
    preferred = config.get("engine.inference_backend", "auto")

    if preferred != "auto":
        return _create_specific(preferred, config)

    return _auto_detect(config)

def _auto_detect(config: dict) -> InferenceBackend:
    system = platform.system()

    if system == "Darwin":
        # Try CoreML (Apple Silicon only)
        if _is_apple_silicon():
            try:
                return CoreMLBackend(config)
            except RuntimeError:
                pass
        # Fall through to CPU

    elif system == "Windows":
        # Try TensorRT (NVIDIA), then DirectML
        if _has_nvidia_gpu():
            try:
                return TensorRTBackend(config)
            except RuntimeError:
                pass
        try:
            return DirectMLBackend(config)
        except RuntimeError:
            pass

    elif system == "Linux":
        # Try TensorRT (NVIDIA), then OpenVINO (Intel)
        if _has_nvidia_gpu():
            try:
                return TensorRTBackend(config)
            except RuntimeError:
                pass
        if _has_intel_gpu():
            try:
                return OpenVINOBackend(config)
            except RuntimeError:
                pass

    # Fallback to CPU
    return CPUBackend(config)
```

### 96.5 Backend capabilities matrix

| Backend | Platform | Hardware | INT8 | FP16 | Cache | Warm-up |
|---|---|---|---|---|---|---|
| CoreML | macOS | Apple Silicon | ✅ | ✅ | ✅ | ~500ms |
| TensorRT | Win/Linux | NVIDIA | ✅ | ✅ | ✅ | ~2s |
| DirectML | Windows | Any DX12 GPU | ❌ | ✅ | ❌ | ~300ms |
| OpenVINO | Linux | Intel | ✅ | ✅ | ✅ | ~400ms |
| CPU | Any | Any | ✅ | ❌ | ❌ | ~100ms |

### 96.6 Configuration

```yaml
engine:
  inference_backend: "auto"  # or "coreml", "tensorrt", "directml", "openvino", "cpu"
  quantization: "int8"       # or "fp16", "fp32"
  skip_model_verification: false
  directml_device_id: 0      # For DirectML only
```

### 96.7 Error handling

| Error | Backend behavior | User experience |
|---|---|---|
| Model file missing | Raise RuntimeError | "Please run: maestro models download" |
| EP not available | Fall back to next EP | Warning log; works |
| GPU out of memory | Fall back to CPU | Warning log; works |
| Model corrupted (SHA mismatch) | Re-download | "Re-downloading model..." |
| Inference timeout (5s) | Skip frame | Warning log; may drop frames |

### 96.8 Telemetry

Each backend reports:
- `backend.name` (string)
- `backend.inference_latency_ms` (histogram)
- `backend.errors.count` (counter, tagged by error type)

### 96.9 Testing

Each backend must pass:
- `test_backend_detect_hands` — basic detection
- `test_backend_close` — resource cleanup
- `test_backend_name` — name property
- `test_backend_warmup` — first inference <5s
- `test_backend_no_memory_leak` — 1000 inferences, memory stable

### 96.10 Future backends

- **ROCm EP** (AMD Linux) — when stable
- **Vulkan EP** — when ONNX Runtime supports it
- **WebGPU EP** — when stable (could enable browser-based Maestro)

---