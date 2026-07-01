# Gesture Specification — AI Agent Reference

**Purpose:** Canonical reference for all gesture definitions, FSM state schemas, YAML examples, feature formulas, and the DTW custom gesture system. Feed this to your coding agent when implementing `core/state_machine.py`, `models/feature_engineering.py`, `models/dtw_matcher.py`, or `data/predefined_gestures.yaml`.

---

## 1. MediaPipe Hand Landmark Map

21 landmarks per hand. All coordinates normalized [0,1] for x,y; z is relative depth (negative = toward camera).

```
  0: WRIST
  1: THUMB_CMC   2: THUMB_MCP   3: THUMB_IP   4: THUMB_TIP
  5: INDEX_MCP   6: INDEX_PIP   7: INDEX_DIP   8: INDEX_TIP
  9: MIDDLE_MCP 10: MIDDLE_PIP 11: MIDDLE_DIP 12: MIDDLE_TIP
 13: RING_MCP  14: RING_PIP  15: RING_DIP  16: RING_TIP
 17: PINKY_MCP 18: PINKY_PIP 19: PINKY_DIP 20: PINKY_TIP
```

Finger groups for iteration:
```python
FINGER_LANDMARKS = {
    "thumb":  [1, 2, 3, 4],
    "index":  [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring":   [13, 14, 15, 16],
    "pinky":  [17, 18, 19, 20],
}
MCP_JOINTS = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}
```

---

## 2. Feature Engineering Formulas

### 2.1 Coordinate System

All features computed in a hand-centric coordinate system:
1. **Origin:** Wrist (landmark 0)
2. **Scale:** Index MCP-to-PIP bone length (landmarks 5 to 6) — makes all features scale-invariant
3. **Mirror:** If hand is "Left", multiply x-coordinates by -1 — makes features hand-agnostic

```python
def to_hand_frame(landmarks: list[Landmark3D], handedness: str) -> list[Landmark3D]:
    wrist = landmarks[0]
    mcp_5 = landmarks[5]
    pip_6 = landmarks[6]
    scale = distance(mcp_5, pip_6)
    if scale < 1e-6:
        scale = 0.05  # fallback
    mirrored = -1.0 if handedness == "Left" else 1.0
    result = []
    for lm in landmarks:
        result.append(Landmark3D(
            x=(lm.x - wrist.x) * mirrored / scale,
            y=(lm.y - wrist.y) / scale,
            z=(lm.z - wrist.z) / scale,
        ))
    return result
```

### 2.2 Joint Angles

Angle at joint B given three landmarks A-B-C:
```python
def joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle in degrees at vertex B, range [0, 180]."""
    ba = a - b
    bc = c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))
```

Key angles to compute per finger (MCP, PIP, DIP):
| Angle | Joints | Meaning |
|---|---|---|
| `thumb_cmc_angle` | 1-2-3 | Thumb opposition |
| `thumb_ip_angle` | 3-4-(4 extrapolated) | Thumb extension |
| `index_mcp_angle` | 5-6-7 | Index abduction |
| `index_pip_angle` | 6-7-8 | Index curl |
| `middle_pip_angle` | 10-11-12 | Middle curl |
| `ring_pip_angle` | 14-15-16 | Ring curl |
| `pinky_pip_angle` | 18-19-20 | Pinky curl |

### 2.3 Finger Curl

Normalized curl per finger: 0 = fully extended, 1 = fully curled.
```python
def finger_curl(landmarks: list[Landmark3D], finger: str) -> float:
    """Returns 0.0 (extended) to 1.0 (curled)."""
    joints = FINGER_LANDMARKS[finger]
    if finger == "thumb":
        # Thumb: use distance from tip to base of index finger
        tip = landmarks[joints[3]]  # 4
        base = landmarks[5]  # INDEX_MCP
        extended_dist = distance(landmarks[joints[0]], landmarks[joints[3]])  # CMC to TIP
        current_dist = distance(tip, base)
        return np.clip(1.0 - current_dist / (extended_dist + 1e-6), 0.0, 1.0)
    else:
        # Other fingers: sum of PIP and DIP angles vs maximum
        mcp = landmarks[joints[0]]  # MCP
        pip = landmarks[joints[1]]  # PIP
        dip = landmarks[joints[2]]  # DIP
        tip = landmarks[joints[3]]  # TIP
        max_reach = distance(mcp, tip)
        current_reach = distance(pip, tip)
        return np.clip(1.0 - current_reach / (max_reach + 1e-6), 0.0, 1.0)
```

