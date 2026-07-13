# Phase 3-4 (M2-M3) — Core Engine & MVP Gestures — AI Agent Prompt

**Milestones:** M2 (Filtering & Features) + M3 (FSM Engine, 3 MVP Gestures, Windows Controller)
**Duration:** Weeks 3-5
**Agent task:** Implement the One-Euro filter, feature engineering module, full FSM engine with AST condition parsing, the 3 MVP gestures, the Windows OS controller, and the action dispatcher. By the end, the app recognizes minimize/switch/scroll gestures and executes real OS actions on Windows.

**Depends on:** M1 (camera + landmark extraction working, SharedMemory communication proven)

---

## 1. M2: One-Euro Filter (`vision/one_euro_filter.py`)

### 1.1 Specification

NumPy-vectorized implementation. Processes all 21 landmarks x 3 coordinates simultaneously. NOT a per-landmark loop.

```python
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class OneEuroFilterState:
    """State for one landmark axis. 21x3 = 63 instances."""
    x_prev: float = 0.0
    x_filt_prev: float = 0.0
    dx_prev: float = 0.0
    hat_x_prev: float = 0.0
    initialized: bool = False

class OneEuroFilter:
    """Vectorized One-Euro filter for hand landmark smoothing.
    
    Reference: "1-Euro Filter: A Simple Speed-based Low-Pass Filter for Noisy Input"
    by Gery Casiez, Nicolas Roussel, Daniel Vogel. CHI 2012.
    """

    def __init__(self, config: dict):
        oe_config = config.get("filtering", {}).get("one_euro", {})
        self._min_cutoff = oe_config.get("min_cutoff", 0.004)
        self._beta = oe_config.get("beta", 0.04)
        self._derivate_cutoff = oe_config.get("derivate_cutoff", 1.0)
        self._dynamic = config.get("filtering", {}).get("dynamic_adaptation", {})

        # Pre-allocate state arrays for 21 landmarks x 3 axes
        # Shape: (21, 3)
        self._x_prev = np.zeros((21, 3), dtype=np.float64)
        self._x_filt_prev = np.zeros((21, 3), dtype=np.float64)
        self._dx_prev = np.zeros((21, 3), dtype=np.float64)
        self._hat_x_prev = np.zeros((21, 3), dtype=np.float64)
        self._initialized = False

        # Velocity output (attached to filtered landmarks)
        self._velocity = np.zeros((21, 3), dtype=np.float64)
        self._acceleration = np.zeros((21, 3), dtype=np.float64)
        self._prev_velocity = np.zeros((21, 3), dtype=np.float64)

    def filter(self, landmarks: np.ndarray, timestamp: float,
               lighting_metric: float | None = None, depth_metric: float | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Filter landmarks and return (filtered, velocity, acceleration).
        
        Args:
            landmarks: (21, 3) array of [x, y, z] per landmark
            timestamp: current time in seconds
            lighting_metric: avg pixel intensity [0, 255] for dynamic adaptation
            depth_metric: wrist-to-MCP distance for dynamic adaptation
            
        Returns:
            (filtered_landmarks, velocity, acceleration) each (21, 3)
        """
        # Dynamic parameter adaptation
        min_cutoff = self._min_cutoff
        beta = self._beta
        if self._dynamic.get("lighting_enabled", False) and lighting_metric is not None:
            # Low light -> more smoothing (lower cutoff)
            light_factor = np.clip(lighting_metric / 128.0, 0.3, 1.0)
            min_cutoff *= light_factor
        if self._dynamic.get("depth_scaling_enabled", False) and depth_metric is not None:
            # Far hand -> more smoothing
            depth_factor = np.clip(depth_metric * 5.0, 0.5, 2.0)
            beta /= depth_factor

        if not self._initialized:
            self._x_prev = landmarks.copy()
            self._x_filt_prev = landmarks.copy()
            self._initialized = True
            return landmarks.copy(), self._velocity.copy(), self._acceleration.copy()

        dt = max(timestamp - self._prev_timestamp, 1e-6)

        # Vectorized computation for all 63 values simultaneously
        # Step 1: Derivative (velocity) with low-pass filtering
        dx = (landmarks - self._x_prev) / dt
        alpha_d = self._smoothing_factor(dt, self._derivate_cutoff)
        hat_dx = alpha_d * dx + (1 - alpha_d) * self._dx_prev

        # Step 2: Adaptive cutoff based on velocity
        cutoff = min_cutoff + beta * np.abs(hat_dx)
        alpha = self._smoothing_factor(dt, cutoff)

        # Step 3: Filtered position
        hat_x = alpha * landmarks + (1 - alpha) * self._x_filt_prev

        # Update state
        self._prev_velocity = self._velocity.copy()
        self._velocity = hat_dx.copy()
        self._acceleration = (self._velocity - self._prev_velocity) / dt
        self._x_prev = landmarks.copy()
        self._dx_prev = hat_dx.copy()
        self._x_filt_prev = hat_x.copy()
        self._prev_timestamp = timestamp

        return hat_x.copy(), self._velocity.copy(), self._acceleration.copy()

    @staticmethod
    def _smoothing_factor(te: float, cutoff: float | np.ndarray) -> float | np.ndarray:
        """Compute smoothing factor alpha from sampling period and cutoff frequency.
        alpha = te / (te + (1 / (2 * pi * cutoff)))"""
        tau = 1.0 / (2.0 * np.pi * cutoff)
        return te / (te + tau)

    def reset(self) -> None:
        """Reset filter state. Call on camera reconnect or hand lost."""
        self._x_prev[:] = 0
        self._x_filt_prev[:] = 0
        self._dx_prev[:] = 0
        self._hat_x_prev[:] = 0
        self._velocity[:] = 0
        self._acceleration[:] = 0
        self._initialized = False
```

