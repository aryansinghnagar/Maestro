---
title: "RFC-009: GPU Compute Abstraction"
---

### RFC-009: GPU Compute Abstraction

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Draft (v0.3+)

#### Problem
As Maestro adds more ML models (gaze tracking, face mesh, future transformer gestures), the GPU compute strategy needs to be generalized beyond the InferenceBackend Protocol.

#### Proposed Solution

Define a `ComputeBackend` Protocol that abstracts over ONNX Runtime, PyTorch (if installed), and native Metal/DirectX/Vulkan compute shaders. Models declare their preferred backend; the runtime auto-selects the best available.

```python
class ComputeBackend(Protocol):
    def allocate_buffer(self, shape, dtype) -> Buffer: ...
    def run_model(self, model_id, inputs) -> list[Buffer]: ...
    def sync(self) -> None: ...
```

#### Alternatives
1. **ONNX Runtime only** — Rejected: limits future models that aren't easily converted to ONNX
2. **PyTorch only** — Rejected: too heavy; not all models need it
3. **No abstraction** — Rejected: tight coupling to specific backend

#### Migration
Defer to v0.3+. Current `InferenceBackend` Protocol (RFC-001) is sufficient for hand tracking.

---