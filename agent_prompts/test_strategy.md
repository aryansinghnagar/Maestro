# Test Strategy — AI Agent Reference

**Purpose:** This file defines the complete testing strategy for the hand-gesture controller. Feed this to your coding agent when writing tests, setting up CI, or debugging quality issues.

---

## 1. Testing Pyramid

```
                    /\
                   /  E2E  \              5%  - Full pipeline, real camera (manual + CI-nightly)
                  /----------\
                 / Integration \           15% - Cross-module, SharedMemory, event bus
                /--------------\
               /    Unit Tests    \       60% - Per-module, mocked dependencies
              /--------------------\
             /   Property & Replay    \  20% - Hypothesis + landmark fixtures
            /________________________\
```

### 1.1 Unit Tests (60%)

Location: `tests/unit/`
Naming: `test_{module}_{function}_{scenario}.py`

Every module must have a corresponding test file:

| Module | Test File | Key Tests |
|---|---|---|
| `vision/camera_stream.py` | `test_camera_stream.py` | Reconnect on disconnect, SharedMemory write, watchdog timeout, backend fallback |
| `vision/landmark_extractor.py` | `test_landmark_extractor.py` | MediaPipe mock, Hand dataclass conversion, empty frame, partial hand |
| `vision/one_euro_filter.py` | `test_one_euro_filter.py` | Static input->zero output, step response, velocity adaptation, edge case (NaN, inf) |
| `models/feature_engineering.py` | `test_feature_engineering.py` | Joint angles (0, 90, 180 deg), finger curl (open/closed), palm normal, scale invariance |
| `models/dtw_matcher.py` | `test_dtw_matcher.py` | Identical sequences->0, orthogonal sequences->high, threshold boundary, numba compile |
| `core/state_machine.py` | `test_state_machine.py` | All FSM transitions, timeout, abort, cooldown, parallel FSM priority |
| `core/event_bus.py` | `test_event_bus.py` | Subscribe/publish, unsubscribe, multiple subscribers, queue overflow |
| `core/config_manager.py` | `test_config_manager.py` | Valid YAML, invalid YAML, schema violation, AST-safe condition parse, migration |
| `os_integration/action_dispatcher.py` | `test_action_dispatcher.py` | Action string parsing, app profile lookup, default fallback, unknown action |
| `actions/action_mapper.py` | `test_action_mapper.py` | "KeyPress:Ctrl+C", "MouseScroll:3", "OS:MinimizeActiveWindow", invalid format |

### 1.2 Integration Tests (15%)

Location: `tests/integration/`

These test module interactions with minimal mocking:

| Test | What It Validates |
|---|---|
| `test_camera_to_landmarks.py` | Process A writes SharedMemory -> Process B reads -> MediaPipe extracts -> Hand dataclass produced |
| `test_filter_to_features.py` | Raw landmarks -> One-Euro -> FeatureVector. Verify smoothing reduces noise by >50% |
| `test_features_to_fsm.py` | FeatureVector sequence -> FSM -> GestureEvent. Test all 3 MVP gestures end-to-end |
| `test_event_bus_dispatch.py` | GestureEvent -> EventBus -> ActionDispatcher -> BaseController mock. Verify correct method called |
| `test_config_hot_reload.py` | Modify YAML on disk -> ConfigManager detects -> EventBus emits ConfigurationChanged -> subscribers update |
| `test_plugin_discovery.py` | Drop .py file in plugins/ -> PluginLoader discovers -> schema validates -> gesture appears in engine |

### 1.3 Property-Based & Replay Tests (20%)

**Hypothesis tests** (`tests/unit/test_properties_*.py`):
- `test_one_euro_monotonic_convergence`: For any input sequence, filtered output converges to input (no drift)
- `test_feature_invariance`: FeatureVector is identical for same pose at different positions/scales (translate, scale, rotate landmark sets)
- `test_fsm_never_single_frame_trigger`: No GestureEvent produced from any single-frame FeatureVector
- `test_dwt_symmetry`: dtw(a, b) == dtw(b, a) for random landmark sequences