### 1.2 Tests

- Static input (same landmark every frame) -> output equals input (no drift)
- Step input -> output follows with lag proportional to beta
- Noisy input -> output is smoother (measure noise reduction ratio)
- NaN input -> output does not crash, filter resets
- Very fast motion -> beta increases, filter tracks closely
- Very slow motion -> min_cutoff applies, aggressive smoothing
- Velocity output matches numerical derivative of filtered position
- 10000 frames -> no memory growth (tracemalloc check)

---

## 2. M2: Feature Engineering (`models/feature_engineering.py`)

Full implementation of all formulas from `gesture-spec.md` Section 2. Key points:

```python
import numpy as np
from models.data_types import Hand, Landmark3D, FeatureVector
import time

FINGER_LANDMARKS = {
    "thumb":  [1, 2, 3, 4],
    "index":  [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring":   [13, 14, 15, 16],
    "pinky":  [17, 18, 19, 20],
}

FINGER_MCP = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}

def compute_features(hand: Hand, velocity: np.ndarray, acceleration: np.ndarray,
                     timestamp: float, frame_number: int) -> FeatureVector:
    """Compute full FeatureVector from a Hand and its motion data.
    
    Args:
        hand: Hand dataclass with 21 Landmark3D
        velocity: (21, 3) velocity array from One-Euro filter
        acceleration: (21, 3) acceleration array from One-Euro filter
        timestamp: current time
        frame_number: frame counter
        
    Returns:
        FeatureVector with all fields populated
    """
    lms = hand.landmarks  # tuple of Landmark3D
    arr = np.array([[l.x, l.y, l.z] for l in lms])  # (21, 3)
    
    # Convert to hand-centric frame
    wrist = arr[0]
    mcp5 = arr[5]
    pip6 = arr[6]
    scale = np.linalg.norm(mcp5 - pip6)
    if scale < 1e-6:
        scale = 0.05
    
    mirror = -1.0 if hand.handedness == "Left" else 1.0
    centered = (arr - wrist) / scale
    centered[:, 0] *= mirror  # Mirror x for left hand
    
    # Finger extension booleans
    finger_extended = {}
    for name, joints in FINGER_LANDMARKS.items():
        tip = np.linalg.norm(centered[joints[3]] - centered[0])
        pip = np.linalg.norm(centered[joints[1]] - centered[0])
        finger_extended[name] = tip > pip * 1.1
    
    # Finger curl (0 = extended, 1 = curled)
    finger_curl = {}
    for name in FINGER_LANDMARKS:
        joints = FINGER_LANDMARKS[name]
        tip_dist = np.linalg.norm(centered[joints[3]] - centered[joints[1]])
        full_reach = np.linalg.norm(centered[joints[0]] - centered[joints[3]])
        if full_reach < 1e-6:
            finger_curl[name] = 0.0
        else:
            finger_curl[name] = float(np.clip(1.0 - tip_dist / full_reach, 0.0, 1.0))
    
    # Hand openness
    openness_values = [1.0 - finger_curl[f] for f in ["index", "middle", "ring", "pinky"]]
    hand_openness = float(np.mean(openness_values))
    
    # Pinch distance
    thumb_tip = centered[4]
    index_tip = centered[8]
    pinch_dist = float(np.linalg.norm(thumb_tip - index_tip))
    
    # Palm normal
    v1 = centered[5] - centered[0]
    v2 = centered[17] - centered[0]
    palm_norm = np.cross(v1, v2)
    norm_mag = np.linalg.norm(palm_norm)
    if norm_mag < 1e-8:
        palm_normal = np.array([0.0, 0.0, 1.0])
    else:
        palm_normal = palm_norm / norm_mag
    
    # Palm center (in hand frame)
    palm_center = (centered[0] + centered[5] + centered[17]) / 3.0
    
    # Index tip (in hand frame)
    index_tip = centered[8]
    
    # Joint angles
    def angle_at(a_idx, b_idx, c_idx):
        a = centered[a_idx]
        b = centered[b_idx]
        c = centered[c_idx]
        ba = a - b
        bc = c - b
        cos_a = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))
    
    # Transform velocity/acceleration to hand frame too
    palm_vel = velocity[0] / scale  # Wrist velocity, normalized
    palm_vel[0] *= mirror
    palm_accel = acceleration[0] / scale
    palm_accel[0] *= mirror
    index_tip_vel = velocity[8] / scale
    index_tip_vel[0] *= mirror
    
    return FeatureVector(
        thumb_extended=finger_extended["thumb"],
        index_extended=finger_extended["index"],
        middle_extended=finger_extended["middle"],
        ring_extended=finger_extended["ring"],
        pinky_extended=finger_extended["pinky"],
        thumb_curl=finger_curl["thumb"],
        index_curl=finger_curl["index"],
        middle_curl=finger_curl["middle"],
        ring_curl=finger_curl["ring"],
        pinky_curl=finger_curl["pinky"],
        hand_openness=hand_openness,
        pinch_distance=pinch_dist,
        palm_normal=palm_normal,
        palm_center=palm_center,
        index_tip=index_tip,
        palm_velocity=palm_vel,
        palm_acceleration=palm_accel,
        index_tip_velocity=index_tip_vel,
        palm_velocity_magnitude=float(np.linalg.norm(palm_vel)),
        handedness=hand.handedness if hand.handedness == "Right" else "Right",
        confidence=hand.confidence,
        timestamp=timestamp,
        frame_number=frame_number,
    )
```

