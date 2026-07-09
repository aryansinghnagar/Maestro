# Implementation Plan: Cross-Platform Hand-Gesture Desktop Controller

This implementation plan details the setup and execution path for building a production-grade, low-latency, cross-platform hand-gesture desktop controller.

## User Review Required

> [!IMPORTANT]
> The project utilizes a **multiprocessing architecture** separating the video capture process from the gesture recognition and application dispatching engine. A single-slot shared memory buffer (`multiprocessing.shared_memory.SharedMemory`) is used to exchange frame data with zero backlog and minimal latency, bypassing the Python GIL.

> [!IMPORTANT]
> **PyQt6** is used for UI components (system tray icon, translucent HUD, and settings panel) instead of Electron to ensure native styling, system integration, and low memory overhead (<150MB target).

> [!WARNING]
> **Platform-Specific OS Permissions:**
> - Windows: Will use `pyautogui` initially, abstracting calls so we can drop in low-level `SendInput` ctypes later.
> - macOS: Needs Accessibility API permissions (`AXIsProcessTrusted`) and Camera permissions.
> - Linux: Requires `/dev/uinput` write access via `evdev`. A setup script will configure the necessary `udev` rules to run the daemon without root.

## Open Questions

- No open questions exist at this stage. The requirements are fully detailed in [master_development_plan.md](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/master_development_plan.md) and associated specifications. We will follow the defined plan strictly.

## Proposed Changes

We will set up the workspace under the `gesture_controller` directory with the following components. All files are listed below as new files.

---

### Repository Infrastructure & Packaging

#### [NEW] [pyproject.toml](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/pyproject.toml)
Defines project metadata, build configurations, dependencies, and formatting settings.

#### [NEW] [requirements.txt](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/requirements.txt)
Lists all production requirements (MediaPipe, OpenCV, PyQt6, NumPy, etc.).

#### [NEW] [setup.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/setup.py)
Minimal project configuration script delegating to `pyproject.toml`.

#### [NEW] [main.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/main.py)
The daemon process entry point that initializes logging, loads configurations, and spawns the orchestration engine.

---

### Core Daemon & Orchestration

#### [NEW] [engine.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/engine.py)
Coordinates processes, processes hand landmarks from SharedMemory, runs the pipeline, and handles shutdowns.

#### [NEW] [event_bus.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/event_bus.py)
In-process event broker managing system event pub/sub.

#### [NEW] [config_manager.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/config_manager.py)
Loads YAML configurations, validates schemas, and implements safe AST walkers for conditions.

#### [NEW] [state_machine.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/state_machine.py)
FSM parser that tracks gesture progress (Idle -> Candidate -> Validation -> Trigger -> Cooldown).

---

### Vision Pipeline & Input Capture

#### [NEW] [camera_stream.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/vision/camera_stream.py)
Process A: Opens camera capture using optimized OpenCV backends and writes frame bytes directly to SharedMemory.

#### [NEW] [landmark_extractor.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/vision/landmark_extractor.py)
Initializes MediaPipe Hands in streaming mode, consuming frames from SharedMemory and mapping output to project datatypes.

#### [NEW] [one_euro_filter.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/vision/one_euro_filter.py)
Suppresses noise in raw landmarks using a speed-adaptive One-Euro Filter.

---

### Mathematical Data Models

#### [NEW] [data_types.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/models/data_types.py)
Predefines all structured coordinate types, landmark configurations, and gesture event definitions.

#### [NEW] [feature_engineering.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/models/feature_engineering.py)
Translates 21 keypoints into translation-, scale-, and rotation-invariant features.

#### [NEW] [dtw_matcher.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/models/dtw_matcher.py)
Provides sub-millisecond dynamic time warping alignments using Numba compilation for user custom gestures.

---

### OS Integration adapters

#### [NEW] [base_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/base_controller.py)
Abstract base interface class for executing operating system actions.

#### [NEW] [windows_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/windows_controller.py)
Injects keys/clicks on Windows and tracks the foreground active process.

#### [NEW] [macos_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/macos_controller.py)
Uses PyObjC / Quartz CoreGraphics APIs for OS inputs and Accessibility interfaces for window tracking.

#### [NEW] [linux_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/linux_controller.py)
Uses `/dev/uinput` via `evdev` to bypass Wayland application isolation.

#### [NEW] [action_dispatcher.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/action_dispatcher.py)
Dispatches gesture events using active application profiles.

---

### GUI and User Experience

#### [NEW] [tray_icon.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/tray_icon.py)
PyQt6 implementation of the background daemon tray menu controls.

#### [NEW] [overlay.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/overlay.py)
Provides on-screen head-up feedback with custom painter loops mapping active index points.

#### [NEW] [gesture_recorder.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/gesture_recorder.py)
GUI panel helping users record custom dynamic gesture templates.

#### [NEW] [settings_window.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/settings_window.py)
Panel editor containing config adjustment widgets.

#### [NEW] [app_entry.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/app_entry.py)
Orchestrates PyQt UI threads and background loops.

---

## Verification Plan

### Automated Tests
Run unit tests, integration tests, and benchmarks using the following commands:
```powershell
# Run the unit tests
pytest tests/unit/

# Run the integration tests
pytest tests/integration/

# Run performance benchmarks
pytest tests/benchmarks/ --benchmark-only

# Run gesture replay tests
pytest tests/replay/
```

### Manual Verification
1. Verify camera watchdog timeout and reconnection sequence by pulling the camera cable.
2. Toggle global safety shortcuts and ensure no incidental hand motions fire system events.
3. Validate Chrome and PowerPoint app-specific profiles by confirming gestures fire different shortcut triggers based on the active window.
4. Verify tracking overlays follow coordinates smoothly with no visual latency.

---

## Master Development Plan (Verbatim)

Unified Development Plan: Cross-Platform Hand-Gesture Desktop Controller

Version: 1.0 | Date: 2026-06-29 | Status: Authoritative Development Guide  
Synthesized from: vision.txt, plan.md, research.md, implementation_plan.md, sys_prompt_1.txt, sys_prompt_2.txt, sys_prompt_3.txt

---

## Table of Contents

1. Executive Summary
2. Mission and Success Criteria
3. System Architecture (Resolved)
4. Technology Stack
5. Canonical Directory Structure
6. Data Flow Pipeline
7. Performance Budgets and KPIs
8. Gesture Specification
9. Configuration Reference
10. Development Timeline
11. Error Handling and Edge Cases
12. Installation and Onboarding UX
13. Performance Profiling Strategy
14. Accessibility and Internationalization
15. Testing Strategy
16. CI/CD Pipeline
17. Security and Privacy
18. Deployment and Packaging
19. Architecture Decision Records
20. Risk Register

---

## 1. Executive Summary

This document is the single, authoritative development guide for building a production-grade, cross-platform, low-latency hand-gesture desktop controller. It synthesizes and resolves all prior planning documents, research, system prompts, and architectural blueprints into one actionable plan with daily-level task breakdowns.

The application transforms a standard RGB webcam into a real-time operating system input device. It captures hand landmarks via Google MediaPipe, smooths them with a vectorized One-Euro Filter, engineers invariant features from the 21-joint skeleton, and feeds them into deterministic Finite State Machines that recognize gestures and dispatch OS commands. The system runs as a background daemon with a system tray icon, a translucent HUD overlay for visual feedback, and a settings/recorder GUI built with PyQt6.

What differentiates this from competitors (MediaPipe Gesture Recognizer, Spatial Touch, Gerik, Gestro, MacGesture, Leap Motion):