**Replay tests** (`tests/replay/`):
- Landmark sequences recorded from real hand motions, stored as JSON in `tests/replay/fixtures/`
- Each fixture: `{"frames": [[{x,y,z}, ...], ...], "expected_gesture": "MinimizeWindow", "hand": "Left"}`
- Test replays sequence through FSM, asserts correct GestureEvent at correct frame index
- Fixtures needed (minimum):
  - `minimize_window_success.json` - 3 examples of correct minimize gesture
  - `minimize_window_abort.json` - 2 examples of interrupted gestures (arm moves)
  - `switch_window_success.json` - 3 examples
  - `scroll_up_down.json` - 2 examples (up and down)
  - `random_idle_motion.json` - 1-hour-equivalent compressed sequence, must produce 0 GestureEvents
  - `false_positive_kitchen_sink.json` - Waving, typing motions, face touching - must produce 0 GestureEvents

### 1.4 End-to-End Tests (5%)

Run only in nightly CI and manual QA:
- Full pipeline: real webcam -> real MediaPipe -> real FSM -> real OS action
- Requires: physical webcam, monitor, human or robot hand
- Automated via pre-recorded video files played as virtual camera (v4l2loopback on Linux, OBS virtual cam on Windows/Mac)
- Test cases:
  1. Play minimize gesture video -> verify window minimizes within 1s
  2. Play switch gesture video -> verify foreground window changes
  3. Play scroll video -> verify scroll events received
  4. Play 10-min idle video -> verify 0 false triggers
  5. Play video with lighting change -> verify graceful handling
  6. Disconnect/reconnect camera mid-stream -> verify auto-recovery

---

## 2. Test Fixtures

### 2.1 Mock Landmark Generator (`conftest.py`)