### 2.4 Finger Extended Boolean

```python
def is_finger_extended(landmarks: list[Landmark3D], finger: str) -> bool:
    """A finger is extended if tip is farther from wrist than PIP."""
    joints = FINGER_LANDMARKS[finger]
    tip = np.array([landmarks[joints[3]].x, landmarks[joints[3]].y, landmarks[joints[3]].z])
    pip = np.array([landmarks[joints[1]].x, landmarks[joints[1]].y, landmarks[joints[1]].z])
    wrist = np.array([landmarks[0].x, landmarks[0].y, landmarks[0].z])
    tip_dist = np.linalg.norm(tip - wrist)
    pip_dist = np.linalg.norm(pip - wrist)
    return tip_dist > pip_dist * 1.1  # 10% margin
```

### 2.5 Palm Normal Vector

```python
def palm_normal(landmarks: list[Landmark3D]) -> np.ndarray:
    """Normal to palm plane defined by WRIST, INDEX_MCP, PINKY_MCP."""
    a = np.array([landmarks[0].x, landmarks[0].y, landmarks[0].z])  # WRIST
    b = np.array([landmarks[5].x, landmarks[5].y, landmarks[5].z])  # INDEX_MCP
    c = np.array([landmarks[17].x, landmarks[17].y, landmarks[17].z])  # PINKY_MCP
    v1 = b - a
    v2 = c - a
    normal = np.cross(v1, v2)
    norm = np.linalg.norm(normal)
    if norm < 1e-8:
        return np.array([0.0, 0.0, 1.0])  # fallback: facing camera
    return normal / norm
```

### 2.6 Hand Openness

```python
def hand_openness(landmarks: list[Landmark3D]) -> float:
    """0.0 = closed fist, 1.0 = fully open palm. Average of all finger extensions."""
    curls = [finger_curl(landmarks, f) for f in ["index", "middle", "ring", "pinky"]]
    return float(1.0 - np.mean(curls))
```

### 2.7 Pinch Distance

```python
def pinch_distance(landmarks: list[Landmark3D]) -> float:
    """Euclidean distance between thumb tip (4) and index tip (8), normalized by hand size."""
    thumb_tip = np.array([landmarks[4].x, landmarks[4].y, landmarks[4].z])
    index_tip = np.array([landmarks[8].x, landmarks[8].y, landmarks[8].z])
    mcp_5 = np.array([landmarks[5].x, landmarks[5].y, landmarks[5].z])
    pip_6 = np.array([landmarks[6].x, landmarks[6].y, landmarks[6].z])
    scale = np.linalg.norm(mcp_5 - pip_6)
    return float(np.linalg.norm(thumb_tip - index_tip) / (scale + 1e-6))
```

### 2.8 FeatureVector Dataclass

```python
@dataclass
class FeatureVector:
    # Finger states (booleans)
    thumb_extended: bool
    index_extended: bool
    middle_extended: bool
    ring_extended: bool
    pinky_extended: bool

    # Finger curls (0-1)
    thumb_curl: float
    index_curl: float
    middle_curl: float
    ring_curl: float
    pinky_curl: float

    # Hand-level features
    hand_openness: float          # 0-1
    pinch_distance: float         # normalized
    palm_normal: np.ndarray       # (3,) unit vector
    palm_orientation: np.ndarray  # (4,) quaternion [w,x,y,z]

    # Joint angles (degrees, 0-180)
    thumb_cmc_angle: float
    index_mcp_angle: float
    index_pip_angle: float
    middle_pip_angle: float
    ring_pip_angle: float
    pinky_pip_angle: float

    # Spatial
    palm_center: np.ndarray  # (3,) hand-frame coords
    index_tip: np.ndarray    # (3,) hand-frame coords

    # Motion (from One-Euro filter output)
    palm_velocity: np.ndarray      # (3,) per-frame
    palm_acceleration: np.ndarray  # (3,) per-frame
    index_tip_velocity: np.ndarray  # (3,) per-frame

    # Metadata
    handedness: str        # "Left" or "Right" (after mirroring, treated as Right)
    confidence: float      # 0-1 from MediaPipe
    timestamp: float       # seconds since start
    frame_number: int
```

