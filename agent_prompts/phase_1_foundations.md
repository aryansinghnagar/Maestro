# Phase 1-2 (M0-M1) — Foundations & Camera — AI Agent Prompt

**Milestones:** M0 (Foundations) + M1 (Camera & MediaPipe)
**Duration:** Weeks 1-2
**Agent task:** Create the project skeleton, set up CI, implement the camera capture process with SharedMemory, and build the MediaPipe landmark extractor. By the end, you have two processes communicating: one writing frames, one extracting hand landmarks.

---

## 1. M0: Repository Foundations (Week 1)

### 1.1 Project Skeleton

Create the full directory structure exactly as specified in `architecture_spec.md`. Every directory needs an `__init__.py`. Create stub files with docstrings explaining purpose.

**Priority files to create (in order):**

```
gesture_controller/
  __init__.py                    # Package version
  main.py                        # Entry point stub
  pyproject.toml                 # Project metadata, tool configs
  requirements.txt               # Pinned dependencies
  requirements-dev.txt           # Test/lint dependencies
  setup.py                       # Minimal, delegates to pyproject.toml

  core/
    __init__.py
    engine.py                    # Stub: class GestureEngine
    event_bus.py                 # Stub: class EventBus
    config_manager.py            # Stub: class ConfigManager
    state_machine.py             # Stub: class GestureFSM

  vision/
    __init__.py
    camera_stream.py             # TODO in M1
    landmark_extractor.py        # TODO in M1
    one_euro_filter.py           # Stub

  models/
    __init__.py
    data_types.py                # ALL dataclasses here
    feature_engineering.py       # Stub
    dtw_matcher.py               # Stub

  os_integration/
    __init__.py
    base_controller.py           # ABC
    windows_controller.py        # Stub
    action_dispatcher.py         # Stub

  plugins/
    __init__.py
    plugin_loader.py             # Stub

  actions/
    __init__.py
    action_mapper.py             # Stub

  gui/
    __init__.py
    app_entry.py                 # Stub

  data/
    default_config.yaml          # Full default config
    predefined_gestures.yaml     # Full gesture definitions
    custom_templates/
      .gitkeep

  tests/
    __init__.py
    conftest.py                  # Shared fixtures
    unit/
      __init__.py
    integration/
      __init__.py
    replay/
      __init__.py
      fixtures/
        .gitkeep
    benchmarks/
      __init__.py

  ml_pipeline/                   # Empty with README
    README.md                    # "OFFLINE ONLY - never imported at runtime"

  adr/
    README.md

  docs/
    README.md

  .github/
    workflows/
      ci.yml                     # Full CI pipeline (see test_strategy.md)
    PULL_REQUEST_TEMPLATE.md
    CODEOWNERS
    .gitignore
```

### 1.2 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "gesture-controller"
version = "0.1.0"
description = "Cross-platform hand-gesture desktop controller"
requires-python = ">=3.11"
license = {text = "MIT"}

[project.scripts]
gesture-controller = "gesture_controller.main:main"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "benchmark: performance benchmark tests",
    "slow: tests that take > 5 seconds",
    "e2e: end-to-end tests requiring hardware",
]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["gesture_controller"]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 1.3 requirements.txt

```
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
PyQt6>=6.5.0
PyYAML>=6.0
jsonschema>=4.17.0
structlog>=23.1.0
numba>=0.57.0
```

### 1.4 requirements-dev.txt

```
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-benchmark>=4.0.0
pytest-timeout>=2.1.0
pytest-xdist>=3.3.0
hypothesis>=6.82.0
black>=23.7.0
flake8>=6.1.0
mypy>=1.5.0
types-PyYAML>=6.0.12
```

### 1.5 Data Models (`models/data_types.py`)

Implement ALL dataclasses here. This is foundational — every other module imports from here.