```python
import numpy as np
import pytest

def make_hand(landmarks):
    """Create a Hand dataclass from list of (x,y,z) tuples."""
    from models.data_types import Hand, Landmark3D
    lms = [Landmark3D(x=x, y=y, z=z) for x, y, z in landmarks]
    return Hand(landmarks=lms, handedness="Right", confidence=1.0)

@pytest.fixture
def open_palm_hand():
    """Hand with all 5 fingers extended, facing camera."""
    coords = [
        (0.5, 0.8, 0.0),   # 0: WRIST
        (0.45, 0.65, 0.0),  # 1: THUMB_CMC
        (0.4, 0.5, 0.0),    # 2: THUMB_MCP
        (0.37, 0.4, 0.0),   # 3: THUMB_IP
        (0.35, 0.3, 0.0),   # 4: THUMB_TIP
        (0.42, 0.55, 0.0),  # 5: INDEX_MCP
        (0.4, 0.4, 0.0),    # 6: INDEX_PIP
        (0.39, 0.3, 0.0),   # 7: INDEX_DIP
        (0.38, 0.22, 0.0),  # 8: INDEX_TIP
        (0.5, 0.53, 0.0),   # 9: MIDDLE_MCP
        (0.5, 0.38, 0.0),   # 10: MIDDLE_PIP
        (0.5, 0.28, 0.0),   # 11: MIDDLE_DIP
        (0.5, 0.2, 0.0),    # 12: MIDDLE_TIP
        (0.57, 0.55, 0.0),  # 13: RING_MCP
        (0.58, 0.42, 0.0),  # 14: RING_PIP
        (0.58, 0.33, 0.0),  # 15: RING_DIP
        (0.58, 0.26, 0.0),  # 16: RING_TIP
        (0.63, 0.58, 0.0),  # 17: PINKY_MCP
        (0.64, 0.47, 0.0),  # 18: PINKY_PIP
        (0.64, 0.39, 0.0),  # 19: PINKY_DIP
        (0.65, 0.33, 0.0),  # 20: PINKY_TIP
    ]
    return make_hand(coords)

@pytest.fixture
def pointing_hand():
    """Index finger extended, all others curled."""
    coords = [
        (0.5, 0.8, 0.0),   # 0: WRIST
        (0.45, 0.65, -0.02), # 1: THUMB_CMC (curled back)
        (0.47, 0.7, -0.01),  # 2: THUMB_MCP
        (0.48, 0.73, -0.01), # 3: THUMB_IP
        (0.47, 0.7, -0.01),  # 4: THUMB_TIP (curled)
        (0.44, 0.6, 0.0),   # 5: INDEX_MCP
        (0.43, 0.45, 0.0),  # 6: INDEX_PIP
        (0.42, 0.33, 0.0),  # 7: INDEX_DIP
        (0.41, 0.22, 0.0),  # 8: INDEX_TIP (extended)
        (0.5, 0.62, 0.0),   # 9: MIDDLE_MCP
        (0.51, 0.68, 0.0),  # 10: MIDDLE_PIP (curled)
        (0.51, 0.72, 0.0),  # 11: MIDDLE_DIP
        (0.50, 0.7, 0.0),   # 12: MIDDLE_TIP
        (0.55, 0.63, 0.0),  # 13: RING_MCP
        (0.56, 0.68, 0.0),  # 14: RING_PIP (curled)
        (0.56, 0.72, 0.0),  # 15: RING_DIP
        (0.55, 0.7, 0.0),   # 16: RING_TIP
        (0.59, 0.64, 0.0),  # 17: PINKY_MCP
        (0.60, 0.68, 0.0),  # 18: PINKY_PIP (curled)
        (0.60, 0.71, 0.0),  # 19: PINKY_DIP
        (0.59, 0.69, 0.0),  # 20: PINKY_TIP
    ]
    return make_hand(coords)

@pytest.fixture
def fist_hand():
    """All fingers curled (closed fist)."""
    coords = [
        (0.5, 0.8, 0.0),
        (0.45, 0.68, -0.03), (0.47, 0.72, -0.02), (0.48, 0.74, -0.02), (0.47, 0.72, -0.02),
        (0.46, 0.68, 0.0), (0.47, 0.72, 0.0), (0.47, 0.74, 0.0), (0.46, 0.72, 0.0),
        (0.50, 0.68, 0.0), (0.50, 0.72, 0.0), (0.50, 0.74, 0.0), (0.50, 0.72, 0.0),
        (0.53, 0.68, 0.0), (0.54, 0.72, 0.0), (0.54, 0.74, 0.0), (0.53, 0.72, 0.0),
        (0.56, 0.69, 0.0), (0.57, 0.72, 0.0), (0.57, 0.74, 0.0), (0.56, 0.72, 0.0),
    ]
    return make_hand(coords)

@pytest.fixture
def pinch_hand():
    """Thumb and index tips close together, others extended."""
    coords = [
        (0.5, 0.8, 0.0),
        (0.45, 0.65, -0.02), (0.42, 0.5, -0.02), (0.40, 0.38, -0.02), (0.39, 0.32, -0.02),
        (0.44, 0.6, 0.0), (0.42, 0.45, 0.0), (0.41, 0.35, 0.0), (0.40, 0.32, 0.0),  # index tip near thumb tip
        (0.5, 0.58, 0.0), (0.5, 0.43, 0.0), (0.5, 0.32, 0.0), (0.5, 0.24, 0.0),
        (0.56, 0.59, 0.0), (0.57, 0.46, 0.0), (0.57, 0.36, 0.0), (0.57, 0.28, 0.0),
        (0.60, 0.61, 0.0), (0.61, 0.50, 0.0), (0.61, 0.42, 0.0), (0.61, 0.36, 0.0),
    ]
    return make_hand(coords)

@pytest.fixture
def thumbs_up_hand():
    """Thumb extended up, all others curled."""
    coords = [
        (0.5, 0.8, 0.0),
        (0.42, 0.65, -0.04), (0.35, 0.50, -0.04), (0.30, 0.38, -0.04), (0.27, 0.28, -0.04),  # thumb extended
        (0.46, 0.68, 0.0), (0.47, 0.72, 0.0), (0.47, 0.74, 0.0), (0.46, 0.72, 0.0),
        (0.50, 0.68, 0.0), (0.50, 0.72, 0.0), (0.50, 0.74, 0.0), (0.50, 0.72, 0.0),
        (0.53, 0.68, 0.0), (0.54, 0.72, 0.0), (0.54, 0.74, 0.0), (0.53, 0.72, 0.0),
        (0.56, 0.69, 0.0), (0.57, 0.72, 0.0), (0.57, 0.74, 0.0), (0.56, 0.72, 0.0),
    ]
    return make_hand(coords)

@pytest.fixture
def landmark_sequence_pointing_then_flick():
    """30 frames: 10 pointing, 10 rapid down flick, 10 idle."""
    frames = []
    for i in range(10):
        frames.append(pointing_hand())
    for i in range(10):
        hand = pointing_hand()
        hand.landmarks[8].y += (i * 0.02)  # shift index tip down
        frames.append(hand)
    for i in range(10):
        frames.append(fist_hand())
    return frames
```