---

## 3. FSM Engine Specification

### 3.1 State Machine Data Model

```python
@dataclass
class FSMState:
    id: str
    is_terminal: bool = False       # True for Trigger state
    min_duration_ms: float = 0      # Must stay this long before transitions allowed
    max_duration_ms: float = float("inf")  # Timeout - return to Idle
    transitions: list["FSMTransition"] = field(default_factory=list)
    on_enter: str | None = None     # Action string if this is Trigger state
    cooldown_ms: float = 0          # Cooldown after trigger

class FSMTransition:
    target_state: str
    condition: str              # AST-parsed expression
    condition_fn: Callable      # Compiled from condition string
    is_abort: bool = False      # If True, go to Idle instead of target

class GestureFSM:
    name: str
    priority: int
    gesture_type: str           # "static" or "dynamic" or "continuous"
    states: dict[str, FSMState]
    initial_state: str = "Idle"
    current_state: str = "Idle"
    state_entered_at: float = 0
    last_triggered_at: float = 0
    is_in_cooldown: bool = False
```

### 3.2 FSM Evaluation Algorithm

```python
def evaluate(self, features: FeatureVector, timestamp: float) -> GestureEvent | None:
    """Evaluate one frame against this FSM. Returns GestureEvent or None."""
    # 1. Check cooldown
    if self.is_in_cooldown:
        if timestamp - self.last_triggered_at > self.state_cooldown_ms / 1000:
            self.is_in_cooldown = False
            self.current_state = "Idle"
        else:
            return None

    state = self.states[self.current_state]
    duration_ms = (timestamp - self.state_entered_at) * 1000

    # 2. Check timeout (max_duration)
    if duration_ms > state.max_duration_ms and not state.is_terminal:
        self.current_state = "Idle"
        return None

    # 3. Check min_duration (don't allow transitions before this)
    if duration_ms < state.min_duration_ms:
        return None

    # 4. Evaluate transitions
    for transition in state.transitions:
        if transition.condition_fn(features):  # AST-compiled callable
            if transition.is_abort:
                self.current_state = "Idle"
                return None
            self.current_state = transition.target_state
            self.state_entered_at = timestamp

            # 5. Check if new state is terminal (Trigger)
            new_state = self.states[transition.target_state]
            if new_state.is_terminal:
                event = GestureEvent(
                    gesture_name=self.name,
                    action=new_state.on_enter,
                    confidence=features.confidence,
                    hand=features.handedness,
                    timestamp=timestamp,
                )
                self.last_triggered_at = timestamp
                self.is_in_cooldown = True
                self.current_state = "Idle"
                return event
            return None

    return None
```

### 3.3 AST Condition Parser

The condition strings in YAML (e.g. `"index_extended == True and middle_curled == True"`) must be parsed safely. **NEVER use eval() or exec().**