```python
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass(frozen=True, slots=True)
class Landmark3D:
    """Single landmark point. Coordinates normalized [0,1] for x,y; z relative depth."""
    x: float
    y: float
    z: float
    visibility: float = 1.0

@dataclass(frozen=True, slots=True)
class Hand:
    """One detected hand with 21 landmarks."""
    landmarks: tuple[Landmark3D, ...]  # Exactly 21
    handedness: str  # "Left" or "Right"
    confidence: float
    wrist: Landmark3D = field(init=False)
    palm_center: np.ndarray = field(init=False)

    def __post_init__(self):
        assert len(self.landmarks) == 21, f"Expected 21 landmarks, got {len(self.landmarks)}"
        object.__setattr__(self, 'wrist', self.landmarks[0])
        pc = np.array([
            (self.landmarks[0].x + self.landmarks[5].x + self.landmarks[17].x) / 3,
            (self.landmarks[0].y + self.landmarks[5].y + self.landmarks[17].y) / 3,
            (self.landmarks[0].z + self.landmarks[5].z + self.landmarks[17].z) / 3,
        ])
        object.__setattr__(self, 'palm_center', pc)

@dataclass
class FeatureVector:
    """Computed features from one frame of one hand."""
    # Finger states
    thumb_extended: bool
    index_extended: bool
    middle_extended: bool
    ring_extended: bool
    pinky_extended: bool
    thumb_curl: float
    index_curl: float
    middle_curl: float
    ring_curl: float
    pinky_curl: float
    # Hand-level
    hand_openness: float
    pinch_distance: float
    palm_normal: np.ndarray
    palm_center: np.ndarray
    index_tip: np.ndarray
    # Motion
    palm_velocity: np.ndarray
    palm_acceleration: np.ndarray
    index_tip_velocity: np.ndarray
    palm_velocity_magnitude: float = 0.0
    # Metadata
    handedness: str = "Right"
    confidence: float = 1.0
    timestamp: float = 0.0
    frame_number: int = 0
    # Accumulated deltas (for dynamic gestures)
    index_tip_delta_y: float = 0.0
    palm_center_delta_x: float = 0.0
    palm_center_delta_y: float = 0.0
    palm_delta_y: float = 0.0

@dataclass
class GestureEvent:
    """Emitted when a gesture is recognized."""
    gesture_name: str
    gesture_type: str  # "static", "dynamic", "continuous", "custom"
    action: str
    confidence: float
    hand: str
    timestamp: float
    app_profile: Optional[str] = None
    gesture_source: str = "fsm"
    metadata: dict = field(default_factory=dict)

class CameraEvent:
    DISCONNECTED = "camera_disconnected"
    RECOVERED = "camera_recovered"
    RECONNECTING = "camera_reconnecting"

class SystemEvent:
    CONFIG_CHANGED = "config_changed"
    PAUSE_TOGGLED = "pause_toggled"
    SHUTDOWN = "shutdown"
```

### 1.6 EventBus (`core/event_bus.py`)

```python
import queue
import threading
from typing import Any, Callable
import structlog

logger = structlog.get_logger(__name__)

class EventBus:
    """In-process publish/subscribe. Single thread-safe queue.
    Subscribers are called in the publishing thread. Keep handlers fast."""

    def __init__(self, max_queue_size: int = 1000):
        self._subscribers: dict[str, list[Callable]] = {}
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h != handler
                ]

    def publish(self, event_type: str, event: Any) -> None:
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler failed", event_type=event_type)
```

### 1.7 ConfigManager (`core/config_manager.py`)

```python
import yaml
import jsonschema
import os
import structlog
from pathlib import Path
from typing import Any

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "data" / "default_config.yaml"

# User config locations per platform
USER_CONFIG_DIRS = {
    "Windows": Path(os.environ.get("APPDATA", "")) / "gesture_controller",
    "Darwin": Path.home() / "Library" / "Application Support" / "gesture_controller",
    "Linux": Path.home() / ".config" / "gesture_controller",
}

class ConfigManager:
    def __init__(self, config_path: Path | None = None):
        self._config: dict = {}
        self._schema: dict = {}
        self._load_schema()
        self._load_config(config_path)

    def _load_schema(self) -> None:
        schema_path = Path(__file__).parent.parent / "data" / "config_schema.json"
        if schema_path.exists():
            with open(schema_path) as f:
                self._schema = json.loads(f.read())

    def _load_config(self, config_path: Path | None = None) -> None:
        paths = []
        if config_path:
            paths.append(config_path)
        # System default
        paths.append(DEFAULT_CONFIG_PATH)
        # User override
        import platform
        user_dir = USER_CONFIG_DIRS.get(platform.system())
        if user_dir:
            paths.append(user_dir / "config.yaml")

        for p in paths:
            if p and p.exists():
                with open(p) as f:
                    user_data = yaml.safe_load(f) or {}
                self._deep_merge(self._config, user_data)

        if self._schema:
            try:
                jsonschema.validate(self._config, self._schema)
            except jsonschema.ValidationError as e:
                logger.error("Config validation failed", errors=str(e.message))
                raise

    def _deep_merge(self, base: dict, override: dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        d = self._config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
```

### 1.8 CI Setup

Create `.github/workflows/ci.yml` — full spec in `test_strategy.md` Section 4. Must include: lint, unit-tests, integration-tests, benchmarks, replay-tests jobs.

Create `.gitignore`:
```
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
.mypy_cache/
.pytest_cache/
.benchmarks/
*.so
.venv/
venv/
*.log
data/custom_templates/*.json
!data/custom_templates/.gitkeep
```

---

## 2. M1: Camera & MediaPipe (Week 2)