### 2.2 SharedMemory Test Helper

```python
@pytest.fixture
def shared_memory_frame():
    from multiprocessing import shared_memory
    import numpy as np
    shm = shared_memory.SharedMemory(create=True, size=640*480*3)
    frame = np.zeros((480, 640, 3), dtype=np.uint8, buffer=shm.buf)
    yield shm, frame
    shm.close()
    shm.unlink()
```

---

## 3. Performance Benchmark Tests

Location: `tests/benchmarks/`
Run with: `pytest tests/benchmarks/ --benchmark-only`
Requires: `pytest-benchmark`

| Benchmark | Target | Measurement |
|---|---|---|
| `bench_camera_capture.py` | < 5ms per frame | Time from read() to SharedMemory write |
| `bench_landmark_extraction.py` | < 10ms per frame | Time from SharedMemory read to list[Hand] |
| `bench_one_euro_filter.py` | < 0.5ms per hand | Time to filter 21 landmarks x 3 axes |
| `bench_feature_engineering.py` | < 0.5ms per hand | Time from smoothed landmarks to FeatureVector |
| `bench_fsm_evaluation.py` | < 0.5ms for all FSMs | Time to evaluate all registered gesture FSMs |
| `bench_full_pipeline.py` | < 20ms total | SharedMemory read -> landmarks -> filter -> features -> FSM -> event |
| `bench_dtw_matching.py` | < 5ms per template | Time to compare 60-frame buffer against 1 template |
| `bench_memory_allocation.py` | 0 net growth over 10k frames | tracemalloc snapshot diff |

---

## 4. CI Test Pipeline

### 4.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: black --check gesture_controller/
      - run: flake8 gesture_controller/
      - run: mypy gesture_controller/ --strict

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit/ -v --cov=gesture_controller --cov-report=xml
      - run: pytest tests/unit/ --cov-fail-under=80

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/integration/ -v

  benchmarks:
    runs-on: ubuntu-latest
    needs: integration-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/benchmarks/ --benchmark-only --benchmark-json=bench_results.json
      - name: Check regression
        run: |
          python scripts/check_bench_regression.py \
            --current bench_results.json \
            --baseline .benchmarks/baseline.json \
            --threshold 1.10

  replay-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/replay/ -v

  nightly-e2e:
    runs-on: self-hosted
    if: github.event_name == 'schedule'
    triggers:
      - cron: '0 3 * * *'
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/e2e/ -v --timeout=600
```

### 4.2 Quality Gates

| Gate | Threshold | CI Job | Action on Fail |
|---|---|---|---|
| Lint | 0 errors, 0 warnings | lint | Block merge |
| Type check | 0 mypy errors | lint | Block merge |
| Unit coverage | >= 80% | unit-tests | Block merge |
| Integration | All pass | integration-tests | Block merge |
| Benchmark regression | < 10% slowdown | benchmarks | Warn, comment on PR |
| Replay accuracy | 100% of fixtures pass | replay-tests | Block merge |
| Memory leak | < 1KB growth / 1000 frames | benchmarks | Block merge |

---

## 5. Test Data Requirements

### 5.1 Landmark Fixture Files

Create these in `tests/replay/fixtures/`:

```
fixtures/
  minimize_window_success_1.json
  minimize_window_success_2.json
  minimize_window_success_3.json
  minimize_window_abort_arm_move.json
  minimize_window_abort_finger_extend.json
  switch_window_success_1.json
  switch_window_success_2.json
  switch_window_success_3.json
  scroll_up.json
  scroll_down.json
  idle_1hour_compressed.json
  false_positive_waving.json
  false_positive_face_touch.json
  false_positive_typing_motion.json
  lighting_change_transition.json
