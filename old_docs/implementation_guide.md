# Cross-Platform Desktop Hand-Gesture Controller

Implement a production-grade, low-latency (<30ms) desktop hand-gesture controller that translates standard webcam video feed into system commands (window management, mouse scrolling, media, and custom controls). The system uses Google's MediaPipe Hands for on-device landmark extraction, a vectorized speed-adaptive One-Euro Filter to resolve the jitter-lag tradeoff, and a deterministic Finite State Machine (FSM) engine to guard against accidental triggers (the "Midas Touch" problem).

This plan has been reworked based on user decisions regarding input simulation and concurrency architectures.

---

## Architectural Decisions & Long-Term Alignments

Based on review and feedback, we are adopting the following technical paths:

1. **Windows Input Simulation Target (Short-Term Simplicity, Long-Term Hardware Emulation)**
   - **Short-Term Approach:** We will implement Windows input simulation using a simpler user-space interface (such as high-level standard APIs or simple Win32 input calls). This reduces initial integration complexity.
   - **Architectural Guard:** The interface `BaseController` will be designed to abstract all OS actions. This ensures that we can drop in low-level hardware emulation via `ctypes.windll.user32.SendInput` structs later without modifying the core FSM or action-mapping logic.

2. **Process Isolation & Concurrency (Confirmed Long-Term Approach)**
   - **Approach:** We will implement the multiprocessing architecture isolating **Process A (Camera Capture)** from **Process B (Inference & Logic)**.
   - **Frame Exchange:** We will use a single-slot shared memory buffer (`multiprocessing.shared_memory.SharedMemory`) rather than a pipe or queue. The newest camera frame will immediately overwrite any pending frame. This guarantees a zero-backlog, lowest-latency path.

3. **Linux Wayland Support (Confirmed Long-Term Approach)**
   - **Approach:** We will build Wayland support as a first-class feature by writing to `/dev/uinput` via the `evdev` library.
   - **Onboarding:** We will include a guided script that creates the necessary `udev` rules so that users can run the daemon without root privileges.

---

## New Essential Features Added

To elevate this application from a prototype to a premium desktop utility, we have designed the following new capabilities into the core architecture:

1. **App-Specific Dynamic Mappings (Profiles)**
   - **Why it's essential:** A gesture like "Swipe Left" should not do the same thing in every app. It should press `ArrowLeft` in PowerPoint or PDF reader (next slide), `Ctrl+Tab` in Chrome/Edge (previous tab), and `MediaPrevious` in VLC or Spotify.
   - **How it's implemented:** The `action_dispatcher.py` dynamically queries the active window's process name using the OS API and resolves the gesture to the command defined in the corresponding profile.

2. **On-Screen Heads-Up Display (Translucent HUD Overlay)**
   - **Why it's essential:** Without visual feedback, users cannot tell if a gesture is being registered, if they are holding a pinch long enough, or if the camera has lost tracking.
   - **How it's implemented:** A lightweight, translucent click-through overlay showing a circular tracking ring around the active index finger, a filling progress indicator for hold/pinch gestures, and subtle card confirmations of executed actions.

3. **Active Safety Lock (Global Pause/Resume)**
   - **Why it's essential:** Users scratch their faces, wave their hands, or type on their keyboards. We need an absolute safety lock to prevent accidental commands.
   - **How it's implemented:** A dedicated system-wide keyboard shortcut (e.g., `Win + Shift + G`) or a simple "safety gesture" (e.g., crossing wrists or double-fist hold for 1.5s) that toggles the gesture engine between `Active` and `Suspended` modes.

4. **Dynamic Environmental Sensitivity Adaptation**
   - **Why it's essential:** Frame rate drops in dim light, and hand size differences or changes in distance from the camera distort absolute movement distances.
   - **How it's implemented:** The `one_euro_filter` and FSM thresholds dynamically scale their speed coefficients and pixel-distance boundaries using:
     - **Lighting metric:** Calculated from the average pixel intensity of the bounding box.
     - **Depth metric:** Scaled relative to the current wrist-to-middle-finger metacarpophalangeal (MCP) landmark distance.

5. **Multi-Hand Coordinated Gestures**
   - **Why it's essential:** Single-hand actions are great for binary triggers (click, minimize), but continuous controls (volume slider, screen brightness, zoom) are much more intuitive when coordinated with two hands (e.g., locking an anchor with the left hand and dragging with the right hand).
   - **How it's implemented:** The FSM engine consumes a dual-hand feature vector, mapping relative deltas between hands to system inputs.