---

## 3. M3: FSM Engine (`core/state_machine.py`)

Full implementation per `gesture-spec.md` Section 3. Key components:

- `FSMState` dataclass with transitions, min/max duration, is_terminal, action, cooldown
- `FSMTransition` dataclass with target_state, condition string, condition_fn (compiled), is_abort
- `GestureFSM` class with evaluate() method implementing the algorithm from gesture-spec.md Section 3.2
- `ASTConditionCompiler` class implementing the safe parser from gesture-spec.md Section 3.3
- `GestureEngine` class that manages all FSMs, resolves conflicts, and emits GestureEvents

```python
# core/state_machine.py — key structure

class GestureFSMManager:
    """Manages all gesture FSMs. Evaluates all every frame, resolves conflicts."""

    def __init__(self, config: dict, event_bus: "EventBus"):
        self._fsms: list[GestureFSM] = []
        self._event_bus = event_bus
        self._global_cooldown_until: float = 0
        self._global_cooldown_ms = config.get("config", {}).get("global_cooldown_ms", 200)
        self._load_gestures(config)

    def _load_gestures(self, config: dict):
        """Load gesture definitions from predefined_gestures.yaml."""
        from core.config_manager import ConfigManager
        # Load from data/predefined_gestures.yaml
        # Parse each gesture into GestureFSM with compiled conditions
        # Sort by priority
        ...

    def evaluate(self, features: FeatureVector) -> GestureEvent | None:
        """Evaluate all FSMs for one frame. Return best GestureEvent or None."""
        # Check global cooldown
        if features.timestamp < self._global_cooldown_until:
            return None

        candidates = []
        for fsm in self._fsms:
            event = fsm.evaluate(features, features.timestamp)
            if event is not None:
                candidates.append(event)

        if not candidates:
            return None

        if len(candidates) == 1:
            event = candidates[0]
        else:
            event = self._resolve_conflict(candidates)

        # Set global cooldown
        self._global_cooldown_until = features.timestamp + self._global_cooldown_ms / 1000

        return event

    def _resolve_conflict(self, candidates: list[GestureEvent]) -> GestureEvent:
        candidates.sort(key=lambda e: (-e.confidence, e.metadata.get("priority", 999)))
        return candidates[0]
```