```python
import ast
import operator

ALLOWED_NAMES = {
    "True": True, "False": False,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
    "not": lambda a: not a,
}

ALLOWED_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: lambda a: not a,
}

def compile_condition(expr_str: str) -> Callable[[FeatureVector], bool]:
    """Parse a condition string into a callable. Raises ValueError on disallowed constructs."""
    tree = ast.parse(expr_str, mode="eval")

    def _eval_node(node):
        if isinstance(node, ast.Name):
            return node.id  # Return string, resolved at call time from FeatureVector
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Compare):
            left = _eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval_node(comparator)
                op_fn = ALLOWED_OPS.get(type(op))
                if op_fn is None:
                    raise ValueError(f"Disallowed operator: {type(op).__name__}")
                left = ("_cmp", op_fn, left, right)
            return left
        elif isinstance(node, ast.BoolOp):
            values = [_eval_node(v) for v in node.values]
            op_fn = ALLOWED_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Disallowed boolean op: {type(node.op).__name__}")
            return ("_bool", op_fn, values)
        elif isinstance(node, ast.UnaryOp):
            operand = _eval_node(node.operand)
            op_fn = ALLOWED_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Disallowed unary op: {type(node.op).__name__}")
            return ("_unary", op_fn, operand)
        else:
            raise ValueError(f"Disallowed AST node: {type(node).__name__}")

    compiled = _eval_node(tree.body)

    def _execute(fv: FeatureVector) -> bool:
        return _resolve(compiled, fv)

    return _execute

def _resolve(node, fv: FeatureVector):
    if isinstance(node, (bool, int, float, str)):
        return node
    elif isinstance(node, str):
        # Must be a FeatureVector attribute name
        if hasattr(fv, node):
            return getattr(fv, node)
        # Check for threshold constants from config
        raise AttributeError(f"Unknown feature: {node}")
    elif isinstance(node, tuple):
        tag = node[0]
        if tag == "_cmp":
            _, op_fn, left, right = node
            return op_fn(_resolve(left, fv), _resolve(right, fv))
        elif tag == "_bool":
            _, op_fn, values = node
            return op_fn(*[_resolve(v, fv) for v in values])
        elif tag == "_unary":
            _, op_fn, operand = node
            return op_fn(_resolve(operand, fv))
    raise ValueError(f"Cannot resolve: {node}")
```

### 3.4 Threshold Constants in Conditions

Condition strings may reference threshold constants (e.g. `FLICK_VEL`, `PALM_STABLE`). These are resolved from the gesture definition or global config at load time.

```python
# In gesture YAML, thresholds defined per-gesture:
thresholds:
  FLICK_VEL: 0.8
  PALM_STABLE: 0.15
  FLICK_DIST: 0.12
  PALM_ABORT: 0.25

# Resolution order:
# 1. Gesture-level thresholds dict
# 2. Global config thresholds (data/default_config.yaml -> engine.thresholds)
# 3. Raise error if not found
```

---

## 4. MVP Gesture FSM Definitions

### 4.1 Minimize Active Window (Priority 1, Dynamic)

```
State: Idle
  -> PointingUp: index_extended and not middle_extended and not ring_extended and not pinky_extended

State: PointingUp [min 200ms, max 2000ms]
  -> RapidDownFlick: index_tip_velocity_y > FLICK_VEL and palm_velocity_y < PALM_STABLE
  -> Idle [abort]: not index_extended
  -> Idle [abort]: palm_velocity_magnitude > PALM_ABORT

State: RapidDownFlick [min 50ms, max 300ms]
  -> Trigger: index_tip_delta_y > FLICK_DIST
  -> Idle [abort]: palm_delta_y > PALM_ABORT
  -> Idle [timeout]: max_duration exceeded

State: Trigger
  action: OS:MinimizeActiveWindow
  cooldown: 1000ms
```

### 4.2 Switch Active Window (Priority 2, Dynamic)

```
State: Idle
  -> HandOpen: hand_openness > 0.7

State: HandOpen [min 150ms, max 1500ms]
  -> HorizontalSwipe: abs(palm_velocity_x) > SWIPE_VEL and abs(palm_velocity_x) > abs(palm_velocity_y) * 2
  -> Idle [abort]: hand_openness < 0.4

State: HorizontalSwipe [min 100ms, max 400ms]
  -> Trigger: abs(palm_center_delta_x) > SWIPE_DIST and abs(palm_velocity_z) < Z_STABLE
  -> Idle [abort]: hand_openness < 0.4
  -> Idle [timeout]: max_duration exceeded

State: Trigger
  action: OS:SwitchWindow
  cooldown: 800ms
```

