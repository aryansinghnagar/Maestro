# Architecture Specification — AI Agent Canonical Reference

**Purpose:** This is the single source of truth for the system architecture. Every other agent prompt references this file. If there is a conflict between any two files, this document wins.

---

## 1. System Overview

A cross-platform desktop application that uses a standard RGB webcam to detect hand gestures via MediaPipe, processes them through a deterministic FSM engine, and dispatches OS-level actions (window management, scrolling, media controls). The app runs as a background daemon with a PyQt6 system tray icon and translucent HUD overlay.

**Process model:** Two processes communicating via shared memory.
- Process A (`vision/camera_stream.py`): Camera capture only. Writes frames to SharedMemory.
- Process B (`core/engine.py`): All inference, filtering, features, FSM, dispatch, and GUI in one process.

**Why not threads?** Python GIL. MediaPipe and NumPy release it partially, but camera I/O and GUI don't. SharedMemory multiprocessing eliminates GIL contention entirely.

**Why not queues/WebSocket?** Queues add backlog latency. WebSocket (Gerik's approach) adds serialization and network stack overhead. Single-slot SharedMemory means newest frame always wins, zero backlog, lowest possible latency.

---

## 2. Module Dependency Graph

```
main.py
  -> core/engine.py (GestureEngine)
       -> core/config_manager.py (ConfigManager)
       -> core/event_bus.py (EventBus)
       -> core/state_machine.py (GestureFSMManager, GestureFSM, FSMState, FSMTransition)
       -> vision/landmark_extractor.py (LandmarkExtractor)
       -> vision/one_euro_filter.py (OneEuroFilter)
       -> models/feature_engineering.py (compute_features)
       -> models/data_types.py (Hand, Landmark3D, FeatureVector, GestureEvent)
       -> models/dtw_matcher.py (CustomGestureMatcher)
       -> os_integration/ (create_controller)
            -> os_integration/base_controller.py (BaseController ABC)
            -> os_integration/windows_controller.py (WindowsController)
            -> os_integration/macos_controller.py (MacOSController)
            -> os_integration/linux_controller.py (LinuxController)
       -> os_integration/action_dispatcher.py (ActionDispatcher)
       -> plugins/plugin_loader.py (PluginLoader)
       -> gui/tray_icon.py (TrayController)
       -> gui/overlay.py (OverlayHUD)
       -> gui/settings_window.py (SettingsWindow)
       -> gui/app_entry.py (GestureControllerApp)

  vision/camera_stream.py (separate Process)
       -> multiprocessing.shared_memory
       -> cv2.VideoCapture
```

**Rule:** Dependencies flow downward. `core/` depends on `models/` and `vision/`. `os_integration/` depends on `core/` only via EventBus and interfaces. `gui/` depends on `core/` only via EventBus and Qt signals. `plugins/` depend on `core/` and `models/`.

**No module imports from another module's implementation details.** All cross-module communication is via:
1. EventBus (pub/sub)
2. ABC interfaces (BaseController, Plugin protocol)
3. Dataclass instances (Hand, FeatureVector, GestureEvent)

---

## 3. Canonical Interface Signatures

### 3.1 Data Types (`models/data_types.py`)

```python
@dataclass(frozen=True, slots=True)
class Landmark3D:
    x: float          # Normalized [0,1]
    y: float          # Normalized [0,1]
    z: float          # Relative depth (negative = toward camera)
    visibility: float = 1.0

@dataclass(frozen=True, slots=True)
class Hand:
    landmarks: tuple[Landmark3D, ...]  # Exactly 21, immutable
    handedness: str   # "Left" or "Right" (MediaPipe label)
    confidence: float  # 0-1
    wrist: Landmark3D = field(init=False)
    palm_center: np.ndarray = field(init=False)

@dataclass
class FeatureVector:
    # Finger states (booleans)
    thumb_extended: bool
    index_extended: bool
    middle_extended: bool
    ring_extended: bool
    pinky_extended: bool
    # Finger curls (0-1, 0=extended, 1=curled)
    thumb_curl: float
    index_curl: float
    middle_curl: float
    ring_curl: float
    pinky_curl: float
    # Hand-level
    hand_openness: float           # 0-1
    pinch_distance: float          # Normalized by hand size
    palm_normal: np.ndarray        # (3,) unit vector
    palm_center: np.ndarray        # (3,) hand-frame coords
    index_tip: np.ndarray          # (3,) hand-frame coords
    # Motion
    palm_velocity: np.ndarray      # (3,) per-frame
    palm_acceleration: np.ndarray  # (3,) per-frame
    index_tip_velocity: np.ndarray  # (3,) per-frame
    palm_velocity_magnitude: float = 0.0
    # Accumulated deltas (for dynamic gestures, reset on state change)
    index_tip_delta_y: float = 0.0
    palm_center_delta_x: float = 0.0
    palm_center_delta_y: float = 0.0
    palm_delta_y: float = 0.0
    # Metadata
    handedness: str = "Right"     # After mirroring, always "Right"
    confidence: float = 1.0
    timestamp: float = 0.0
    frame_number: int = 0

@dataclass
class GestureEvent:
    gesture_name: str
    gesture_type: str    # "static", "dynamic", "continuous", "custom"
    action: str          # Raw action string, e.g. "OS:MinimizeActiveWindow"
    confidence: float    # 0-1
    hand: str            # "Left" or "Right"
    timestamp: float
    app_profile: str | None = None
    gesture_source: str = "fsm"  # "fsm" or "dtw"
    metadata: dict = field(default_factory=dict)
```

### 3.2 EventBus (`core/event_bus.py`)

```python
class EventBus:
    def __init__(self, max_queue_size: int = 1000) -> None: ...
    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None: ...
    def unsubscribe(self, event_type: str, handler: Callable) -> None: ...
    def publish(self, event_type: str, event: Any) -> None: ...
```

Event types used in the system:
- `"gesture_triggered"` -> GestureEvent
- `"camera_disconnected"` -> dict {"reason": str}
- `"camera_recovered"` -> dict {}
- `"config_changed"` -> dict {changed keys}
- `"plugin_reloaded"` -> str (plugin name)
- `"pause_toggled"` -> bool (True = paused)
- `"shutdown"` -> None

### 3.3 ConfigManager (`core/config_manager.py`)

```python
class ConfigManager:
    def __init__(self, config_path: Path | None = None) -> None:
        # Loads: default_config.yaml -> user config.yaml (merged)
        # Validates against JSON Schema
        ...
    def get(self, key: str, default: Any = None) -> Any:
        # Dot-notation: get("camera.fps_target") -> 30
        ...
    def set(self, key: str, value: Any) -> None: ...
    def save_user_config(self) -> None:
        # Write to platform-specific user config dir
        ...
    def reload(self) -> None:
        # Re-read YAML from disk, merge, validate
        ...
```

### 3.4 BaseController ABC (`os_integration/base_controller.py`)

```python
class BaseController(ABC):
    def key_press(self, key: str, modifiers: list[str] | None = None) -> None: ...
    def key_release(self, key: str) -> None: ...
    def key_combo(self, keys: list[str]) -> None: ...
    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None: ...
    def mouse_double_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> ...
    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None: ...
    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None: ...
    def get_foreground_app(self) -> str: ...
    def minimize_active_window(self) -> None: ...
    def switch_window(self) -> None: ...
    def show_desktop(self) -> None: ...
    def media_play_pause(self) -> None: ...
    def media_next(self) -> None: ...
    def media_previous(self) -> None: ...
    def media_volume_up(self) -> None: ...
    def media_volume_down(self) -> None: ...
    def is_supported(self) -> bool: ...
```

### 3.5 GestureEngine (`core/engine.py`)

```python
class GestureEngine:
    def __init__(self, config: ConfigManager, event_bus: EventBus) -> None:
        # Creates SharedMemory, starts camera process, initializes all pipeline stages
        ...
    def process_frame(self, timestamp: float) -> None:
        # One full pipeline iteration:
        # SharedMemory -> landmarks -> filter -> features -> FSM -> event bus
        ...
    def set_paused(self, paused: bool) -> None: ...
    def shutdown(self) -> None: ...
    def get_current_hands(self) -> list: ...  # For GUI polling
    def get_fsm_states(self) -> dict: ...   # For GUI overlay
    def get_fps(self) -> float: ...
    def get_gesture_count(self) -> int: ...
    def reload_config(self) -> None: ...
```

### 3.6 Plugin Protocol

Any .py file in a plugin directory must define:

```python
PLUGIN_META: dict  # {"name": str, "version": str, "description": str}
GESTURE_DEFINITIONS: list[dict]  # FSM gesture definitions in YAML schema format
ACTION_HANDLERS: dict[str, Callable]  # Optional: custom action handlers
```

---

## 4. SharedMemory Protocol

### 4.1 Memory Layout

```
Offset 0 to 921,599 (640 * 480 * 3 bytes):
  Raw RGB frame, row-major, shape (480, 640, 3), dtype uint8

Total size: 921,600 bytes
```

No header, no sequence number, no metadata. The reader (Process B) always gets the latest frame. If Process A writes while B reads, B may get a torn frame (partially updated). This is acceptable because:
1. Torn frames produce no hand landmarks (MediaPipe handles gracefully)
2. The next frame (1/30th second later) will be clean
3. Adding synchronization would add latency

### 4.2 Lifecycle

1. Process B creates SharedMemory with `create=True`
2. Process B passes the `name` attribute to Process A via constructor or command-line arg
3. Process A opens it with `SharedMemory(name=shm_name)`
4. Both processes run independently
5. On shutdown: Process B calls `shm.close()` then `shm.unlink()`

---

## 5. Performance Constraints

### 5.1 Latency Budget (per frame)

| Stage | Budget | Notes |
|---|---|---|
| Camera capture + preprocess | 6 ms | USB3 webcam, OpenCV resize + flip |
| SharedMemory write | < 0.1 ms | memcpy, negligible |
| SharedMemory read | < 0.1 ms | memcpy, negligible |
| MediaPipe Hands | 10 ms | BlazePalm + hand landmark model |
| One-Euro filter | 0.5 ms | 21 landmarks x 3 axes, vectorized |
| Feature engineering | 0.5 ms | Geometry math on 21 points |
| FSM evaluation | 0.5 ms | ~10 FSMs, each ~5 comparisons |
| Action dispatch | 2 ms | OS event injection |
| **Total** | **< 20 ms** | **>= 50 FPS target** |

### 5.2 Resource Budgets

| Resource | Limit | Measurement |
|---|---|---|
| CPU | <= 10% quad-core | 30-min monitoring, average |
| Memory (RSS) | <= 200 MB | Peak, including MediaPipe model |
| Startup time | <= 2 seconds | Process spawn to first frame processed |
| Disk (installed) | <= 150 MB | PyInstaller bundle |

### 5.3 Allocation Rules

- Pre-allocate all arrays used in the frame loop. Never allocate inside the loop.
- Reuse FeatureVector, numpy arrays for landmarks, velocity, acceleration.
- Use `np.ndarray(shape, dtype=np.float64)` with buffer reuse.
- Profile with `tracemalloc` at each milestone. Zero net growth over 10,000 frames.

---

## 6. Concurrency Model

### 6.1 Process A: Camera Capture

- Runs as `multiprocessing.Process(daemon=True)`
- Single while loop: `cap.read() -> preprocess -> SharedMemory.write`
- No inference, no logic. Pure I/O.
- Watchdog: if no frame for 2 seconds, reconnect.
- Reconnect: exponential backoff [100, 200, 400, 800, 1600] ms.
- Backend fallback: try multiple OpenCV backends (MSMF, DirectShow on Windows; V4L2, USB on Linux; AVFoundation on macOS).

### 6.2 Process B: Everything Else

Single process, single main loop:
```
while running:
    hands = extractor.extract(shm_name)     # Read SharedMemory + MediaPipe
    if hands:
        for hand in hands:
            filtered = filter.process(hand.landmarks)  # One-Euro
            features = compute_features(filtered)      # Feature engineering
            event = fsm_manager.evaluate(features)      # FSM
            if event:
                event_bus.publish("gesture_triggered", event)
    sleep(0.001)  # Prevent busy-wait when no hands
```

GUI runs on the main thread via PyQt6 event loop. Engine polls via QTimer at ~60 FPS for display updates. The actual inference loop can run on a separate thread within Process B if needed (profile first), but the GIL impact is minimal since MediaPipe and NumPy release it.

### 6.3 No Locks on SharedMemory

By design: single writer (Process A), single reader (Process B), single slot. No locks, no semaphores, no atomic operations. The newest frame always wins. Torn frames are handled gracefully by MediaPipe (produces no landmarks).

---

## 7. Error Handling Philosophy

### 7.1 Principles

1. **Never crash.** The daemon must survive any error and log it.
2. **Degrade gracefully.** If camera fails, show disconnected status. If MediaPipe fails, skip frame.
3. **Recover automatically.** Camera reconnects. Config reloads on change. Plugins reload on file modify.
4. **Log everything.** Structured JSON logging via structlog. Every error has full context.

### 7.2 Error Categories

| Category | Example | Response |
|---|---|---|
| Camera I/O | Device disconnected | Reconnect with backoff, publish camera_disconnected |
| MediaPipe | No landmarks in frame | Return None, continue loop |
| Config | Invalid YAML | Log error, use defaults, show notification |
| Plugin | Import error | Log warning, skip plugin, continue |
| OS Action | Permission denied | Log error, show notification to user |
| SharedMemory | FileNotFoundError | Log error, attempt re-creation |
| Filter | NaN in input | Reset filter state, skip frame |

### 7.3 Safety Mechanisms

- **Pause hotkey:** Win+Shift+G (Windows), Cmd+Shift+G (macOS), configurable on Linux. Immediately stops all gesture recognition.
- **Global cooldown:** 200ms between any two gesture triggers. Prevents action storms.
- **No single-frame trigger:** FSM requires minimum duration in Candidate state.
- **Config validation:** JSON Schema at startup. Invalid config produces clear error, does not start.

---

## 8. Privacy Design

1. **On-device inference only.** No cloud API calls at runtime.
2. **No raw frame persistence.** Frames exist only in SharedMemory, destroyed after landmark extraction.
3. **No image capture or recording.** The app never saves images or video.
4. **Telemetry opt-in only.** Default: off. If enabled, sends anonymized aggregate stats only (gesture counts, FPS, error rates). Never sends landmarks, frames, or personal data.
5. **Config stored locally.** User configs and custom gesture templates live in platform-standard user config directories.
6. **Open source.** Full code auditable. No hidden network calls.

---

## 9. Platform Abstraction Strategy

### 9.1 Factory Pattern

```python
# os_integration/__init__.py
def create_controller() -> BaseController:
    system = platform.system()
    if system == "Windows":
        from .windows_controller import WindowsController
        return WindowsController()
    elif system == "Darwin":
        from .macos_controller import MacOSController
        return MacOSController()
    elif system == "Linux":
        from .linux_controller import LinuxController
        return LinuxController()
    raise RuntimeError(f"Unsupported platform: {system}")
```

### 9.2 Platform Differences Handled

| Capability | Windows | macOS | Linux |
|---|---|---|---|
| Key/mouse input | pyautogui (SendInput upgrade) | CGEventPost (Quartz) | /dev/uinput (evdev) |
| Foreground app | win32gui + psutil | NSWorkspace | D-Bus / xdotool |
| Minimize window | ShowWindow(SW_MINIMIZE) | AXUIElement kAXPressAction | Compositor-dependent |
| Switch window | Alt+Tab | CGWindowList + AXUIElement raise | Compositor-dependent |
| Media keys | pyautogui media keys | NSEvent systemDefined | /dev/uinput KEY_* |
| Permissions | None (standard user) | Accessibility + Camera | Camera + input group + udev |
| Packaging | .exe (NSIS via PyInstaller) | .app (DMG via PyInstaller) | deb/rpm (fpm) |

---

## 10. Configuration Architecture

### 10.1 Layer Order (later overrides earlier)

1. `data/default_config.yaml` — shipped with app, version-controlled
2. `data/predefined_gestures.yaml` — shipped gesture definitions and app profiles
3. `~/.config/gesture_controller/config.yaml` — user overrides (platform-specific path)
4. Command-line arguments — highest priority

### 10.2 Config Schema

All YAML files validated against JSON Schema at startup. Schema files in `data/`:
- `config_schema.json` — validates `default_config.yaml` and user config
- `gesture_schema.json` — validates `predefined_gestures.yaml` and plugin gesture definitions

### 10.3 Hot Reload

ConfigManager uses a filesystem watcher (watchdog) on the user config file. On modification:
1. Re-read YAML
2. Validate against schema
3. Deep-merge with defaults
4. Publish `config_changed` event
5. Engine and GUI subscribers update their state

---

## 11. Testing Architecture

See `test_strategy.md` for the full testing specification. Key architectural points:

- **Unit tests** mock all external dependencies (camera, MediaPipe, OS controller)
- **Integration tests** use real SharedMemory but mock MediaPipe
- **Replay tests** use pre-recorded landmark JSON fixtures fed through the FSM
- **Benchmarks** use pytest-benchmark with 1000-frame pre-generated sequences
- **E2E tests** use virtual cameras (OBS, v4l2loopback) and real OS
- **CI gates:** lint, type-check, 80% coverage, benchmark regression <10%, replay accuracy 100%

---

## 12. File Naming Conventions

| Pattern | Meaning | Example |
|---|---|---|
| `test_{module}_{function}_{scenario}.py` | Unit test | `test_one_euro_filter_static_input.py` |
| `bench_{module}.py` | Benchmark | `bench_full_pipeline.py` |
| `test_{integration}_{flow}.py` | Integration test | `test_camera_to_landmarks.py` |
| `{feature}_success_N.json` | Replay fixture | `minimize_window_success_1.json` |

---

## 13. Critical Invariants (Never Violate)

1. **MediaPipe objects never leave `vision/landmark_extractor.py`.** Convert to project dataclasses immediately.
2. **No `eval()`, `exec()`, `compile()` on user-provided strings.** Use AST allow-list walker.
3. **No raw image data persists after landmark extraction.** SharedMemory is the only buffer.
4. **No module directly calls another module's methods.** All communication via EventBus.
5. **No single frame can trigger a gesture.** FSM minimum duration is non-zero for all non-Idle states.
6. **No network communication at runtime.** Zero cloud calls, zero WebSocket, zero HTTP.
7. **No blocking calls in the frame loop.** Camera I/O is in a separate process. GUI is on Qt event loop.
8. **`ml_pipeline/` is never imported at runtime.** It is for offline model training only.
9. **All thresholds are in YAML config.** Zero magic numbers in code.
10. **Left hand is mirrored to right hand coordinate system** before feature engineering.