6. **Automated Diagnostic Logging & Recovery**
   - **Why it's essential:** Webcam connections drop, OS permissions change, and USB hubs restart. The daemon must recover gracefully.
   - **How it's implemented:** Hardware watchdog monitoring in `camera_stream.py` that handles automatic backend switches (e.g., V4L2 vs USB on Linux, AVFoundation on Mac, MSMF vs DirectShow on Windows) on frame-drop thresholds, and outputs sanitized telemetry files for troubleshooting.

---

## Proposed Changes

We will build the project inside the directory `gesture_controller` with the following clean, modular component structures.

```
gesture_controller/
├── core/
├── vision/
├── models/
├── plugins/
├── os_integration/
├── actions/
├── gui/
├── data/
├── tests/
└── main.py
```

---

### Component 1: Core Orchestration and Config

This component manages the main process lifecycle, the in-process event bus (using a lock-free pub/sub design), the deterministic state machine engine, and user configurations.

#### [NEW] [event_bus.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/event_bus.py)
A lightweight, thread-safe, in-process pub/sub event bus using Python's `queue` or observer pattern. To satisfy the latency requirements, it will run inside the process memory space and will never use local WebSockets or network stacks (Gerik's design bug).

#### [NEW] [config_manager.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/config_manager.py)
Manages YAML configuration parsing, schema validation, and user profile persistence (such as custom FSM thresholds, filters, active profiles, and camera IDs).
- **Security Constraint:** Implements a strict parser for dynamic FSM condition strings using Python's `ast.parse` and an allow-list walker, explicitly prohibiting the use of raw `eval()`.

#### [NEW] [state_machine.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/state_machine.py)
The core FSM engine. Consumes the normalized feature vectors frame-by-frame. It manages transitions between `Idle`, `Ready`, `Executing`, `Trigger`, and `Cooldown` states, enforcing timeouts and Midas-Touch abort guards.

#### [NEW] [engine.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/core/engine.py)
The master daemon coordinator. Spawns the multiprocessing queues, initializes shared memory segments, runs the main inference-logic loop, manages graceful shutdown signals, and handles error recovery.

---

### Component 2: Camera Stream and Vision Pipeline

Responsible for hardware camera access (Process A), MediaPipe Hand landmark regressor execution, and vectorized One-Euro filtering.

#### [NEW] [camera_stream.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/vision/camera_stream.py)
Runs in a separate OS process. Captures frames from OpenCV, handles automatic camera recovery if the device disconnects, and writes the raw image matrix into a shared memory buffer. It drops older frames immediately if the consumer is slower than the camera FPS.

#### [NEW] [landmark_extractor.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/vision/landmark_extractor.py)
Imports MediaPipe Hands and wraps it in `LIVE_STREAM` mode. Consumes raw frames from the shared memory buffer, extracts 21 3D landmarks, converts them immediately to standardized coordinate structs, and frees/recycles frame memory.

#### [NEW] [one_euro_filter.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/vision/one_euro_filter.py)
A NumPy-vectorized implementation of the speed-adaptive One-Euro Filter. Computes the dynamic cutoff frequency based on landmark velocity to suppress jitter when hand is static, while minimizing latency during rapid flicks.

---

### Component 3: Feature Engineering and Pattern Matching

Calculates geometric features from raw landmarks and implements Dynamic Time Warping (DTW) for user-recorded custom gestures.

#### [NEW] [feature_engineering.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/models/feature_engineering.py)
Translates 21 Cartesian coordinates into translation-, scale-, and rotation-invariant features:
- Origin alignment (using wrist as origin).
- Depth scaling (using middle finger MCP length).
- Joint angles (using bone vector dot products).
- Handedness (automatically mirroring gesture definitions for left vs. right hands).
- Dynamic sensitivity parameters (lighting and depth-based adaptations).

#### [NEW] [dtw_matcher.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/models/dtw_matcher.py)
Calculates Dynamic Time Warping distances between the rolling frame buffer history and user-recorded gesture templates. Compiled using `numba` to achieve sub-millisecond similarity alignment matrices.

---

### Component 4: OS Integration and Event Dispatching

Abstracts operating system calls behind a unified interface, mapping FSM triggers to native keyboard, mouse, and window-level actions.

#### [NEW] [base_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/base_controller.py)
An Abstract Base Class (`ABC`) defining standard input injection and window-management methods.