### 4.3 Scroll Up/Down (Priority 3, Continuous)

```
State: Idle
  -> PointingForward: index_extended and not middle_extended and not ring_extended and index_tip_z < FORWARD_THRESH

State: PointingForward [min 200ms, max 3000ms]
  -> ScrollingActive: abs(palm_velocity_y) > SCROLL_VEL_TRIGGER
  -> Idle [abort]: middle_extended or ring_extended
  -> Idle [timeout]: max_duration exceeded

State: ScrollingActive [min 0ms, max 5000ms]
  -> ScrollingActive (self): continue while hand moves
  action: MouseScroll:delta  (continuous, every frame while in state)
  -> Idle [release]: hand_openness < 0.3 or index_tip_z > FORWARD_RELEASE
  -> Idle [timeout]: max_duration exceeded

State: Idle
  cooldown: 200ms
```

---

## 5. Secondary Gesture Definitions

### 5.1 Thumbs Up (Static)

```
State: Idle
  -> ThumbUpPose: thumb_extended and not index_extended and not middle_extended

State: ThumbUpPose [min 200ms, max 2000ms]
  -> Trigger: duration >= 200ms (auto-transition)
  -> Idle [abort]: not thumb_extended or index_extended

State: Trigger
  action: Media:PlayPause
  cooldown: 1000ms
```

### 5.2 Open Palm Show Desktop (Static)

```
State: Idle
  -> PalmOpen: hand_openness > 0.85

State: PalmOpen [min 300ms, max 2000ms]
  -> Trigger: duration >= 300ms
  -> Idle [abort]: hand_openness < 0.5

State: Trigger
  action: OS:ShowDesktop
  cooldown: 1500ms
```

### 5.3 Pinch Click (Static)

```
State: Idle
  -> Pinching: pinch_distance < PINCH_THRESHOLD

State: Pinching [min 150ms, max 1000ms]
  -> Trigger: duration >= 150ms
  -> Idle [abort]: pinch_distance > PINCH_RELEASE

State: Trigger
  action: MouseClick:Left
  cooldown: 500ms
```

### 5.4 Peace Sign (Static, Configurable Action)

```
State: Idle
  -> PeacePose: index_extended and middle_extended and not ring_extended and not pinky_extended

State: PeacePose [min 200ms, max 2000ms]
  -> Trigger: duration >= 200ms
  -> Idle [abort]: ring_extended or pinky_extended or not index_extended

State: Trigger
  action: Configurable  (from app profile or global default)
  cooldown: 800ms
```

### 5.5 Swipe Left/Right (Dynamic)

```
State: Idle
  -> HandOpen: hand_openness > 0.7

State: HandOpen [min 100ms, max 1000ms]
  -> Swiping: abs(palm_velocity_x) > SWIPE_VEL and abs(palm_velocity_x) > abs(palm_velocity_y) * 2
  -> Idle [abort]: hand_openness < 0.4

State: Swiping [min 80ms, max 350ms]
  -> TriggerLeft: palm_center_delta_x < -SWIPE_DIST
  -> TriggerRight: palm_center_delta_x > SWIPE_DIST
  -> Idle [abort]: hand_openness < 0.4
  -> Idle [timeout]: max_duration exceeded

State: TriggerLeft
  action: SwipeLeft  (resolved via app profile)
  cooldown: 300ms

State: TriggerRight
  action: SwipeRight  (resolved via app profile)
  cooldown: 300ms
```

---

## 6. Full YAML Schema for `predefined_gestures.yaml`

