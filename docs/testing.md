# Comprehensive Testing & Risk Mitigation Guide

This document serves as the authoritative testing guide for **Maestro**. It covers the multi-tiered test suite architecture, execution instructions, quality assurance gates, and an exhaustive breakdown of failure modes and edge case risks across diverse operating environments.

---

## 1. Executive Summary & Testing Philosophy

Maestro is a real-time, cross-platform desktop application that combines computer vision (MediaPipe/ONNX), dynamic state machines (FSM), offline voice recognition (Vosk), dynamic gesture matching (DTW), and native operating system input injection (Win32, Quartz, uinput).

To guarantee **zero regressions**, low processing latency (<30ms), and 100% strict type safety, Maestro employs a **multi-layered testing architecture**:

```
 ┌─────────────────────────────────────────────────────────┐
 │                   Automated CI Gates                    │
 │    (pytest matrix, mypy, black, bandit, workflow-lint)  │
 └────────────────────────────┬────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────┐
 │                  Testing Layers                         │
 ├─────────────────────────────────────────────────────────┤
 │ 1. Unit Tests          - Isolated component logic       │
 │ 2. Integration Tests   - Subsystem interaction & GUI    │
 │ 3. Replay Tests        - Deterministic landmark series  │
 │ 4. Benchmark Tests     - Latency & throughput profiling │
 │ 5. Fuzzing & Property  - AST safety & boundary values   │
 └─────────────────────────────────────────────────────────┘
```

---

## 2. Test Suite Architecture

The test suite is located in `gesture_controller/tests/` and structured into distinct categories:

### 2.1 Unit Tests (`gesture_controller/tests/unit/`)
Focuses on pure logic in isolation with external dependencies mocked out:
- **`test_state_machine.py`**: Validates Finite State Machine (FSM) state transitions, cooldown timers, and gesture triggers.
- **`test_one_euro_filter.py`**: Verifies dynamic jitter suppression filtering across low and high movement velocities.
- **`test_dtw_matcher.py`**: Tests Dynamic Time Warping distance computation and multi-frame gesture pattern matching.
- **`test_expression_evaluator.py`**: Validates restricted AST expression parsing for custom gesture conditions.
- **`test_config_manager.py`**: Tests JSON configuration serialization, schema validation, and default fallback handling.
- **`test_signal_handler.py`**: Verifies SIGINT/SIGTERM graceful shutdown hooks and thread safety.

### 2.2 Integration Tests (`gesture_controller/tests/integration/`)
Validates multi-component interaction:
- **`test_full_pipeline.py`**: Tests end-to-end processing from raw frame inputs to OS action dispatching.
- **`test_camera_to_landmarks.py`**: Verifies frame acquisition, double-buffering, and landmark extraction.
- **`test_gui_integration.py`**: Tests PyQt6 settings window, HUD overlay rendering, and onboarding wizard interactions.
- **`test_plugin_lifecycle.py`**: Verifies plugin loading, WASM sandboxing, and runtime registration.

### 2.3 Replay Tests (`gesture_controller/tests/replay/`)
Executes deterministic regression testing against recorded landmark sequences stored in `gesture_controller/tests/replay/fixtures/`:
- **`pinch.json`**: Verifies click/pinch gesture recognition.
- **`scroll.json`**: Tests continuous vertical/horizontal scrolling accuracy.
- **`swipe.json`**: Tests fast directional swipe gesture triggers.
- **`minimize.json`**: Tests complex multi-finger hand gestures.

### 2.4 Benchmark Tests (`gesture_controller/tests/benchmarks/`)
Monitors performance budgets using `pytest-benchmark`:
- **`test_bench_dtw`**: Micro-benchmarks DTW distance matrix computation.
- **`test_bench_one_euro`**: Measures One-Euro filter iteration latency (<15µs target).
- **`test_bench_fsm`**: Measures state machine evaluation overhead (<25µs target).
- **`test_bench_full_pipeline`**: Measures total frame processing loop time (<33ms target).

### 2.5 Fuzzing & Security Tests (`gesture_controller/tests/fuzz/` & `test_config_ast_safety.py`)
- Tests restricted AST expression parser against random bytecode, malicious strings, and invalid syntax to ensure arbitrary code execution is strictly impossible.

---

## 3. Comprehensive Failure Modes & Risk Analysis

The following matrix documents potential failure conditions across hardware, OS platforms, vision pipelines, and concurrency models, along with Maestro's built-in resilience mechanisms.