- Deterministic FSM-based recognition with structural Midas-Touch resistance, not frame-by-frame classification
- Shared-memory multiprocessing architecture that bypasses both the Python GIL and network-stack IPC (Gerik's critical design flaw)
- Plugin ecosystem for gestures and actions with hot-reload capability
- App-specific gesture profiles so the same gesture maps to different actions per application
- Cross-platform OS abstraction over Windows, macOS, and Linux (Wayland/X11) behind a clean ABC
- Sub-20ms end-to-end latency target on a quad-core CPU without any GPU requirement
- Privacy-first design: zero cloud inference, zero raw frame persistence, zero telemetry by default
- Comprehensive testing with landmark replay fixtures, performance gating in CI, and 1000-hour stability target

Key additions beyond prior documents: This plan expands into areas the source files glossed over or missed entirely: comprehensive error handling and edge cases for camera permissions, multi-monitor setups, high-DPI scaling, and OS permission dialogs; first-run installation and onboarding UX flows with permission wizards; a performance profiling strategy with specific tools (py-spy, cProfile, tracemalloc) and checkpoints at each milestone; and accessibility/internationalization requirements covering screen readers, keyboard navigation, left/right hand modes, and multi-language UI strings.

---

## 2. Mission and Success Criteria

Mission: Let a user control their desktop (window management, scrolling, media, and custom actions) using only a standard RGB webcam and bare hands, with sub-30ms reaction time, near-zero accidental triggers, and zero impact on privacy.

Priority ordering (order matters):
1. Correctness
2. Reliability
3. Determinism
4. Low latency
5. False-positive reduction
6. Maintainability
7. Extensibility
8. Readability
9. Performance optimization
10. Developer experience

Never sacrifice correctness for speed. Never sacrifice architecture for short-term convenience. Never introduce technical debt when an extensible solution is practical.

The project is successful only if it becomes:
- A reference-quality implementation of webcam-based gesture control
- Extensible enough that new gestures, actions, or vision backends can be added without modifying the core engine
- Deterministic, low-latency, and robust enough for daily use by non-technical users
- Easier to maintain and contribute to than competing open-source alternatives
- Documented, tested, benchmarked, and architected to professional engineering standards rather than as a prototype

---

## 3. System Architecture (Resolved)

### 3.1 Conflict Resolutions

The source documents contained conflicting guidance. The following resolutions are authoritative:

| Decision Area | Conflicting Sources | Resolved Approach |
|---|---|---|
| Concurrency | sys_prompt_1: 6 threads; sys_prompt_2: 3 threads; vision.txt: 3 threads | Multiprocessing: Process A (camera) isolated from Process B (inference+logic) via `multiprocessing.shared_memory.SharedMemory` single-slot buffer. Bypasses GIL entirely. |
| Frame exchange | vision.txt: queue-based; sys_prompt_2: queue size 1 | Single-slot SharedMemory. Newest frame overwrites stale data. Zero backlog, lowest latency. |
| UI framework | vision.txt: Electron/React or PyQt | PyQt6. Native tray, no Chromium overhead. Electron explicitly rejected. |
| Directory structure | vision.txt: flat core/ui/utils | implementation_plan.md modular structure (core/, vision/, models/, plugins/, os_integration/, actions/, gui/) |
| Windows input | sys_prompt_2: SendInput via ctypes; impl_plan: simpler first | Start with pyautogui. BaseController ABC allows drop-in upgrade to SendInput later. |
| Event system | Not in vision.txt; partial in sys_prompt_1 | In-process pub/sub via queue.Queue. NEVER WebSocket/network (Gerik's bug). |
| Condition parsing | Not addressed in vision.txt | AST allow-list walker. eval()/exec() on condition strings absolutely prohibited. |
| ML pipeline | vision.txt: Azure MLOps | Build-time only. ml_pipeline/ never imported at runtime. 100% on-device inference. |

### 3.2 Process Architecture

```
Process A: Camera Capture (camera_stream.py)
+------------------+    +-------------------+    +--------------------+
| OpenCV            |    | Preprocessing      |    | SharedMemory       |
| VideoCapture      |--->| (resize 640x480,   |--->| (single slot,      |
| (hw accel where    |    |  BGR->RGB, mirror) |    |  newest overwrites) |
|  available)        |    |                    |    +--------+-----------+
+------------------+    +-------------------+             |
  Watchdog: auto-reconnect on disconnect                    |
  Backend fallback: MSMF->DirectShow (Win),               |
  V4L2->USB (Linux), AVFoundation (Mac)                   |
                                                            |
============================================================|
                                                            |
Process B: Inference & Logic (engine.py)                    |
+------------------+  +------------------+  +----------+  +--------+
| Landmark          |  | One-Euro         |  | Feature  |  | FSM    |
| Extractor         |->| Filter           |->| Engineer |->| Engine |
| (MediaPipe Hands  |  | (NumPy vectorized|  | (joint   |  | (Idle->|
|  LIVE_STREAM)     |  |  dynamic cutoff)  |  | angles,  |  | Candid |
+------------------+  +------------------+  | finger   |  | ->Valid|
                                           | curl,    |  | ->Trigg|
+------------------+  +------------------+  | palm,    |  | ->Cool |
| Action            |  | Event Bus        |  | velocity) |  +---+----+
| Dispatcher       |<-| (in-process      |  +----------+      |
| (platform-specific|  |  pub/sub)        |                    |
|  BaseController)  |  +------------------+                    |
+--------+---------+                                        |
         |                                                   |
+--------v---------+  +------------------+  +--------------------+
| OS Controller      |  | Plugin Loader     |  | GUI Thread (PyQt6) |
| Windows: pyautogui |  | (hot-reload,      |  | - System tray      |
| MacOS: Quartz/AX   |  |  schema validation)|  | - Overlay HUD      |
| Linux: /dev/uinput |  +------------------+  | - Settings window   |
|--------------------+                         | - Gesture recorder  |
                                               +--------------------+
```

### 3.3 Core Architectural Principles

1. Modularity: No module depends on implementation details of another. Dependencies flow toward abstractions (ABCs/interfaces).
2. Dependency Inversion: Business logic never knows Windows APIs, macOS APIs, Linux APIs, MediaPipe internals, or GUI framework internals.
3. Freshness over completeness: Drop frames rather than increase latency. Process newest data only.
4. Landmark-first reasoning: Raw RGB images disappear immediately after landmark extraction.
5. Configurability over hardcoding: Every threshold, filter parameter, cooldown, and sensitivity is in YAML. No magic numbers.
6. Privacy by design: On-device inference only. No cloud calls at runtime. No raw frame storage. Telemetry opt-in, anonymized only.
7. Determinism: The gesture engine is fully deterministic. No random decisions. No single-frame triggers.

---

## 4. Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Type-hinted, PEP 8, black-formatted, mypy-checked |
| Vision | MediaPipe Hands | LIVE_STREAM mode, 21 3D landmarks |
| Camera | OpenCV 4.x | VideoCapture with hardware acceleration |
| Filtering | NumPy + Numba | Vectorized One-Euro, JIT-compiled DTW |
| GUI | PyQt6 | System tray, overlay, settings, recorder |
| Config | PyYAML + jsonschema | Schema validation for all YAML files |
| OS: Windows | pyautogui + ctypes | Simple start, upgrade path to SendInput |
| OS: macOS | PyObjC (Quartz) | CGEventPost, AXUIElement |
| OS: Linux | evdev | /dev/uinput for Wayland |
| Testing | pytest + pytest-cov | Unit, integration, replay, benchmark |
| Linting | flake8 + mypy + black | CI gating, no exceptions |
| Packaging | PyInstaller | .exe (NSIS), .app (DMG), deb/rpm |
| C Extensions | Cython (optional) | Only for proven hot paths via profiling |
| Logging | structlog | Structured JSON logging |

---

## 5. Canonical Directory Structure

```
gesture_controller/
├── core/
│   ├── __init__.py
│   ├── engine.py                 # Master daemon coordinator, process lifecycle
│   ├── event_bus.py              # In-process pub/sub (queue.Queue based)
│   ├── config_manager.py         # YAML config, schema validation, AST-safe conditions
│   └── state_machine.py          # FSM engine: GestureFSM, FSMState, FSMTransition
│
├── vision/
│   ├── __init__.py
│   ├── camera_stream.py          # Process A: frame capture -> SharedMemory
│   ├── landmark_extractor.py     # MediaPipe Hands wrapper, LIVE_STREAM mode
│   └── one_euro_filter.py        # NumPy-vectorized One-Euro filter
│
├── models/
│   ├── __init__.py
│   ├── data_types.py             # Hand, Finger, Joint, Landmark3D, FeatureVector
│   ├── feature_engineering.py    # Joint angles, finger curl, palm normal, velocity
│   └── dtw_matcher.py            # Numba-compiled DTW for custom gesture matching
│
├── os_integration/
│   ├── __init__.py
│   ├── base_controller.py        # ABC: key_press, mouse_click, scroll, etc.
│   ├── windows_controller.py     # Windows: pyautogui/ctypes, foreground tracking
│   ├── macos_controller.py       # macOS: Quartz.CoreGraphics, AXUIElement
│   ├── linux_controller.py # Linux: /dev/uinput via evdev, udev setup
│   └── action_dispatcher.py      # Routes GestureEvent -> controller method
│
├── plugins/
│   ├── __init__.py
│   ├── plugin_loader.py          # Dynamic discovery, hot-reload, schema validation
│   └── builtin/
│       ├── __init__.py
│       ├── media_gestures.py     # Play/Pause, Volume Up/Down, Next/Prev
│       └── window_gestures.py    # Minimize, Switch, Maximize, Close
│
├── actions/
│   ├── __init__.py
│   └── action_mapper.py          # Parses "KeyPress:Ctrl+C" -> controller.key_press()
│
├── gui/
│   ├── __init__.py
│   ├── tray_icon.py              # System tray: pause/resume, camera, status
│   ├── overlay.py                # Translucent click-through HUD
│   ├── gesture_recorder.py       # Record 3-5 custom gesture examples
│   ├── settings_window.py        # Configuration editor, profile manager
│   └── app_entry.py              # PyQt6 QApplication init, wires GUI to engine
│
├── data/
│   ├── predefined_gestures.yaml  # Default FSM gesture definitions + app profiles
│   ├── default_config.yaml       # Default configuration
│   └── custom_templates/         # User-recorded DTW templates (.json)
│       └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures, mock landmark generators
│   ├── unit/                     # Per-module unit tests
│   ├── integration/              # Cross-module integration tests
│   ├── replay/                   # Prerecorded landmark sequence tests
│   │   └── fixtures/             # JSON landmark dumps
│   └── benchmarks/               # Performance benchmark tests
│
├── ml_pipeline/                  # OFFLINE ONLY - never imported at runtime
├── adr/                          # Architecture Decision Records
├── docs/                         # architecture.md, performance.md, gesture-reference.md
├── main.py                       # Daemon entry point
├── requirements.txt
├── setup.py
├── pyproject.toml
├── coding_guidelines.md
└── CHANGELOG.md
```

---

## 6. Data Flow Pipeline

### Stage 1: Camera Capture (Process A)
- Input: USB webcam device index
- Processing: cv2.VideoCapture with hw accel. Resize 640x480, BGR to RGB, horizontal mirror.
- Output: Raw frame in SharedMemory (single slot, overwrites stale).
- Watchdog: No frame for 2s -> reconnect. Backend fallback. Log CameraDisconnected/CameraRecovered.
- Error handling: SharedMemory write failure -> skip frame. Device disappears -> reconnect with exponential backoff (100ms to 1.6s).

### Stage 2: Landmark Extraction
- Input: Raw RGB from SharedMemory
- Processing: MediaPipe Hands LIVE_STREAM. Up to 2 hands, 21 Landmark3D each.
- Output: list[Hand] with landmarks, handedness, confidence.
- Conversion: MediaPipe objects -> project Hand/Landmark3D dataclasses IMMEDIATELY. MediaPipe never leaves this module.
- Memory: Raw frame buffer released after extraction. No image data persists.

### Stage 3: One-Euro Filtering
- Input: list[Landmark3D] (raw)
- Processing: Vectorized One-Euro filter on all (x,y,z) via NumPy. Dynamic cutoff: low speed -> aggressive smoothing; high speed -> minimal lag.
- Environmental adaptation: Beta and min_cutoff scaled by lighting metric (avg pixel intensity of bounding box) and depth metric (wrist-to-MCP distance).
- Output: list[Landmark3D] (smoothed) with velocity and acceleration attached.

### Stage 4: Feature Engineering
- Input: Smoothed landmarks with velocity/acceleration
- Processing: Origin alignment (wrist), depth scaling (MCP bone length), joint angles (bone vector dot products), finger curl, finger spread, palm normal, palm orientation (quaternion), hand openness, pinch distance, velocities, accelerations, handedness mirroring.
- Output: FeatureVector dataclass.

### Stage 5: FSM Gesture Engine
- Input: FeatureVector per frame per hand
- Processing: All gesture FSMs evaluate in parallel. States: Idle -> Candidate -> Validation -> Confirmed -> Triggered -> Cooldown -> Idle.
- Transitions require: min confidence, min duration, timeout, velocity constraints, orientation constraints, hysteresis, rejection conditions, cooldown.
- Priority: Highest confidence, then predefined order, then most recently armed.
- Output: GestureEvent or None.

### Stage 6: Event Bus
- Input: GestureEvent, CameraDisconnected, ConfigurationChanged, etc.
- Processing: In-process pub/sub. Subscribers: ActionDispatcher, OverlayHUD, TrayIcon, logger.
- No module directly calls another. All inter-module communication through event bus.

### Stage 7: Action Dispatcher
- Input: GestureEvent + active window process name
- Processing: Query foreground app -> check app-specific profile -> parse action string -> call BaseController method.
- Output: OS command executed.

### Stage 8: OS Backend
- Windows: WindowsController (pyautogui -> SendInput upgrade path). Foreground tracking via win32gui.
- macOS: MacOSController (CGEventPost, AXUIElement).
- Linux: LinuxController (/dev/uinput via evdev, udev rules for non-root).

---

## 7. Performance Budgets and KPIs

### 7.1 Per-Stage Latency Budget

| Stage | Budget (worst case) | Notes |
|---|---|---|
| Camera capture | < 5 ms | USB3 at 60fps; ~10ms if 30fps |
| Preprocessing | < 1 ms | OpenCV; regression is a code smell |
| Hand detection | < 10 ms | MediaPipe BlazePalm |
| Landmark estimation | < 10 ms | May overlap with detection in tracking |
| Filtering + features | < 1 ms | One-Euro + geometry math |
| FSM evaluation | < 1 ms | Dozens of comparisons |
| Action dispatch | < 2 ms | Key/mouse event injection |
| Total | < 20 ms | Target >= 50 FPS sustained |

### 7.2 Top-Level KPIs (Acceptance Gates)

| KPI | Target | Verification |
|---|---|---|
| Gesture accuracy | >= 95% precision & recall | Labeled validation set, confusion matrix |
| False positives | <= 1 per hour, idle | 1-hour random-motion replay test |
| Frame rate | >= 30 FPS sustained | Pipeline timing on target hardware |
| End-to-end latency | <= 20ms mean, <= 50ms p95 | Per-stage profiling, summed |
| CPU usage | <= 10% quad-core | 30-min continuous monitoring |
| Memory | <= 200 MB RSS | Heap profiling, leak check |
| Startup | <= 2 seconds | Launch to ready-to-recognize |
| Stability | 0 crashes / 1000 hours | Long-running stress/soak test |

### 7.3 Resource Management Rules

- Avoid allocations inside frame loops. Pre-allocate and reuse buffers.
- Pool objects (landmark arrays, feature vectors). Never create per-frame objects if avoidable.
- Use contiguous NumPy arrays (C-order). Avoid Python lists in hot paths.
- Profile allocations with tracemalloc at each milestone gate.
- If a PR regresses any KPI beyond 10%, CI must fail or flag.

---

## 8. Gesture Specification

### 8.1 MVP Gesture Vocabulary (ship in priority order)

Priority 1: Minimize Active Window (Dynamic)
- Trigger: Index finger pointing up, then rapidly flicked down
- FSM: Idle -> PointingUp (index extended, others curled, >=200ms) -> RapidDownFlick (index tip Y delta > threshold within 300ms, palm stable) -> Trigger -> Cooldown (1000ms)
- Default action: OS:MinimizeActiveWindow
- Abort: Palm moves > threshold (arm moving, not finger), other fingers extend

Priority 2: Switch Active Window (Dynamic)
- Trigger: Open hand swipes horizontally
- FSM: Idle -> HandOpen (all fingers extended, >=150ms) -> HorizontalSwipe (palm X delta > threshold within 400ms, Z stable) -> Trigger -> Cooldown (800ms)
- Default action: OS:SwitchWindow
- Abort: Hand closes during swipe, vertical exceeds horizontal

Priority 3: Scroll Up/Down (Continuous)
- Trigger: Index pointing at screen, hand moves vertically
- FSM: Idle -> PointingForward (index extended, Z decreases, >=200ms) -> ScrollingActive (palm Y delta -> scroll delta continuously) -> Release (hand retracts or 5s timeout) -> Cooldown (200ms)
- Default action: MouseScroll:delta (proportional)
- Abort: Multiple fingers extend, hand rotates

### 8.2 Secondary Gestures (post-MVP)

Static:
| Gesture | Condition | Action | Cooldown |
|---|---|---|---|
| Thumbs Up | Thumb extended, others curled, >=200ms | Media:PlayPause | 1000ms |
| Open Palm | All fingers extended, >=300ms | OS:ShowDesktop | 1500ms |
| Pinch | Thumb-index dist < threshold, >=150ms | MouseClick:Left | 500ms |
| Peace Sign | Index+middle extended, others curled, >=200ms | Configurable | 800ms |

Dynamic:
| Gesture | Pattern | Action | Cooldown |
|---|---|---|---|
| Swipe Left | Open hand moves left | KeyPress:ArrowLeft (profile-dependent) | 300ms |
| Swipe Right | Open hand moves right | KeyPress:ArrowRight (profile-dependent) | 300ms |

Multi-Hand (stretch): Volume Slider (left anchor, right drag), Zoom (two hands apart/together).

### 8.3 Gesture Definition Schema (YAML)

```yaml
version: "1.0"
config:
  global_cooldown_ms: 200
  max_simultaneous_gestures: 1
  priority_resolution: confidence

gestures:
  - name: MinimizeWindow
    type: dynamic
    priority: 1
    states:
      - id: Idle
        transitions:
          - to: PointingUp
            condition: "index_extended == True and middle_curled == True"
      - id: PointingUp
        min_duration_ms: 200
        timeout_ms: 2000
        transitions:
          - to: RapidDownFlick
            condition: "index_tip_velocity_y > FLICK_VEL and palm_center_velocity_y < PALM_STABLE"
          - to: Idle
            condition: "index_extended == False"
            abort: true
      - id: RapidDownFlick
        min_duration_ms: 50
        max_duration_ms: 300
        transitions:
          - to: Trigger
            condition: "index_tip_delta_y > FLICK_DIST"
          - to: Idle
            condition: "palm_center_delta_y > PALM_ABORT"
            abort: true
      - id: Trigger
        action: "OS:MinimizeActiveWindow"
        cooldown_ms: 1000

app_profiles:
  chrome.exe:
    SwipeLeft: "KeyPress:Ctrl+Shift+Tab"
    SwipeRight: "KeyPress:Ctrl+Tab"
  POWERPNT.EXE:
    SwipeLeft: "KeyPress:ArrowLeft"
    SwipeRight: "KeyPress:ArrowRight"
  vlc.exe:
    SwipeLeft: "Media:Previous"
    SwipeRight: "Media:Next"
  _default:
    SwipeLeft: "KeyPress:ArrowLeft"
    SwipeRight: "KeyPress:ArrowRight"
```

### 8.4 Custom Gesture Recording
1. Settings -> Custom Gestures -> Record New Gesture
2. Perform gesture 3 times, each 2 seconds (60 frames at 30 FPS)
3. Extract 21-landmark sequences, normalize (wrist origin, hand-size scale, 60-frame duration)
4. Store as JSON in data/custom_templates/
5. Runtime: rolling 60-frame buffer compared via Numba-compiled DTW (threshold default 0.15)
6. Immediate test capability with adjustable threshold

---

## 9. Configuration Reference

### 9.1 Default Config (data/default_config.yaml)

```yaml
version: "1.0"
camera:
  device_id: 0
  resolution: [640, 480]
  fps_target: 30
  backend_preference: ["MSMF", "DirectShow"]  # per-OS defaults
  auto_reconnect: true
  reconnect_backoff_ms: [100, 200, 400, 800, 1600]
  watchdog_timeout_ms: 2000

filtering:
  type: "one_euro"
  one_euro:
    min_cutoff: 0.004
    beta: 0.04
    derivate_cutoff: 1.0
  dynamic_adaptation:
    lighting_enabled: true
    depth_scaling_enabled: true

sensitivity:
  global_multiplier: 1.0

safety:
  pause_hotkey: "Win+Shift+G"  # per-OS variants documented
  safety_gesture_enabled: false

engine:
  max_hands: 2
  min_detection_confidence: 0.7
  min_tracking_confidence: 0.5

hud:
  enabled: true
  opacity: 0.3
  show_tracking_points: true
  show_progress_ring: true
  show_action_confirmation: true
  confirmation_duration_ms: 800

logging:
  level: "INFO"
  structured: true
  rotation: "daily"
  max_files: 7
  telemetry_enabled: false

profiles:
  active_profile: "default"
  auto_detect_app: true
```

### 9.2 Config Validation
All YAML validated against JSON Schema at startup. Invalid configs produce clear error listing all violations. Schema versioning allows migration.

### 9.3 User Profile Persistence
- Windows: %APPDATA%/gesture_controller/
- macOS: ~/Library/Application Support/gesture_controller/
- Linux: ~/.config/gesture_controller/

---

## 10. Development Timeline

### Phase Overview

| Week | Phase | Milestone | Focus |
|---|---|---|---|
| 1 | Phase 1 | M0 Foundations | Repo skeleton, CI, infrastructure |
| 2 | Phase 2 | M1 Camera & MediaPipe | Vision pipeline, landmark extraction |
| 3 | Phase 3 | M2 Filtering & Features | One-Euro, feature engineering, pose detection |
| 4-5 | Phase 4 | M3 MVP Gestures & OS | FSM engine, 3 gestures, Windows controller |
| 5-6 | Phase 5 | M4 Cross-Platform | macOS, Linux X11/Wayland adapters |
| 6-7 | Phase 6 | M5 Plugins & Config | Plugin loader, hot-reload, YAML schema, profiles |
| 7-8 | Phase 7 | M6 Custom Gestures | Recorder UI, DTW matcher, template storage |
| 8-9 | Phase 8 | M7 UI & Testing | Tray, overlay, full test suite, CI perf gating |
| 9-10 | Phase 9 | M8 Release Prep | Packaging, docs, ADRs, beta build |

---

## 11. Error Handling and Edge Cases

### 11.1 Error Categories and Responses

| Category | Example | Response | Logged Level |
|---|---|---|---|
| Camera I/O | Device disconnected | Reconnect with exponential backoff, publish camera_disconnected event | WARNING |
| Camera I/O | SharedMemory write failure | Skip frame, continue loop | DEBUG |
| Camera I/O | Device disappears mid-stream | Backoff reconnect, try alternate backends | ERROR |
| MediaPipe | No hands detected in frame | Return empty list, continue (normal) | DEBUG |
| MediaPipe | Model loading failure | Fatal: log error, show dialog, exit | CRITICAL |
| MediaPipe | Partial hand (visible: false) | Filter out low-visibility landmarks, continue | DEBUG |
| One-Euro Filter | NaN or inf in input | Reset filter state, skip frame | WARNING |
| One-Euro Filter | Timestamp not monotonically increasing | Clamp dt to positive minimum | WARNING |
| Feature Engineering | Division by zero (scale=0) | Use fallback scale value of 0.05 | DEBUG |
| Feature Engineering | All-zero landmarks | Return default FeatureVector, skip FSM | WARNING |
| FSM Engine | Unknown feature in condition string | Log error, skip that FSM, continue | ERROR |
| Config | Invalid YAML syntax | Show error dialog listing line/column, use defaults | ERROR |
| Config | Schema validation failure | Show all violations, use defaults for invalid keys | ERROR |
| Config | Missing required key | Use default, log warning | WARNING |
| Plugin | Import error | Skip plugin, log warning, continue | WARNING |
| Plugin | Schema validation failure | Skip plugin, log violation details | WARNING |
| Plugin | Missing PLUGIN_META | Skip file, log debug | DEBUG |
| OS Action | Permission denied (macOS Accessibility) | Show permission dialog with instructions | ERROR |
| OS Action | Window management not available (Linux Wayland) | Log warning, skip window actions, keep key/mouse/scroll | WARNING |
| OS Action | pyautogui failsafe triggered | Log, pause gesture recognition | ERROR |
| SharedMemory | FileNotFoundError (Process B startup before A) | Re-create SharedMemory, restart camera process | ERROR |
| SharedMemory | PermissionError | Fatal: log, exit | CRITICAL |
| GUI | PyQt6 display error | Log, continue headless if possible | WARNING |
| Packaging | Missing dependency at runtime | verify_install.py catches, shows user instructions | ERROR |

### 11.2 Recovery Strategies

Camera Recovery:
1. Watchdog timer: if no frame received for `watchdog_timeout_ms` (default 2000ms), mark as disconnected.
2. Publish `camera_disconnected` event (tray icon updates, overlay shows warning).
3. Attempt reconnect with exponential backoff: [100, 200, 400, 800, 1600] ms.
4. Try alternate OpenCV backends (MSMF then DirectShow on Windows; V4L2 then USB on Linux; AVFoundation on macOS).
5. After 5 failed attempts, hold for 5 seconds, then reset backoff to index 0.
6. On successful reconnect: publish `camera_recovered`, reset One-Euro filter state.

Config Recovery:
1. If user config is invalid YAML: log error, show notification, continue with defaults.
2. If user config fails schema validation: log each violation, use defaults for invalid keys, keep valid keys.
3. If default config is corrupted (should never happen in version-controlled code): fatal error.
4. ConfigManager never crashes the app. Worst case: all defaults, no user customizations.

MediaPipe Recovery:
1. If MediaPipe returns empty results for 100 consecutive frames: log warning (may be lighting issue).
2. If MediaPipe throws exception: catch, log, skip frame, continue. MediaPipe is generally robust.
3. If MediaPipe model fails to load at startup: fatal. Show dialog, suggest checking installation.

Plugin Recovery:
1. If a plugin fails to load: skip it, log warning, continue loading other plugins.
2. If a plugin crashes at runtime (handler throws): catch, log, unsubscribe that plugin.
3. If hot-reload fails: keep previous version of plugin active, log error.

### 11.3 Edge Cases

Multi-monitor setups:
- Overlay HUD covers the primary monitor by default. Configurable to cover all virtual desktop.
- Mouse actions (click, scroll) target the monitor where the cursor is, which is correct by default.
- Window management actions (minimize, switch) work on the active window regardless of monitor.

High-DPI / display scaling:
- PyQt6 handles DPI scaling via `AA_EnableHighDpiScaling`.
- Overlay coordinates are in logical pixels (Qt handles physical-to-logical mapping).
- MediaPipe coordinates are normalized [0,1], independent of display resolution.
- PyAutoGUI on Windows may need DPI awareness: `ctypes.windll.shcore.SetProcessDpiAwareness(1)`.

Multiple cameras:
- Config `camera.device_id` selects which camera (0, 1, 2...).
- Settings UI provides dropdown of available cameras (via `cv2.VideoCapture(i).isOpen()` probing).
- Only one camera active at a time. Switching requires restart of camera process.

No camera detected:
- On first launch with no camera: show setup wizard explaining camera requirement.
- List detected cameras. If none: show link to troubleshooting guide.
- App remains in system tray but gesture recognition is disabled.

Rapid lighting changes:
- One-Euro dynamic adaptation adjusts smoothing based on lighting metric.
- MediaPipe handles moderate lighting variation internally.
- Extreme changes (light on/off) cause brief tracking loss, then recovery.

Face detected instead of hand:
- MediaPipe Hands only detects hands. Face detection is a separate model not loaded.
- No false triggers from face gestures.

Two hands simultaneously:
- MediaPipe returns up to 2 Hand objects.
- Each hand is processed independently through the full pipeline.
- Global cooldown prevents both hands from triggering simultaneously (configurable: `max_simultaneous_gestures`).
- Multi-hand gestures (volume slider, zoom) are a stretch goal, not in MVP.

Hand enters/leaves frame:
- Hand enters: One-Euro filter initializes on first frame (no smoothing until 2nd frame).
- Hand leaves: FSMs reset to Idle. No stale state carried over.
- Hand re-enters: fresh initialization. No "ghost" gestures from previous appearance.

OS sleep/wake:
- On sleep: camera process may fail. On wake: watchdog triggers reconnect.
- macOS: NSWorkspace notifications for sleep/wake to proactively pause/resume.
- Windows: WM_POWERBROADCAST message handling.
- Linux: D-Bus login manager signals.

---

## 12. Installation and Onboarding UX

### 12.1 First-Run Experience

When the app launches for the first time (no user config directory exists):

Step 1: Welcome Screen
- "Welcome to Gesture Controller" with brief description (2-3 sentences).
- "Next" button.

Step 2: Camera Setup
- Dropdown showing detected cameras with preview thumbnail (1 frame).
- If no camera detected: show troubleshooting steps.
- "Test Camera" button: shows live preview for 3 seconds.
- "Next" button (disabled until camera works).

Step 3: Permission Setup (platform-specific)
- Windows: No special permissions needed. Just inform: "Gesture Controller will send keyboard and mouse input on your behalf."
- macOS: Check `AXIsProcessTrusted()`. If False: "Gesture Controller needs Accessibility permission to control windows. Click below to open System Preferences." Button opens System Preferences > Privacy > Accessibility.
- Linux: Check `/dev/uinput` write access and group membership. If no access: "Install udev rules for non-root input injection" with copy-paste terminal commands.

Step 4: Gesture Tutorial
- Show animated GIF or short video of each MVP gesture.
- User tries each gesture with real-time feedback (landmarks shown in HUD).
- "Minimize Window: Point index finger up, then flick down quickly."
- "Switch Window: Open hand, swipe left or right."
- "Scroll: Point index finger at screen, move hand up/down."
- Checkbox: "Skip tutorial" (can be re-opened from Settings > Help).

Step 5: Sensitivity Calibration (optional)
- User performs each gesture 3 times.
- App measures timing and motion magnitude.
- Suggests sensitivity multiplier adjustment if gestures are consistently too fast/slow.
- "Use recommended settings" / "Customize" buttons.

Step 6: Ready
- "You're all set! Gesture Controller is running in your system tray."
- "The overlay shows hand tracking. Try minimizing this window with a gesture!"
- Close button (app minimizes to tray).

### 12.2 Onboarding State Persistence

```yaml
# Stored in user config directory as onboarding_state.yaml
completed: true  # Set to true after step 6
camera_tested: true
permissions_granted: true
tutorial_completed: true
calibration_done: false
version: "1.0"  # If version changes, re-run onboarding
```

### 12.3 Settings > Help Menu

- "Run Setup Wizard Again" — deletes onboarding_state.yaml, relaunches wizard.
- "Gesture Reference" — opens gesture_spec.html (generated from gesture_spec.md).
- "Troubleshooting Guide" — opens docs/troubleshooting.md.
- "Open Log Directory" — opens platform log folder.
- "About" — version, license, links.

---

## 13. Performance Profiling Strategy

### 13.1 Tools

| Tool | Purpose | When to Use |
|---|---|---|
| `time.perf_counter()` | Per-stage latency | Every frame in debug builds |
| `cProfile` | Function-level profiling | When a stage exceeds budget |
| `py-spy` | Sampling profiler (no code changes) | Production-like profiling |
| `tracemalloc` | Memory allocation tracking | At every milestone gate |
| `pytest-benchmark` | Automated regression detection | Every CI run |
| `snakeviz` | cProfile output visualization | After capturing profile stats |
| `memray` | Memory profiler with flame graphs | Deep memory investigation |

### 13.2 Profiling Checkpoints

At the end of each milestone, run the full profiling suite:

M0 (Foundations):
- Baseline memory: app startup with no camera, no MediaPipe. Target: < 30 MB RSS.
- Import time: `python -c "import time; t=time.perf_counter(); import gesture_controller; print(time.perf_counter()-t)"`. Target: < 1 second.

M1 (Camera + MediaPipe):
- Camera capture latency: 1000 frames, measure per-frame time. Target: < 5ms mean.
- SharedMemory write: measure time for np.copyto. Target: < 0.1ms.
- MediaPipe extraction: 1000 frames, measure per-frame time. Target: < 10ms mean.
- Memory after 1000 frames: check for leaks. Target: 0 net growth.

M2 (Filtering + Features):
- One-Euro filter: 1000 frames of random landmarks. Target: < 0.5ms.
- Feature engineering: 1000 frames. Target: < 0.5ms.
- Combined filter+features: target < 1ms.
- tracemalloc: 0 allocations in hot path (all pre-allocated).

M3 (FSM + OS):
- FSM evaluation: 1000 frames with 10 active FSMs. Target: < 0.5ms.
- Action dispatch: 100 calls to each OS action type. Target: < 2ms each.
- Full pipeline: SharedMemory read to GestureEvent. Target: < 20ms.
- 30-minute soak test: monitor CPU and memory. Target: < 10% CPU, < 200 MB, 0 crashes.

M4-M8:
- Repeat M3 profiling on each platform.
- Plugin loading time: < 100ms for 10 plugins.
- DTW matching: < 5ms per template.
- GUI responsiveness: tray click < 100ms, settings open < 500ms.
- PyInstaller binary startup: < 2 seconds.

### 13.3 Profile-Guided Optimization Workflow

1. Run benchmarks, identify stage exceeding budget.
2. If in Python code: run `cProfile`, analyze with `snakeviz`.
3. If in NumPy code: check for unnecessary copies, non-vectorized operations.
4. If in MediaPipe: cannot optimize (external). Adjust budget if consistently over.
5. If allocation-heavy: use `tracemalloc` to find source, pre-allocate or pool.
6. If still over budget after Python-level optimization: consider Cython or Numba for the hot path.
7. Cython is a last resort. Only for proven bottlenecks with profiling evidence.

### 13.4 CI Performance Gating

```python
# scripts/check_bench_regression.py
# Compares current benchmark results against baseline
# Fails if any benchmark is > 10% slower than baseline
# Usage: python check_bench_regression.py --current bench_results.json --baseline .benchmarks/baseline.json --threshold 1.10
```

---

## 14. Accessibility and Internationalization

### 14.1 Accessibility (a11y)

Keyboard Navigation:
- All GUI elements (settings window, tray menu) must be keyboard-navigable.
- Tab order follows visual layout (left-to-right, top-to-bottom).
- Focus indicators visible on all interactive elements.
- Pause hotkey (Win+Shift+G) works without any GUI interaction.

Screen Reader Support:
- All Qt widgets have accessible names set via `setAccessibleName()`.
- Tray icon tooltip describes current state ("Gesture Controller: Active, 30 FPS").
- Overlay HUD is purely visual and informational; screen reader users use the tray tooltip for status.
- Settings window labels use `setBuddy()` to associate with their input widgets.

Visual Accessibility:
- Minimum contrast ratio: 4.5:1 for text (WCAG AA).
- Overlay skeleton lines: minimum 2px width, high contrast against dark background.
- Action confirmation text: white on semi-transparent dark background.
- Settings window: respects OS high-contrast mode.
- Minimum font size: 12px in settings, 10px in overlay.

Motor Accessibility:
- All gestures can be performed with one hand.
- Sensitivity multiplier allows users with limited hand mobility to reduce required motion.
- Gesture cooldown and minimum duration are configurable.
- Pause hotkey provides immediate escape from any recognition state.

### 14.2 Left/Right Hand Mode

- By default, the app works with either hand (MediaPipe detects handedness).
- Left-hand landmarks are mirrored to right-hand coordinate system before feature engineering.
- This means gesture definitions only need to be written once (for right hand).
- Users can configure `engine.preferred_hand` to "Left", "Right", or "Both" (default).
- When set to a specific hand, the other hand's landmarks are discarded before processing.

### 14.3 Internationalization (i18n)

String Externalization:
- All user-facing strings stored in `data/strings/` as JSON files.
- `data/strings/en.json` is the source of truth.
- Format: `"settings.window.title": "Gesture Controller Settings"`

Supported Languages (MVP):
- English (en) — complete
- Hindi (hi) — complete
- Spanish (es) — community-contributed
- Additional languages via community PRs

String Loading:
```python
# core/i18n.py
class I18n:
    def __init__(self, locale: str = "en"):
        self._strings = self._load(locale)
    
    def t(self, key: str, **kwargs) -> str:
        template = self._strings.get(key, key)
        return template.format(**kwargs)
    
    def _load(self, locale: str) -> dict:
        path = Path(__file__).parent.parent / "data" / "strings" / f"{locale}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return self._load("en")  # Fallback to English
```

Config:
```yaml
# In default_config.yaml
ui:
  locale: "en"  # or "auto" to detect from system locale
```

---

## 15. Testing Strategy

See `agent_prompts/test_strategy.md` for the complete testing specification including:

- Testing pyramid (60% unit, 15% integration, 20% property/replay, 5% E2E)
- Full test file list per module with specific test cases
- Mock landmark generator fixtures (open_palm_hand, pointing_hand, fist_hand, pinch_hand, thumbs_up_hand)
- Performance benchmark tests with targets
- CI pipeline with GitHub Actions (lint, unit, integration, benchmarks, replay, nightly E2E)
- Quality gates (coverage >= 80%, benchmark regression < 10%, replay accuracy 100%)
- Landmark fixture JSON schema and required fixture files
- Debugging guide for common test failures
- Manual QA acceptance checklist

---

## 16. CI/CD Pipeline

### 16.1 Branch Strategy

- `main`: Production-ready. Only merge via PR with all checks passing.
- `develop`: Integration branch. PRs merge here first.
- `feature/*`: Individual feature branches. PR to `develop`.
- `release/*`: Release preparation. PR to `main`.
- `hotfix/*`: Emergency fixes. PR directly to `main` and `develop`.

### 16.2 CI Pipeline (GitHub Actions)

```yaml
# Triggered on: push to any branch, PR to main/develop
# Jobs (in order with dependencies):

# 1. lint (2 min)
#    - black --check
#    - flake8
#    - mypy --strict

# 2. unit-tests (5 min, parallel across 3 OS)
#    - ubuntu-latest, windows-latest, macos-latest
#    - pytest tests/unit/ -v --cov --cov-fail-under=80

# 3. integration-tests (5 min, depends on unit-tests)
#    - ubuntu-latest
#    - pytest tests/integration/

# 4. benchmarks (3 min, depends on integration-tests)
#    - ubuntu-latest
#    - pytest tests/benchmarks/ --benchmark-only
#    - check_bench_regression.py against baseline

# 5. replay-tests (3 min, depends on unit-tests)
#    - ubuntu-latest
#    - pytest tests/replay/

# 6. nightly-e2e (30 min, cron 0 3 * * *)
#    - self-hosted runner with webcam
#    - pytest tests/e2e/ --timeout=600
#    - Upload artifact: e2e report

# 7. build (10 min, only on main/develop, depends on all above)
#    - PyInstaller build for current platform
#    - Upload artifact: binary bundle
```

### 16.3 CD Pipeline (Release)

Manual trigger on `release/*` branches:

1. Run full CI + E2E on all 3 platforms (self-hosted runners).
2. Build PyInstaller bundles for Windows, macOS, Linux.
3. Create GitHub Release with:
   - Windows: `GestureController-Setup-vX.Y.Z.exe`
   - macOS: `GestureController-vX.Y.Z.dmg`
   - Linux: `gesture-controller_X.Y.Z_amd64.deb`
   - Source tarball
   - CHANGELOG excerpt
4. Publish to PyPI (optional, for pip-installed usage).

### 16.4 Versioning

- Semantic Versioning: MAJOR.MINOR.PATCH
- MAJOR: breaking config/plugin API changes
- MINOR: new gestures, new features, new platform support
- PATCH: bug fixes, performance improvements
- Pre-release: `-alpha.N`, `-beta.N`, `-rc.N`

---

## 17. Security and Privacy

### 17.1 Threat Model

| Threat | Mitigation |
|---|---|
| Malicious YAML config | JSON Schema validation, AST allow-list parser (no eval/exec) |
| Malicious plugin | Plugin runs in same process; sandbox via restricted imports (future: subprocess isolation) |
| Camera hijacking | Only reads from user-selected device index; no network camera support |
| Keystroke logging | App sends input, does not log keystrokes. Telemetry is opt-in and anonymized. |
| Frame exfiltration | Frames exist only in SharedMemory, never persisted, never transmitted. |
| Privilege escalation (Linux udev) | udev rules only grant /dev/uinput access, not general input. User must be in input group. |
| Supply chain (dependencies) | Pin versions in requirements.txt. Review new dependency additions. |
| Man-in-the-middle (telemetry) | Telemetry uses HTTPS. Opt-in only. No personal data sent. |

### 17.2 Privacy Guarantees

1. No cloud inference. MediaPipe runs 100% on-device. No frames leave the machine.
2. No frame storage. Raw images exist only in SharedMemory buffer, overwritten every frame.
3. No recording. The app never captures or saves video or images.
4. No telemetry by default. If enabled, sends only: gesture count, FPS, error count, OS version, app version. No landmarks, no frames, no usernames.
5. Local config only. User preferences, custom gestures, app profiles stored in platform user config directory.
6. Open source. Full source code auditable. No obfuscated binaries, no hidden network calls.
7. No unique identifiers. Telemetry does not include machine ID, IP address, or user identity.

### 17.3 Security Practices

- No eval/exec/compile on user-provided strings. AST allow-list walker only.
- Plugin isolation: Plugins are loaded via importlib. In MVP, they share the process. Future: consider subprocess isolation for untrusted plugins.
- Dependency pinning: requirements.txt pins exact versions. Dependabot for security updates.
- Code signing: Windows binaries signed with Authenticode (release builds). macOS .app notarized.
- No SUID binaries. Linux udev rules are the only elevated permission mechanism.
- Input injection is explicit. Only BaseController methods can send OS input. No other code path.

---

## 18. Deployment and Packaging

### 18.1 PyInstaller Configuration

See `agent_prompts/phase_5_polish.md` Section 5 for the complete `.spec` file.

Key packaging details:
- `console=False` — no terminal window on Windows
- `upx=True` — compress binary
- Data files bundled: `data/` directory (configs, gesture definitions)
- Hidden imports: mediapipe, numpy, PyQt6, yaml, jsonschema, structlog, numba, evdev
- Excludes: matplotlib, tkinter, scipy, pandas (reduce bundle size)

### 18.2 Platform-Specific Installers

Windows (NSIS):
- `GestureController-Setup-vX.Y.Z.exe`
- Installs to `C:/Program Files/GestureController/`
- Creates desktop shortcut, start menu entry
- Adds to Windows Startup (optional, user choice)
- Uninstaller removes all files and registry entries

macOS (DMG):
- `GestureController-vX.Y.Z.dmg`
- Drag-and-drop install to /Applications
- First-run: requests Camera and Accessibility permissions
- Info.plist includes NSCameraUsageDescription, NSAccessibilityUsageDescription

Linux (deb via fpm):
- `gesture-controller_X.Y.Z_amd64.deb`
- Installs to `/opt/gesture-controller/`
- Includes udev rules in separate package: `gesture-controller-udev`
- systemd user service file for auto-start (optional)

### 18.3 Install Size Budget

| Component | Budget |
|---|---|
| Python runtime + stdlib | ~30 MB |
| MediaPipe models + libs | ~15 MB |
| PyQt6 | ~40 MB |
| NumPy + Numba | ~20 MB |
| OpenCV | ~15 MB |
| App code + data | ~2 MB |
| Total compressed | < 80 MB |
| Total installed | < 150 MB |

### 18.4 Post-Install Verification

- `scripts/verify_install.py` checks: imports, camera access, MediaPipe, config files.
- Run automatically after installation. Show results to user.
- If any check fails: show clear instructions to fix.

---

## 19. Architecture Decision Records

### ADR-001: Multiprocessing over Threading
- Context: Need concurrent camera capture and inference without GIL contention.
- Decision: Use `multiprocessing` with `shared_memory.SharedMemory` single-slot buffer.
- Consequences: Bypasses GIL entirely. Lowest latency. No backlog. Requires careful SharedMemory lifecycle management.
- Alternatives considered: Threading (GIL bottleneck), Queue (backlog latency), WebSocket IPC (Gerik's bug — network stack overhead).

### ADR-002: PyQt6 over Electron
- Context: Need system tray, overlay, and settings window.
- Decision: PyQt6 with native widgets.
- Consequences: Smaller binary (~40MB vs ~150MB), native look, system tray support, no Chromium overhead.
- Alternatives considered: Electron/React (rejected: bloated, no native tray), Tkinter (rejected: ugly, limited tray support).

### ADR-003: FSM over ML Classification
- Context: Need gesture recognition with minimal false positives.
- Decision: Deterministic finite state machines with minimum duration, timeout, and abort conditions.
- Consequences: Zero single-frame triggers. Predictable behavior. Requires manual gesture definition. Does not scale to hundreds of gestures.
- Alternatives considered: MediaPipe Gesture Recognizer (rejected: no temporal reasoning), neural network classifier (rejected: non-deterministic, black box).

### ADR-004: AST Condition Parsing
- Context: Gesture YAML condition strings need safe evaluation.
- Decision: Parse with `ast.parse()`, walk tree with allow-list of operators, compile to callable.
- Consequences: No code execution risk. Limited to boolean expressions and comparisons. Cannot call functions.
- Alternatives considered: eval() (rejected: security), custom DSL parser (rejected: reinventing Python).

### ADR-005: pyautogui with SendInput Upgrade Path
- Context: Need OS input injection on Windows.
- Decision: Start with pyautogui (simple, cross-platform). BaseController ABC allows drop-in upgrade to SendInput via ctypes.
- Consequences: Fast to implement. May have latency issues (pyautogui has internal delays). Upgrade path preserves API.
- Alternatives considered: Direct SendInput from start (rejected: complex, platform-specific), ctypes only (rejected: verbose).

### ADR-006: In-Process EventBus over IPC
- Context: Modules need to communicate without tight coupling.
- Decision: `queue.Queue`-based pub/sub within Process B. No network communication.
- Consequences: Zero serialization overhead. Subscribers called in publisher's thread. Gerik's WebSocket approach caused latency — we avoid that entirely.
- Alternatives considered: WebSocket (rejected: Gerik's bug), ZMQ (rejected: overkill for single-process), signals/slots only (rejected: couples to Qt).

### ADR-007: /dev/uinput for Linux Wayland
- Context: Wayland does not allow applications to inject input via X11 APIs.
- Decision: Use `/dev/uinput` via `python-evdev` to create a virtual input device.
- Consequences: Works on Wayland and X11. Requires udev rules for non-root access. Window management still compositor-dependent.
- Alternatives considered: ydotool (rejected: external dependency, dbus), xdotool (rejected: X11 only), GNOME/KDE D-Bus only (rejected: compositor-specific).

### ADR-008: DTW for Custom Gestures
- Context: Users need to define custom gestures without training ML models.
- Decision: Record 3 examples, normalize to 60-frame templates, average into single template, match via Numba-compiled DTW.
- Consequences: No training required. Instant feedback. Template quality depends on recording consistency. Does not scale to thousands of custom gestures.
- Alternatives considered: Neural network fine-tuning (rejected: requires GPU, data, expertise), hidden Markov models (rejected: more complex, marginal improvement).

### ADR-009: Privacy by Design
- Context: Webcam-based app raises privacy concerns.
- Decision: No cloud inference, no frame storage, no recording, telemetry opt-in only with anonymized data.
- Consequences: User trust. No server infrastructure costs. Cannot offer cloud features (multi-device sync, remote config).
- Alternatives considered: Cloud processing (rejected: latency, privacy, cost), local frame recording (rejected: storage, privacy).

### ADR-010: Plugin System with Hot Reload
- Context: Users and developers need to extend gesture/action vocabulary.
- Decision: Python files in plugin directories, discovered via glob, validated via JSON Schema, hot-reloaded via watchdog.
- Consequences: Easy to extend. No build step. Risk: malicious plugin in same process (accepted for MVP).
- Alternatives considered: Lua scripts (rejected: learning curve), YAML-only (rejected: limited expressiveness), subprocess plugins (rejected: IPC complexity).

---

## 20. Risk Register

| # | Risk | Probability | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R1 | MediaPipe latency exceeds 10ms budget on low-end hardware | Medium | High | Profile; reduce resolution to 320x240; consider MediaPipe GPU delegate | Engine | Open |
| R2 | Camera permissions blocked on macOS (Accessibility + Camera) | High | High | Clear onboarding wizard; link to System Preferences; app unusable without | UI | Open |
| R3 | Linux Wayland window management unavailable on some compositors | High | Medium | Multiple fallback paths (wlr, KWin, GNOME, xdotool, null); graceful degradation | Platform | Open |
| R4 | False positive rate > 1/hour in real-world use | Medium | High | FSM minimum duration + abort conditions; replay test suite with real motion data; user-tunable sensitivity | Engine | Open |
| R5 | PyInstaller bundle exceeds 150MB | Medium | Low | Exclude unnecessary deps; UPX compression; split into core + platform packages | Build | Open |
| R6 | One-Euro filter introduces visible lag during fast gestures | Low | High | Dynamic beta adaptation; profile with real gestures; user-adjustable parameters | Engine | Open |
| R7 | Plugin crashes affect main process stability | Medium | Medium | Try/except around plugin handlers; unload crashing plugin; future: subprocess isolation | Plugins | Open |
| R8 | DTW custom gesture matching too slow with many templates | Low | Medium | Numba JIT; batch comparison; limit max templates to 50; profile at scale | Engine | Open |
| R9 | High-DPI display causes coordinate mismatches | Medium | Medium | Qt DPI scaling; test on 150%/200% displays; MediaPipe coords are normalized (immune) | UI | Open |
| R10 | App startup exceeds 2-second target | Low | Medium | Lazy-load GUI components; profile import times; defer MediaPipe init to first frame | Engine | Open |
| R11 | SharedMemory torn frame causes MediaPipe crash | Low | Low | MediaPipe handles invalid input gracefully (returns empty). No mitigation needed. | Vision | Closed |
| R12 | OpenCV camera backend differs across OS/hardware | Medium | Low | Multi-backend fallback chain; configurable backend preference; user can override | Vision | Open |
| R13 | User config YAML corrupted by concurrent write | Low | Medium | Atomic write (write to temp file, rename); single writer (ConfigManager) | Config | Open |
| R14 | Numba JIT compilation causes first-frame stutter | Low | Low | Pre-compile DTW at startup with dummy data; Numba caches compiled functions | Engine | Open |
| R15 | Competitor releases superior open-source alternative | Low | Low | Focus on architecture quality, extensibility, and UX. Our FSM approach is differentiated. | Strategy | Open |