```yaml
version: "1.0"

config:
  global_cooldown_ms: 200
  max_simultaneous_gestures: 1
  priority_resolution: "confidence"  # or "order" or "most_recent"
  default_thresholds:
    FLICK_VEL: 0.8
    PALM_STABLE: 0.15
    FLICK_DIST: 0.12
    PALM_ABORT: 0.25
    SWIPE_VEL: 0.6
    SWIPE_DIST: 0.15
    Z_STABLE: 0.1
    FORWARD_THRESH: -0.05
    FORWARD_RELEASE: 0.02
    SCROLL_VEL_TRIGGER: 0.3
    PINCH_THRESHOLD: 0.15
    PINCH_RELEASE: 0.25

gestures:
  - name: MinimizeWindow
    type: dynamic
    priority: 1
    thresholds:
      FLICK_VEL: 0.8
      PALM_STABLE: 0.15
      FLICK_DIST: 0.12
      PALM_ABORT: 0.25
    states:
      - id: Idle
        transitions:
          - to: PointingUp
            condition: "index_extended == True and middle_extended == False and ring_extended == False and pinky_extended == False"
      - id: PointingUp
        min_duration_ms: 200
        max_duration_ms: 2000
        transitions:
          - to: RapidDownFlick
            condition: "index_tip_velocity_y > FLICK_VEL and palm_velocity_y < PALM_STABLE"
          - to: Idle
            condition: "index_extended == False"
            abort: true
          - to: Idle
            condition: "palm_velocity_magnitude > PALM_ABORT"
            abort: true
      - id: RapidDownFlick
        min_duration_ms: 50
        max_duration_ms: 300
        transitions:
          - to: Trigger
            condition: "index_tip_delta_y > FLICK_DIST"
          - to: Idle
            condition: "palm_delta_y > PALM_ABORT"
            abort: true
      - id: Trigger
        is_terminal: true
        action: "OS:MinimizeActiveWindow"
        cooldown_ms: 1000

  # ... (SwitchWindow, ScrollUpDown, ThumbsUp, OpenPalm, Pinch, PeaceSign, SwipeLeft, SwipeRight
  # follow same schema pattern)

app_profiles:
  chrome.exe:
    SwipeLeft: "KeyPress:Ctrl+Shift+Tab"
    SwipeRight: "KeyPress:Ctrl+Tab"
    ScrollUp: "MouseScroll:-3"
    ScrollDown: "MouseScroll:3"
  POWERPNT.EXE:
    SwipeLeft: "KeyPress:ArrowLeft"
    SwipeRight: "KeyPress:ArrowRight"
  vlc.exe:
    SwipeLeft: "Media:Previous"
    SwipeRight: "Media:Next"
    ThumbsUp: "Media:PlayPause"
  Spotify.exe:
    ThumbsUp: "Media:PlayPause"
    SwipeLeft: "Media:Previous"
    SwipeRight: "Media:Next"
  _default:
    SwipeLeft: "KeyPress:ArrowLeft"
    SwipeRight: "KeyPress:ArrowRight"
    ScrollUp: "MouseScroll:-3"
    ScrollDown: "MouseScroll:3"
```

---

## 7. Custom Gesture DTW System

### 7.1 Recording Flow

1. User opens Settings > Custom Gestures > Record New
2. App enters recording mode, shows 3-second countdown
3. Records 3 examples, each 2 seconds (60 frames at 30 FPS)
4. Each example = sequence of 21 (x,y,z) normalized coordinates
5. Normalization: wrist origin, MCP-bone scale, 60-frame temporal resampling

### 7.2 Normalization

```python
def normalize_sequence(raw_frames: list[np.ndarray]) -> np.ndarray:
    """
    Input: list of (21, 3) arrays
    Output: (60, 63) array — 60 timesteps, 21 landmarks x 3 coords
    """
    # 1. Per-frame: wrist origin, hand-size scale
    normalized = []
    for frame in raw_frames:
        wrist = frame[0]
        scale = np.linalg.norm(frame[5] - frame[6])  # INDEX_MCP to INDEX_PIP
        if scale < 1e-6:
            scale = 0.05
        centered = (frame - wrist) / scale
        normalized.append(centered.flatten())  # (63,)

    normalized = np.array(normalized)  # (N, 63)

    # 2. Temporal resampling to exactly 60 frames via linear interpolation
    if len(normalized) < 60:
        indices = np.linspace(0, len(normalized) - 1, 60)
        resampled = np.interp(indices, np.arange(len(normalized)), normalized, axis=0)
    else:
        indices = np.linspace(0, len(normalized) - 1, 60)
        resampled = np.array([normalized[int(i)] for i in indices])

    return resampled  # (60, 63)
```