#### [NEW] [windows_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/windows_controller.py)
Windows-specific controller implementing a simpler user-space input emulation framework (e.g. using standard user-space accessibility and input APIs), designed to be easily pluggable with low-level `SendInput` ctypes structures in the future. Tracks the foreground window process name using Windows API to support app-specific profiles.

#### [NEW] [macos_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/macos_controller.py)
macOS-specific controller implementing `Quartz.CoreGraphics` event posting for input simulation and `AXUIElement` Accessibility API calls for non-focused window management.

#### [NEW] [linux_controller.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/linux_controller.py)
Linux-specific controller using `/dev/uinput` via the `evdev` library to simulate a hardware mouse and keyboard, bypassing Wayland input isolation blocks.

#### [NEW] [action_dispatcher.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/os_integration/action_dispatcher.py)
Resolves incoming `GestureEvent` triggers. Retrieves the active window process name, checks the configuration profile mapping, and routes the action (e.g. keypress, scroll, active window minimize) to the corresponding `BaseController` subclass.

---

### Component 5: Plugins and Custom Mappings

Establishes the extensibility system.

#### [NEW] [action_mapper.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/actions/action_mapper.py)
Translates configuration action strings (e.g. `"KeyPress:Ctrl+C"`, `"OS:MinimizeActiveWindow"`, `"MouseScroll:5"`) into execution callbacks on the native OS controller.

#### [NEW] [builtin/media_gestures.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/plugins/builtin/media_gestures.py)
A Python-based gesture plugin implementing common media controls (Play/Pause, Volume Up/Down, Next/Prev) utilizing the plugin API.

#### [NEW] [builtin/window_gestures.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/plugins/builtin/window_gestures.py)
A Python-based gesture plugin containing default FSM structures for active window management.

---

### Component 6: Graphical User Interface & HUD

PyQt-based system tray icon, settings manager, custom gesture recorder, and transparent overlay HUD.

#### [NEW] [tray_icon.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/tray_icon.py)
Creates a system tray entry for pausing/resuming tracking, selecting active camera, showing device status, and opening settings.

#### [NEW] [overlay.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/overlay.py)
A click-through translucent desktop HUD that draws the active tracking points on the user's hand and renders circular progress bars on hold triggers.

#### [NEW] [gesture_recorder.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/gesture_recorder.py)
Onboarding interface guiding users through template recording (capturing 3 examples of 2 seconds each), saving coordinates to JSON, and verifying detection confidence.

#### [NEW] [app_entry.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/gui/app_entry.py)
Wires the PyQt loop with the master daemon engine, coordinating clean initialization and GUI threads.

---

### Component 7: Configurations and Entrypoint

#### [NEW] [predefined_gestures.yaml](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/data/predefined_gestures.yaml)
Defines the three default gestures (`MinimizeWindow`, `SwitchWindow`, and `ScrollUpDown`) using the FSM state schema. Includes application-specific profiles (e.g. Chrome, VLC, PowerPoint mappings).

#### [NEW] [main.py](file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/gesture_controller/main.py)
The primary entrypoint of the application. Checks OS, instantiates target processes, loads configurations, and spins up the system.

---

## Verification Plan

### Automated Tests
We will build a mock-landmark data framework to run unit and integration tests offline without requiring a connected camera hardware feed.

Run the following test commands:
- **Unit & Integration Tests:**
  ```powershell
  python -m pytest tests/unit/
  ```
- **Gesture Replay Tests (Validation set):**
  ```powershell
  python -m pytest tests/replay/
  ```
- **Performance Benchmark Gating:**
  ```powershell
  python tests/benchmarks/run_perf_tests.py
  ```

### Manual Verification
1. **Camera Stream & Watchdog:** Force-disconnect the camera USB cable during execution; verify the daemon shifts to search/reconnect loop and recovers tracking within 1.5 seconds of reconnection.
2. **Safety Lock Verification:** Toggle the active safety lock gesture/shortcut and perform various incidental gestures (e.g. wave, write, point); verify zero actions fire in suspended mode.
3. **App-Specific Profile Testing:**
   - Map "Swipe Left" to `Previous Slide` in PowerPoint and `Previous Tab` in Chrome.
   - Verify PowerPoint slide transitions back when active, and Chrome shifts tabs when active, without cross-firing.
4. **Overlay HUD Rendering:** Perform a pinch gesture and verify the translucent overlay displays a circular completion gauge directly tracking the hand coordinates with zero visual latency.