### 2.1 CameraStream Process (`vision/camera_stream.py`)

This runs as a **separate process** (not thread). It captures frames and writes them to SharedMemory.

```python
import cv2
import numpy as np
import multiprocessing as mp
from multiprocessing import shared_memory
import structlog
import time
import sys

logger = structlog.get_logger(__name__)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_CHANNELS = 3
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS

class CameraStream:
    """Process A: Captures frames from webcam and writes to SharedMemory."""

    def __init__(self, config: dict, shm_name: str):
        self.config = config
        self.shm_name = shm_name
        self._running = False
        self._cap: cv2.VideoCapture | None = None
        self._backoff_idx = 0
        self._backoff_times = config.get("camera", {}).get(
            "reconnect_backoff_ms", [100, 200, 400, 800, 1600]
        )

    def run(self) -> None:
        """Main loop for the camera capture process."""
        self._running = True
        while self._running:
            try:
                self._connect_camera()
                self._capture_loop()
            except Exception as e:
                logger.error("Camera error, reconnecting", error=str(e))
                self._disconnect()
                self._backoff_reconnect()
        logger.info("Camera stream stopped")

    def _connect_camera(self) -> None:
        device_id = self.config.get("camera", {}).get("device_id", 0)
        backends = self.config.get("camera", {}).get("backend_preference", [])

        self._cap = None
        for backend in backends:
            try:
                cap = cv2.VideoCapture(device_id, cv2.CAP_BACKENDS.get(backend, cv2.CAP_ANY))
                if cap.isOpened():
                    self._cap = cap
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, self.config.get("camera", {}).get("fps_target", 30))
                    logger.info("Camera connected", backend=backend, device=device_id)
                    self._backoff_idx = 0
                    return
            except Exception:
                continue

        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera device {device_id} with any backend")

    def _capture_loop(self) -> None:
        shm = shared_memory.SharedMemory(name=self.shm_name)
        frame_buf = np.ndarray((FRAME_HEIGHT, FRAME_WIDTH, FRAME_CHANNELS), dtype=np.uint8, buffer=shm.buf)
        watchdog_timeout = self.config.get("camera", {}).get("watchdog_timeout_ms", 2000) / 1000
        last_frame_time = time.monotonic()

        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                if time.monotonic() - last_frame_time > watchdog_timeout:
                    logger.warning("Camera watchdog triggered")
                    raise RuntimeError("Camera frame timeout")
                time.sleep(0.001)
                continue

            last_frame_time = time.monotonic()

            # Preprocessing: resize, BGR->RGB, horizontal mirror
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.flip(frame, 1)  # Mirror

            # Write to SharedMemory (newest overwrites)
            np.copyto(frame_buf, frame)

        shm.close()

    def _disconnect(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _backoff_reconnect(self) -> None:
        if not self._running:
            return
        wait = self._backoff_times[min(self._backoff_idx, len(self._backoff_times) - 1)] / 1000
        logger.info("Reconnecting camera", wait_ms=wait * 1000)
        time.sleep(wait)
        self._backoff_idx = min(self._backoff_idx + 1, len(self._backoff_times) - 1)

    def stop(self) -> None:
        self._running = False
        self._disconnect()


def start_camera_process(config: dict, shm_name: str) -> mp.Process:
    """Spawn camera capture as a separate process."""
    stream = CameraStream(config, shm_name)
    process = mp.Process(target=stream.run, daemon=True, name="camera_capture")
    process.start()
    return process
```

### 2.2 LandmarkExtractor (`vision/landmark_extractor.py`)

```python
import numpy as np
import mediapipe as mp
from multiprocessing import shared_memory
import structlog
from models.data_types import Hand, Landmark3D

logger = structlog.get_logger(__name__)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_CHANNELS = 3
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS

class LandmarkExtractor:
    """Wraps MediaPipe Hands. Reads from SharedMemory, outputs project Hand dataclasses.
    MediaPipe objects NEVER leave this class."""

    def __init__(self, config: dict):
        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=config.get("engine", {}).get("max_hands", 2),
            min_detection_confidence=config.get("engine", {}).get("min_detection_confidence", 0.7),
            min_tracking_confidence=config.get("engine", {}).get("min_tracking_confidence", 0.5),
        )
        logger.info("MediaPipe Hands initialized")

    def extract(self, shm_name: str) -> list[Hand] | None:
        """Read frame from SharedMemory, extract landmarks, return list[Hand].
        Returns None if no hands detected."""
        try:
            shm = shared_memory.SharedMemory(name=shm_name)
            frame = np.ndarray(
                (FRAME_HEIGHT, FRAME_WIDTH, FRAME_CHANNELS),
                dtype=np.uint8,
                buffer=shm.buf,
            )
            rgb_frame = frame.copy()  # MediaPipe needs contiguous array
            shm.close()
        except FileNotFoundError:
            logger.warning("SharedMemory not found")
            return None

        results = self._hands.process(rgb_frame)
        if not results.multi_hand_landmarks:
            return None

        hands = []
        for hand_landmarks, handedness in zip(
            results.multi_hand_landmarks,
            results.multi_handedness,
        ):
            landmarks = tuple(
                Landmark3D(
                    x=lm.x,
                    y=lm.y,
                    z=lm.z,
                    visibility=lm.visibility if hasattr(lm, "visibility") else 1.0,
                )
                for lm in hand_landmarks.landmark
            )
            hand = Hand(
                landmarks=landmarks,
                handedness=handedness.classification[0].label,
                confidence=handedness.classification[0].score,
            )
            hands.append(hand)

        return hands

    def close(self) -> None:
        self._hands.close()
```