---

## 4. M3: Windows Controller (`os_integration/windows_controller.py`)

### 4.1 Implementation

```python
import pyautogui
import platform
import structlog
from os_integration.base_controller import BaseController

logger = structlog.get_logger(__name__)

# pyautogui safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01  # Minimal pause between actions

class WindowsController(BaseController):
    """Windows OS controller using pyautogui. Start simple, upgrade to SendInput later."""

    def __init__(self):
        if not self.is_supported():
            raise RuntimeError("WindowsController not supported on this OS")
        logger.info("WindowsController initialized (pyautogui)")

    def is_supported(self) -> bool:
        return platform.system() == "Windows"

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        if modifiers:
            combo = "+".join(modifiers + [key])
            pyautogui.hotkey(combo)
        else:
            pyautogui.press(key)

    def key_release(self, key: str) -> None:
        pyautogui.keyUp(key)

    def key_combo(self, keys: list[str]) -> None:
        pyautogui.hotkey(*keys)

    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)

    def mouse_double_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        pyautogui.doubleClick(x, y, button=button)

    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        if absolute:
            pyautogui.moveTo(x, y)
        else:
            pyautogui.move(x, y)

    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        if delta_y:
            pyautogui.scroll(int(delta_y))
        if delta_x:
            pyautogui.hscroll(int(delta_x))

    def get_foreground_app(self) -> str:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length:
            # Get window title
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            # Get process name via PID
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            import psutil
            try:
                return psutil.Process(pid.value).name().lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return title.lower()
        return ""

    def minimize_active_window(self) -> None:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE

    def switch_window(self) -> None:
        self.key_combo(["alt", "tab"])

    def show_desktop(self) -> None:
        self.key_combo(["win", "d"])

    def media_play_pause(self) -> None:
        pyautogui.press("playpause")

    def media_next(self) -> None:
        pyautogui.press("nexttrack")

    def media_previous(self) -> None:
        pyautogui.press("prevtrack")

    def media_volume_up(self) -> None:
        for _ in range(3):
            pyautogui.press("volumeup")

    def media_volume_down(self) -> None:
        for _ in range(3):
            pyautogui.press("volumedown")
```

### 4.2 SendInput Upgrade Path (Future)

When profiling shows pyautogui is too slow or unreliable:
```python
# In windows_controller.py — future upgrade
def _send_key_event(self, vk_code: int, flags: int = 0) -> None:
    """Send key event via SendInput. Faster and more reliable than pyautogui."""
    import ctypes
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                     ("dwFlags", ctypes.c_uint), ("time", ctypes.c_uint),
                     ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _anonymous_ = ("_input",)
        _fields_ = [("type", ctypes.c_uint), ("_input", _INPUT)]

    inp = INPUT(type=1)
    inp.ki.wVk = vk_code
    inp.ki.dwFlags = flags
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
```

---

## 5. M3: Action Dispatcher (`os_integration/action_dispatcher.py`)