### 7.3 DTW Distance (Numba-compiled)

```python
import numba
import numpy as np

@numba.njit(fastmath=True)
def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute DTW distance between two sequences.
    a: (N, D), b: (M, D)
    Returns: float, normalized by path length
    """
    n = a.shape[0]
    m = b.shape[0]
    INF = 1e18

    # Cost matrix (only keep 2 rows for memory efficiency)
    cost = np.full((2, m + 1), INF)
    cost[0, 0] = 0.0

    for i in range(1, n + 1):
        cost[i % 2, 0] = INF
        for j in range(1, m + 1):
            dist = 0.0
            for k in range(a.shape[1]):
                diff = a[i - 1, k] - b[j - 1, k]
                dist += diff * diff
            cost[i % 2, j] = dist + min(
                cost[(i - 1) % 2, j],      # insertion
                cost[i % 2, j - 1],         # deletion
                cost[(i - 1) % 2, j - 1],   # match
            )

    dtw_val = cost[n % 2, m]
    # Normalize by path length
    path_len = float(n + m)
    return dtw_val / path_len

@numba.njit(fastmath=True)
def dtw_distance_batch(query: np.ndarray, templates: np.ndarray, thresholds: np.ndarray) -> tuple:
    """
    Compare query against multiple templates.
    query: (60, 63), templates: (T, 60, 63), thresholds: (T,)
    Returns: (best_idx, best_dist) or (-1, inf) if none match
    """
    best_idx = -1
    best_dist = 1e18
    for t in range(templates.shape[0]):
        d = dtw_distance(query, templates[t])
        if d < best_dist:
            best_dist = d
            best_idx = t
    if best_idx >= 0 and best_dist < thresholds[best_idx]:
        return (best_idx, best_dist)
    return (-1, best_dist)
```

### 7.4 Template Storage Format

```json
{
  "version": "1.0",
  "name": "My Custom Wave",
  "action": "KeyPress:Space",
  "hand": "Right",
  "threshold": 0.15,
  "recorded_at": "2026-06-29T12:00:00Z",
  "examples": [
    [[0.0, 0.0, 0.0, ...60 frames x 63 values...]],
    [[0.0, 0.0, 0.0, ...60 frames x 63 values...]],
    [[0.0, 0.0, 0.0, ...60 frames x 63 values...]]
  ],
  "template": [[0.0, 0.0, 0.0, ...60 frames x 63 values...]]
}
```

The `template` field is the mean of all examples (averaged frame-by-frame). At runtime, the DTW distance is computed against this single averaged template.

---

## 8. GestureEvent Data Model

```python
@dataclass
class GestureEvent:
    gesture_name: str         # e.g. "MinimizeWindow", "CustomWave"
    gesture_type: str         # "static", "dynamic", "continuous", "custom"
    action: str               # Raw action string, e.g. "OS:MinimizeActiveWindow"
    confidence: float         # 0-1
    hand: str                 # "Left" or "Right"
    timestamp: float          # Seconds since epoch
    app_profile: str | None   # Process name if app-specific profile was used
    gesture_source: str       # "fsm" or "dtw"
    metadata: dict = field(default_factory=dict)  # Extensible: scroll delta, swipe direction, etc.
```

---

## 9. Priority and Conflict Resolution

When multiple FSMs could trigger simultaneously:

1. **Highest confidence wins** (default mode)
2. If tied, **lowest priority number wins** (Priority 1 > Priority 2)
3. If still tied, **most recently armed FSM wins** (entered Candidate state most recently)
4. If still tied, **first in YAML definition order wins**

Global cooldown prevents any gesture from triggering within `global_cooldown_ms` of the last trigger, regardless of which gesture triggered.

```python
def resolve_gesture_conflict(candidates: list[GestureEvent], config: dict) -> GestureEvent | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Sort by: confidence desc, priority asc
    candidates.sort(key=lambda e: (-e.confidence, e.priority))
    return candidates[0]
```
