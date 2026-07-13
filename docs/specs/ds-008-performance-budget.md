---
title: "DS-008: Performance Budget Spec"
---

## DS-008: Performance Budget Spec

### 103.1 Budget table

See §34.1.

### 103.2 Budget enforcement

See §34.2.

### 103.3 Budget revision process

See §34.3.

### 103.4 Budget alerts

See §34.4.

### 103.5 Profiling methodology

See §25.

### 103.6 Component-level targets

| Component | Current P50 | Target P50 | Budget enforcement |
|---|---|---|---|
| `OneEuroFilter.filter()` | 45µs | 10µs | CI benchmark |
| `compute_features()` | 218µs | 50µs | CI benchmark |
| `GestureFSMManager.evaluate()` | 132µs | 20µs | CI benchmark |
| `CustomGestureMatcher.match()` | 2.7µs | 1µs | CI benchmark |
| `np.array allocation` | 18µs | 2µs | CI benchmark |
| `HandTracker.update()` | unknown | 5µs | CI benchmark |
| `LandmarkExtractor.detect_hands()` (GPU) | 15-25ms | <8ms | Manual (CI has no GPU) |
| `LandmarkExtractor.detect_hands()` (CPU) | 15-25ms | <15ms | CI benchmark |
| `FramePipeline.read()` | unknown | 50µs | CI benchmark |
| `ActionDispatcher.dispatch()` | <100µs | <100µs | CI benchmark |
| `EventBus.publish()` (async) | unknown | 50µs | CI benchmark |
| `OverlayHUD.paintEvent()` | unknown | 5ms | Manual |
| `TrayIcon.update_status()` | unknown | 1ms | Manual |
| **Python hot-path total** | 418µs | 83µs | CI benchmark |
| **E2E total (GPU)** | ~150ms | <15ms | Manual (CI has no GPU) |
| **E2E total (CPU)** | ~150ms | <30ms | CI benchmark |

### 103.7 Memory budgets

| Component | Target | Notes |
|---|---|---|
| Engine process RSS | <150MB | Includes ONNX Runtime, OpenCV |
| Camera process RSS | <50MB | Just OpenCV |
| Broker process RSS | <30MB | Minimal |
| Per-frame allocation | 0 | Pre-allocated buffers |
| Total system memory | <250MB | All processes combined |

### 103.8 CPU budgets

| Component | Target CPU% | Notes |
|---|---|---|
| Engine thread | <5% on M1, <10% on Intel i5 | At 30 FPS |
| Camera process | <3% | At 30 FPS |
| Broker process | <1% | Mostly idle |
| GUI thread | <2% | At 60 FPS idle, <10% when repainting |
| Total system CPU | <15% | All processes combined |

### 103.9 Binary size budget

| Component | Target | Notes |
|---|---|---|
| Maestro binary (Nuitka) | <25MB | Compressed |
| Models (downloaded) | <10MB | hand_landmark + palm_detector |
| Total install footprint | <35MB | Binary + models |

---