```python
import re
import structlog
from models.data_types import GestureEvent
from os_integration.base_controller import BaseController
from core.config_manager import ConfigManager

logger = structlog.get_logger(__name__)

class ActionDispatcher:
    """Routes GestureEvent to the appropriate BaseController method."""

    def __init__(self, controller: BaseController, config: ConfigManager, event_bus: "EventBus"):
        self._controller = controller
        self._config = config
        self._profiles = self._load_profiles()
        event_bus.subscribe("gesture_triggered", self._on_gesture)

    def _load_profiles(self) -> dict[str, dict[str, str]]:
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent / "data" / "predefined_gestures.yaml"
        if not path.exists():
            return {}
        with open(path) as f:
            data = yaml.safe_load(f)
        return data.get("app_profiles", {})

    def _on_gesture(self, event: GestureEvent) -> None:
        action_str = self._resolve_action(event)
        self._execute(action_str)
        logger.info("Action executed", gesture=event.gesture_name, action=action_str)

    def _resolve_action(self, event: GestureEvent) -> str:
        if not self._config.get("profiles.auto_detect_app", True):
            return event.action
        foreground = self._controller.get_foreground_app()
        if foreground and foreground in self._profiles:
            if event.gesture_name in self._profiles[foreground]:
                return self._profiles[foreground][event.gesture_name]
        if "_default" in self._profiles:
            if event.gesture_name in self._profiles["_default"]:
                return self._profiles["_default"][event.gesture_name]
        return event.action

    def _execute(self, action_str: str) -> None:
        parts = action_str.split(":", 1)
        if len(parts) != 2:
            logger.error("Invalid action format", action=action_str)
            return

        action_type, action_value = parts[0], parts[1]

        if action_type == "OS":
            self._execute_os(action_value)
        elif action_type == "KeyPress":
            self._execute_keypress(action_value)
        elif action_type == "MouseClick":
            self._execute_mouse_click(action_value)
        elif action_type == "MouseScroll":
            self._execute_scroll(action_value)
        elif action_type == "Media":
            self._execute_media(action_value)
        else:
            logger.error("Unknown action type", type=action_type)

    def _execute_os(self, action: str) -> None:
        dispatch = {
            "MinimizeActiveWindow": self._controller.minimize_active_window,
            "SwitchWindow": self._controller.switch_window,
            "ShowDesktop": self._controller.show_desktop,
        }
        fn = dispatch.get(action)
        if fn:
            fn()
        else:
            logger.error("Unknown OS action", action=action)

    def _execute_keypress(self, keys_str: str) -> None:
        keys = keys_str.split("+")
        self._controller.key_combo(keys)

    def _execute_mouse_click(self, button: str) -> None:
        self._controller.mouse_click(button=button.lower())

    def _execute_scroll(self, delta_str: str) -> None:
        try:
            delta = int(delta_str)
            self._controller.mouse_scroll(delta_y=delta)
        except ValueError:
            logger.error("Invalid scroll delta", delta=delta_str)

    def _execute_media(self, action: str) -> None:
        dispatch = {
            "PlayPause": self._controller.media_play_pause,
            "Next": self._controller.media_next,
            "Previous": self._controller.media_previous,
            "VolumeUp": self._controller.media_volume_up,
            "VolumeDown": self._controller.media_volume_down,
        }
        fn = dispatch.get(action)
        if fn:
            fn()
```

---

## 6. Engine Main Loop Integration

Update `core/engine.py` to wire everything together:

```python
class GestureEngine:
    def __init__(self, config, event_bus):
        self._config = config
        self._event_bus = event_bus
        self._paused = False

        # Vision pipeline
        self._extractor = LandmarkExtractor(config)
        self._filter = OneEuroFilter(config)

        # Feature engineering
        # (compute_features is a module-level function)

        # Gesture engine
        self._fsm_manager = GestureFSMManager(config, event_bus)

        # Action dispatch
        controller = create_controller()
        self._dispatcher = ActionDispatcher(controller, config, event_bus)

        # Stats
        self._fps = 0.0
        self._gesture_count = 0
        self._frame_count = 0

    def process_frame(self, timestamp: float):
        if self._paused:
            return

        # 1. Read landmarks from SharedMemory (done by extractor)
        hands = self._extractor.extract(self._shm_name)
        if not hands:
            return

        for hand in hands:
            # 2. Convert to numpy
            lm_array = np.array([[l.x, l.y, l.z] for l in hand.landmarks])

            # 3. Filter
            filtered, velocity, acceleration = self._filter.filter(lm_array, timestamp)

            # 4. Convert back to Landmark3D for feature engineering
            smoothed_landmarks = tuple(
                Landmark3D(x=f[0], y=f[1], z=f[2]) for f in filtered
            )
            smoothed_hand = Hand(
                landmarks=smoothed_landmarks,
                handedness=hand.handedness,
                confidence=hand.confidence,
            )

            # 5. Features
            features = compute_features(smoothed_hand, velocity, acceleration, timestamp, self._frame_count)

            # 6. FSM
            event = self._fsm_manager.evaluate(features)
            if event:
                event.hand = hand.handedness
                self._event_bus.publish("gesture_triggered", event)
                self._gesture_count += 1

        self._frame_count += 1
```

---

## 7. Tests for M2-M3

### M2 Tests:
- `tests/unit/test_one_euro_filter.py` — all cases from Section 1.2 above
- `tests/unit/test_feature_engineering.py`:
  - Open palm: all fingers extended -> hand_openness > 0.8
  - Fist: all fingers curled -> hand_openness < 0.2
  - Pinch: thumb-index close -> pinch_distance < 0.2
  - Pointing: only index extended -> index_extended=True, others False
  - Scale invariance: same pose at 2x distance -> identical features
  - Hand mirroring: Left hand -> features match Right hand equivalent

### M3 Tests:
- `tests/unit/test_state_machine.py` — see test-strategy.md Section 1.1
- `tests/unit/test_condition_parser.py`:
  - "index_extended == True" parses and evaluates correctly
  - "index_extended == True and middle_extended == False" works
  - "index_tip_velocity_y > 0.5" with numeric comparison
  - "not index_extended" with negation
  - "eval(" in expression raises ValueError
  - "__import__(" in expression raises ValueError
- `tests/unit/test_action_dispatcher.py`:
  - "OS:MinimizeActiveWindow" calls controller.minimize_active_window()
  - "KeyPress:Ctrl+C" calls controller.key_combo(["Ctrl", "C"])
  - "MouseScroll:3" calls controller.mouse_scroll(delta_y=3)
  - "Media:PlayPause" calls controller.media_play_pause()
  - App profile lookup: chrome.exe + SwipeLeft -> "KeyPress:Ctrl+Shift+Tab"
- `tests/integration/test_features_to_fsm.py`:
  - Feed minimize gesture landmark sequence -> GestureEvent produced
  - Feed switch gesture landmark sequence -> GestureEvent produced
  - Feed random motion -> no GestureEvent

---

## 8. Acceptance Criteria for M2

- [ ] OneEuroFilter produces smooth output from noisy input
- [ ] Filter is vectorized (no Python loop over 21 landmarks)
- [ ] Dynamic adaptation: low light increases smoothing
- [ ] Velocity and acceleration arrays are correct
- [ ] Feature engineering produces correct FeatureVector for all test poses
- [ ] Features are scale-invariant (same pose, different distance -> same features)
- [ ] Features are hand-agnostic (left/right mirror -> same features)
- [ ] All M2 tests pass
- [ ] Full pipeline timing: camera -> filter -> features < 12ms

## 9. Acceptance Criteria for M3

- [ ] FSM engine loads all 3 MVP gestures from YAML
- [ ] Conditions parsed via AST (no eval/exec)
- [ ] Minimize gesture: pointing + flick -> OS:MinimizeActiveWindow dispatched
- [ ] Switch gesture: open hand + horizontal swipe -> OS:SwitchWindow dispatched
- [ ] Scroll gesture: pointing + vertical motion -> MouseScroll dispatched continuously
- [ ] No single frame can trigger any gesture
- [ ] Cooldown prevents rapid re-triggering
- [ ] WindowsController: minimize, switch, scroll, media keys all work
- [ ] ActionDispatcher parses all action string formats
- [ ] App profiles: same gesture maps to different action per app
- [ ] All M3 tests pass
- [ ] False positive rate: < 1 per hour on idle motion replay