### 2.3 SharedMemory Setup in Engine

```python
# In core/engine.py — initialization
import multiprocessing as mp
from multiprocessing import shared_memory

class GestureEngine:
    def __init__(self, config_path: str | None = None):
        self._config = ConfigManager(config_path)
        self._event_bus = EventBus()

        # Create SharedMemory for frame passing
        FRAME_SIZE = 640 * 480 * 3
        self._frame_shm = shared_memory.SharedMemory(create=True, size=FRAME_SIZE)
        self._shm_name = self._frame_shm.name

        # Start camera process
        from vision.camera_stream import start_camera_process
        self._camera_process = start_camera_process(self._config._config, self._shm_name)

        # Initialize landmark extractor (runs in this process)
        from vision.landmark_extractor import LandmarkExtractor
        self._extractor = LandmarkExtractor(self._config._config)

    def _main_loop(self) -> None:
        import time
        while self._running:
            hands = self._extractor.extract(self._shm_name)
            if hands:
                # Pass to filter -> features -> FSM (M2, M3)
                pass
            time.sleep(0.001)  # ~1000 FPS max poll rate

    def shutdown(self) -> None:
        self._running = False
        self._camera_process.join(timeout=3)
        self._frame_shm.close()
        self._frame_shm.unlink()
```

---

## 3. Tests to Write for M0-M1

### M0 Tests:
- `tests/unit/test_data_types.py` — Hand creation with 21 landmarks, frozen dataclass, palm_center computation
- `tests/unit/test_event_bus.py` — subscribe/publish/unsubscribe, error in handler does not crash
- `tests/unit/test_config_manager.py` — load default, merge user override, schema validation error, get/set
- `tests/unit/test_config_ast_safety.py` — verify eval/exec are never called (grep the codebase)

### M1 Tests:
- `tests/unit/test_camera_stream.py` — test with mock VideoCapture, SharedMemory write, watchdog, reconnect
- `tests/unit/test_landmark_extractor.py` — mock MediaPipe results, verify Hand dataclass conversion, no MediaPipe objects leak
- `tests/integration/test_camera_to_landmarks.py` — Process A writes, Process B reads, landmarks produced

### SharedMemory conftest fixture:
```python
# tests/conftest.py
import pytest
import numpy as np
from multiprocessing import shared_memory

@pytest.fixture
def frame_shared_memory():
    shm = shared_memory.SharedMemory(create=True, size=640*480*3)
    yield shm.name
    shm.close()
    shm.unlink()

@pytest.fixture
def sample_rgb_frame():
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
```

---

## 4. Acceptance Criteria for M0

- [ ] Full directory structure created with all __init__.py files
- [ ] pyproject.toml passes `pip install -e .`
- [ ] `black --check`, `flake8`, `mypy --strict` all pass on the skeleton
- [ ] CI workflow runs lint + unit-tests on push
- [ ] Data models (Hand, Landmark3D, FeatureVector, GestureEvent) fully implemented with type hints
- [ ] EventBus subscribe/publish works
- [ ] ConfigManager loads YAML, validates schema, deep-merges user config
- [ ] default_config.yaml has all config keys from Section 9 of master plan

## 5. Acceptance Criteria for M1

- [ ] CameraStream runs as separate process
- [ ] Frame written to SharedMemory is valid RGB 640x480
- [ ] LandmarkExtractor reads from SharedMemory, returns list[Hand]
- [ ] MediaPipe objects (mp.HandLandmark etc) never appear outside landmark_extractor.py
- [ ] Camera disconnect triggers reconnect with exponential backoff
- [ ] Watchdog fires after 2s of no frames
- [ ] Integration test: camera process writes, main process reads landmarks
- [ ] Memory: no frame data persists after landmark extraction (verify with tracemalloc)
- [ ] All M0 + M1 tests pass
