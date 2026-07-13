---
title: "RFC-003: GestureEngine Decomposition"
---

### RFC-003: GestureEngine Decomposition

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 4)

#### Problem
`GestureEngine` (506 LOC) is a god class with 20+ instance attributes and 18 responsibilities. It's explicitly omitted from coverage. It cannot be unit-tested without heavy mocking.

#### Proposed Solution

Split into 5 focused classes:

```
EngineCoordinator
├── FramePipeline (camera, SHM, frame_ready_event)
├── InferencePipeline (LandmarkExtractor, OneEuroFilter, HandTracker, features)
├── GestureRecognizer (GestureFSMManager, CustomGestureMatcher)
└── SignalHandler (SIGINT/SIGTERM, shutdown)
```

Each class has <100 LOC, single responsibility, and is independently testable.

#### Alternatives Considered
1. **Keep monolithic, add comprehensive mocking** — Rejected: 506 LOC × 18 responsibilities is unmaintainable
2. **Functional decomposition (no classes)** — Rejected: need state management (camera process, filters, FSMs)
3. **More classes (10+)** — Rejected: 5 is the sweet spot; more would be over-engineering

#### Migration Plan
1. Extract `FramePipeline` (camera process + SHM lifecycle)
2. Extract `InferencePipeline` (filter + tracker + features)
3. Extract `GestureRecognizer` (FSM + DTW + conflict resolution)
4. Extract `SignalHandler` (signal handling + shutdown coordination)
5. `EngineCoordinator` wires them together and runs the main loop
6. Each class gets its own test file

#### Backward Compatibility
- `GestureEngine` class removed (replaced by `EngineCoordinator`)
- All `engine.xxx` methods moved to appropriate new class
- Config keys unchanged

#### Tests
- `test_frame_pipeline.py` — camera process, SHM, frame skipping
- `test_inference_pipeline.py` — backend, tracker, filter, features
- `test_gesture_recognizer.py` — FSM, DTW, conflict resolution
- `test_signal_handler.py` — SIGINT/SIGTERM
- `test_engine_coordinator.py` — wiring, main loop

---