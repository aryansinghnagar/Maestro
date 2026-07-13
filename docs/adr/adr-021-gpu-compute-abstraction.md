---
title: "ADR-021: GPU Compute Abstraction"
---

### ADR-021: GPU Compute Abstraction

**Date:** 2026-07-09
**Status:** Proposed
**Context:** As Maestro adds more ML models (gaze tracking, face mesh, future transformer gestures), the GPU compute strategy needs to be generalized beyond the InferenceBackend Protocol.

**Decision:** Define a `ComputeBackend` Protocol that abstracts over ONNX Runtime, PyTorch (if installed), and native Metal/DirectX/Vulkan compute shaders. Models declare their preferred backend; the runtime auto-selects the best available.

**Consequences:**
- Positive: Future-proof for adding non-ONNX models (e.g., PyTorch transformer for gesture recognition); unified memory management.
- Negative: Adds abstraction layer; potential performance overhead if not careful.

**Implementation:**
```python
class ComputeBackend(Protocol):
    def allocate_buffer(self, shape, dtype) -> Buffer: ...
    def run_model(self, model_id, inputs) -> list[Buffer]: ...
    def sync(self) -> None: ...
```