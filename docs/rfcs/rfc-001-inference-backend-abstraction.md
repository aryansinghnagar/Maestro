---
title: "RFC-001: Inference Backend Abstraction"
---

### RFC-001: Inference Backend Abstraction

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 6)

#### Problem
The `LandmarkExtractor` class directly instantiates either `mediapipe.tasks.python.vision.HandLandmarker` or `ONNXHandLandmarker` based on a boolean flag. Adding a new backend (CoreML, TensorRT, DirectML) requires modifying `LandmarkExtractor.__init__`.

#### Proposed Solution

```python
# core/protocols.py
class InferenceBackend(Protocol):
    def detect_hands(self, frame: np.ndarray, timestamp_ms: int) -> list[Hand]: ...
    def close(self) -> None: ...

# vision/backends/factory.py
def create_backend(config: dict) -> InferenceBackend:
    preferred = config.get("engine.inference_backend", "auto")
    if preferred == "auto":
        # Try CoreML → TensorRT → DirectML → OpenVINO → CPU
        ...
    return backend
```

#### Alternatives Considered
1. **Single MediaPipe backend** — Rejected: CPU-only, 15-25ms latency, dominant bottleneck
2. **Single ONNX CPU backend** — Rejected: 8-15ms is still slow; misses GPU opportunity
3. **Strategy pattern with explicit class** — Rejected: Protocol (structural typing) is more Pythonic

#### Migration Plan
1. Define `InferenceBackend` Protocol
2. Wrap existing MediaPipe and ONNX paths as backend implementations
3. Implement CoreML, DirectML, TensorRT backends
4. Add `create_backend()` factory with auto-detection
5. Update `LandmarkExtractor` to accept any `InferenceBackend`

#### Backward Compatibility
Existing `engine.use_onnx` config key maps to `engine.inference_backend: "onnx"` (deprecated) or `"cpu"` (default).

#### Tests
- Each backend must pass `test_backend_detect_hands`
- Auto-detection must select best available backend
- Backend `close()` must release all resources

#### Risks
- ONNX model conversion may fail → fallback to MediaPipe CPU
- CoreML ANE op coverage gaps → GPU fallback still 3× faster than CPU
- TensorRT cache invalidation on driver update → rebuild cache

---