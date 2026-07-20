---
title: "ADR-011: ONNX Runtime over MediaPipe Python"
---

### ADR-011: ONNX Runtime over MediaPipe Python

**Date:** 2026-07-09
**Status:** Accepted

**Context:** MediaPipe Tasks Python API is CPU-only on desktop (GPU delegates are mobile-only, per GitHub issue #5344). This caps inference at 15-25ms per frame, dominating the E2E latency budget. ONNX Runtime provides cross-platform GPU execution providers (CoreML, DirectML, TensorRT, OpenVINO) that can cut inference to 3-8ms.

**Decision:** Migrate hand-tracking inference from `mediapipe` Python package to ONNX Runtime with the converted hand_landmarker ONNX model. Ship multi-EP strategy: try CoreML on macOS, TensorRT/DirectML on Windows/Linux, fall back to CPU.

**Implementation Details:**
- Created modular `InferenceBackend` protocol and factory pattern in `gesture_controller.vision.backends`.
- Implemented `CoreMLBackend`, `TensorRTBackend`, `DirectMLBackend`, and `CPUBackend` wrappers.
- Quantized the model dynamically to INT8 (`hand_landmark_int8.onnx`), shrinking model size by ~70% and accelerating CPU-fallback paths.

**Consequences:**
- Positive: 3-5× inference speedup on GPU hardware; INT8 quantization option; no dependency on MediaPipe's Python wrapper.
- Negative: Must maintain ONNX model conversion pipeline; lose MediaPipe's built-in palm→hand two-stage pipeline (must reimplement).
- Supersedes: Parts of ADR-001 (inference process isolation becomes less critical with faster inference).

**Validation:**
- All execution provider backends implemented and validated via unit test suite (`test_backends.py`).
- 258/258 unit tests passing successfully with 70.50% total coverage.