```

### 5.2 Fixture JSON Schema

```json
{
  "type": "object",
  "required": ["version", "fps", "hands", "expected_gestures"],
  "properties": {
    "version": {"type": "string", "const": "1.0"},
    "fps": {"type": "integer", "minimum": 15, "maximum": 60},
    "hands": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["handedness", "frames"],
        "properties": {
          "handedness": {"type": "string", "enum": ["Left", "Right"]},
          "frames": {
            "type": "array",
            "items": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["x", "y", "z"],
                "properties": {
                  "x": {"type": "number", "minimum": 0, "maximum": 1},
                  "y": {"type": "number", "minimum": 0, "maximum": 1},
                  "z": {"type": "number"}
                }
              },
              "minItems": 21, "maxItems": 21
            }
          }
        }
      }
    },
    "expected_gestures": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["gesture_name", "trigger_frame"],
        "properties": {
          "gesture_name": {"type": "string"},
          "trigger_frame": {"type": "integer", "minimum": 0},
          "tolerance_frames": {"type": "integer", "default": 5}
        }
      }
    }
  }
}
```

---

## 6. Debugging Guide for Test Failures

### FSM Test Fails - Gesture Not Recognized
1. Print the FeatureVector at each frame in the failing sequence
2. Check which FSM state the gesture gets stuck in
3. Verify the condition expression evaluates as expected (check AST parser output)
4. Common causes: threshold too tight, min_duration not met, abort condition triggered

### Filter Test Fails - Output Drifts
1. Check for NaN/inf in input (filter cannot recover from these)
2. Verify derivate_cutoff > 0 (division by zero otherwise)
3. Check that timestamps are monotonically increasing

### Integration Test Fails - SharedMemory Race
1. Add a sequence number header to the SharedMemory block for debugging
2. Verify Process A is not writing while Process B is reading (single-slot means newest wins by design, but check frame_size matches)
3. Check that SharedMemory size = 640 * 480 * 3 exactly

### Benchmark Regresses
1. Run `python -m cProfile -o profile.stats tests/benchmarks/bench_<failing>.py`
2. Use `snakeviz profile.stats` to visualize
3. Check for: new allocations in hot path, unnecessary copies, Python loops over NumPy data
4. If regression is in MediaPipe: cannot fix (external), document and adjust budget

---

## 7. Acceptance Test Checklist (Manual QA)

Before any release, a human must verify:

- [ ] App starts in < 2 seconds on target hardware
- [ ] System tray icon appears and responds to clicks
- [ ] Minimize gesture works 9/10 times in good lighting
- [ ] Switch window gesture works 9/10 times
- [ ] Scroll gesture tracks hand smoothly, no jitter
- [ ] No false triggers during 10 minutes of normal hand movement near camera
- [ ] Pause hotkey (Win+Shift+G / Cmd+Shift+G) immediately stops all gesture recognition
- [ ] Camera disconnect -> reconnect -> recognition resumes within 5 seconds
- [ ] Settings window opens, changes persist after restart
- [ ] HUD overlay shows tracking points and progress ring
- [ ] Custom gesture can be recorded and immediately tested
- [ ] App-specific profiles switch correctly when foreground app changes
- [ ] Memory stays below 200MB after 30 minutes of continuous use
- [ ] CPU stays below 10% on quad-core during continuous use