| Category | Potential Failure / Breakage Condition | System Impact | Built-in Mitigation & Resilience Strategy |
|---|---|---|---|
| **Vision & Lighting** | Extreme low light, heavy backlighting, or severe camera motion blur. | Hand landmarks fail detection or produce erratic coordinates (jitter). | **Adaptive One-Euro Filter** dynamically adjusts cutoff frequencies based on velocity; low-confidence frames are discarded. |
| **Vision Pipeline** | Multiple hands in camera frame or hand partially occluded by objects. | Confusion over primary hand ID; false positive gesture triggers. | **Palm Detector & Hand Topology Filter** selects highest-confidence single hand and enforces anatomical joint constraints. |
| **Resource Starvation** | High CPU saturation or low-end hardware (e.g. dual-core CPU without dedicated GPU). | Inference frame rate drops below 30 FPS; processing delay accumulates. | **Adaptive Performance Tier Manager** automatically downgrades backend (Tier 1 GPU → Tier 2 CPU → Tier 3 Low-FPS) to preserve system responsiveness. |
| **Camera Hardware** | Camera unplugged during active session or occupied by another app. | OpenCv `VideoCapture` read fails or returns empty frames. | **Camera Watchdog Thread** monitors frame timestamp delta; auto-reconnects with exponential backoff if stream drops. |
| **Windows OS** | Application running under standard user while target app is Elevated (Admin). | UIPI (User Interface Privilege Isolation) blocks `SendInput` mouse/keyboard events. | **Input Injection Broker** (`broker.py`) runs as an isolated, privileged IPC service to route injected inputs safely. |
| **macOS Privacy** | Accessibility or Input Monitoring permissions revoked by user in System Settings. | `Quartz.CGEvent` creation fails silently or raises permission errors. | **Pre-flight Permission Check** detects missing Quartz rights and prompts user with guided macOS System Settings deep-links. |
| **Linux Display** | Wayland display server active without legacy XTest/uinput permissions. | Direct X11 event injection fails; `/dev/uinput` raises `PermissionError`. | **Linux Controller Fallback** routes input via `uinput` daemon socket or D-Bus media interface (`mpris_media.py`). |
| **Voice Subsystem** | Microphone disconnected, PyAudio stream failure, or missing Vosk speech model. | Voice listener thread crashes or hangs waiting for audio buffer. | **Offline Vosk Isolator** runs voice recognition on a dedicated worker thread with non-blocking stream reads and model existence checks. |
| **Custom Expressions** | User enters invalid or malicious condition string (e.g., `__import__('os').system('dir')`). | Potential security vulnerability or evaluation crash. | **Restricted AST Parser** (`expression_evaluator.py`) evaluates expressions against an allowed whitelist of math ops and variables only. |
| **Thread & Signals** | User closes terminal window sending `SIGINT` / `SIGTERM` while camera thread active. | Subprocesses left orphaned (zombies); camera lock held. | **SignalHandler** catches `SIGINT`/`SIGTERM` and executes graceful multi-stage teardown before process exit. |

---

## 4. Test Execution Guide

### 4.1 Running All Local Tests

To run the complete test suite with coverage:
```bash
python -m pytest --cov=gesture_controller
```

### 4.2 Running Specific Test Categories

Run only unit tests:
```bash
python -m pytest gesture_controller/tests/unit
```

Run integration tests:
```bash
python -m pytest gesture_controller/tests/integration
```

Run replay tests:
```bash
python -m pytest gesture_controller/tests/replay
```

Run performance benchmarks:
```bash
python -m pytest gesture_controller/tests/benchmarks --benchmark-only
```

### 4.3 Running Quality & Type Checkers

Run `mypy` strict type checker:
```bash
python -m mypy --config-file pyproject.toml gesture_controller/
```

Run `black` code formatter check:
```bash
python -m black --check gesture_controller/
```

Run `bandit` security scanner:
```bash
python -m bandit -r gesture_controller/ -x gesture_controller/tests/ -ll
```

---

## 5. CI/CD Automated Quality Gates

Every commit pushed to `main` triggers the GitHub Actions CI pipeline defined in `.github/workflows/ci.yml`.

### Matrix Coverage
- **Operating Systems**: `windows-latest`, `ubuntu-latest`, `macos-latest`
- **Python Versions**: `3.11`, `3.12`, `3.13`

### Enforced Quality Gates
1. **Workflow Lint**: Validates GitHub Actions YAML syntax.
2. **Lint & Typecheck**: Enforces `mypy` zero-error requirement across all source files.
3. **Security Scan**: Executes `bandit` to block potential security regressions.
4. **Multi-Platform Test Matrix**: Executes 550+ tests headlessly across all 9 OS/Python matrix combinations (`QT_QPA_PLATFORM=offscreen`).
