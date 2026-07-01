# Phase 6-7 (M5-M6) — Plugins, Config & Custom Gestures — AI Agent Prompt

**Milestones:** M5 (Plugins & Config System) + M6 (Custom Gestures & DTW)
**Duration:** Weeks 6-8
**Agent task:** Build the plugin discovery/hot-reload system, complete the YAML config schema with app profiles, implement the gesture recorder UI, and build the Numba-compiled DTW matcher for user-defined custom gestures.

**Depends on:** M4 (cross-platform OS adapters working), M3 (FSM engine with 3 MVP gestures)

---

## 1. Plugin System Architecture

### 1.1 Plugin Interface (Contract)

Every plugin is a Python file in the `plugins/` directory (or `~/.config/gesture_controller/plugins/` for user plugins). Each plugin file must define:

```python
# plugins/builtin/media_gestures.py  (example)

PLUGIN_SCHEMA = {
    "type": "object",
    "required": ["name", "version", "gestures"],
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "gestures": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "states"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["static", "dynamic", "continuous"]},
                    "priority": {"type": "integer", "minimum": 1},
                    "states": {"type": "array"},
                },
            },
        },
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "handler"],
                "properties": {
                    "name": {"type": "string"},
                    "handler": {"type": "string"},
                },
            },
        },
    },
}

# Plugin metadata dict — MUST be present
PLUGIN_META = {
    "name": "media-gestures",
    "version": "1.0.0",
    "description": "Media playback gestures: play/pause, volume, next/prev",
    "author": "gesture-controller-core",
}

# Gesture definitions in the same FSM YAML schema format as predefined_gestures.yaml
GESTURE_DEFINITIONS = [
    {
        "name": "ThumbsUp",
        "type": "static",
        "priority": 10,
        "states": [
            {"id": "Idle", "transitions": [
                {"to": "ThumbUpPose", "condition": "thumb_extended == True and index_extended == False and middle_extended == False"},
            ]},
            {"id": "ThumbUpPose", "min_duration_ms": 200, "max_duration_ms": 2000, "transitions": [
                {"to": "Trigger", "condition": "True"},  # auto-trigger after min_duration
                {"to": "Idle", "condition": "thumb_extended == False", "abort": True},
            ]},
            {"id": "Trigger", "is_terminal": True, "action": "Media:PlayPause", "cooldown_ms": 1000},
        ],
    },
    # VolumeUp, VolumeDown, Next, Previous follow same pattern
]

# Optional: custom action handlers for actions not covered by BaseController
ACTION_HANDLERS = {
    # "CustomAction:MyThing": my_custom_handler_function,
}
```

### 1.2 Plugin Discovery (`plugins/plugin_loader.py`)

```python
import importlib.util
import jsonschema
import os
import sys
import time
import structlog
from pathlib import Path
from typing import Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = structlog.get_logger(__name__)

PLUGIN_DIRS = [
    Path(__file__).parent / "builtin",          # Built-in plugins
    Path(__file__).parent.parent / "data" / "plugins",  # Bundled plugins
]

# User plugin directory (per-platform)
import platform
if platform.system() == "Windows":
    USER_PLUGIN_DIR = Path(os.environ.get("APPDATA", "")) / "gesture_controller" / "plugins"
elif platform.system() == "Darwin":
    USER_PLUGIN_DIR = Path.home() / "Library" / "Application Support" / "gesture_controller" / "plugins"
else:
    USER_PLUGIN_DIR = Path.home() / ".config" / "gesture_controller" / "plugins"

PLUGIN_DIRS.append(USER_PLUGIN_DIR)

class PluginLoadError(Exception):
    def __init__(self, plugin_path: str, reason: str):
        self.plugin_path = plugin_path
        self.reason = reason
        super().__init__(f"Failed to load plugin {plugin_path}: {reason}")

class Plugin:
    """Loaded plugin wrapper."""
    def __init__(self, path: Path, module: Any, meta: dict, gestures: list[dict], actions: dict):
        self.path = path
        self.module = module
        self.meta = meta
        self.gestures = gestures
        self.actions = actions
        self.loaded_at = time.monotonic()

class PluginLoader:
    """Discovers, validates, and manages gesture/action plugins."""

    def __init__(self, event_bus: "EventBus", schema: dict | None = None):
        self._event_bus = event_bus
        self._plugins: dict[str, Plugin] = {}
        self._schema = schema or self._default_schema()
        self._observer: Observer | None = None

    def _default_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name", "version"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "version": {"type": "string"},
            },
        }

    def discover_all(self) -> list[Plugin]:
        """Scan all plugin directories, load valid plugins."""
        plugins = []
        seen_names = set()

        for plugin_dir in PLUGIN_DIRS:
            if not plugin_dir.exists():
                continue
            for py_file in sorted(plugin_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                try:
                    plugin = self._load_plugin(py_file)
                    if plugin.meta["name"] in seen_names:
                        logger.warning("Duplicate plugin name, skipping", name=plugin.meta["name"], path=str(py_file))
                        continue
                    seen_names.add(plugin.meta["name"])
                    plugins.append(plugin)
                except PluginLoadError as e:
                    logger.warning("Plugin load failed", path=str(py_file), reason=e.reason)

        self._plugins = {p.meta["name"]: p for p in plugins}
        logger.info("Plugins loaded", count=len(plugins), names=[p.meta["name"] for p in plugins])
        return plugins

    def _load_plugin(self, path: Path) -> Plugin:
        """Load a single plugin file."""
        spec = importlib.util.spec_from_file_location(path.stem, str(path))
        if spec is None or spec.loader is None:
            raise PluginLoadError(str(path), "Cannot create module spec")

        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module  # Allow relative imports

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise PluginLoadError(str(path), f"Import error: {e}")

        # Validate required attributes
        if not hasattr(module, "PLUGIN_META"):
            raise PluginLoadError(str(path), "Missing PLUGIN_META")

        meta = module.PLUGIN_META
        jsonschema.validate(meta, self._schema)

        gestures = getattr(module, "GESTURE_DEFINITIONS", [])
        actions = getattr(module, "ACTION_HANDLERS", {})

        return Plugin(path=path, module=module, meta=meta, gestures=gestures, actions=actions)

    def start_hot_reload(self) -> None:
        """Watch plugin directories for changes, auto-reload on file modification."""
        class PluginFileHandler(FileSystemEventHandler):
            def __init__(self, loader: "PluginLoader"):
                self.loader = loader

            def on_modified(self, event):
                if event.src_path.endswith(".py") and not Path(event.src_path).name.startswith("_"):
                    logger.info("Plugin file modified, reloading", path=event.src_path)
                    try:
                        plugin = self.loader._load_plugin(Path(event.src_path))
                        self.loader._plugins[plugin.meta["name"]] = plugin
                        self.loader._event_bus.publish("plugin_reloaded", plugin.meta["name"])
                    except PluginLoadError as e:
                        logger.error("Hot reload failed", path=event.src_path, reason=e.reason)

        self._observer = Observer()
        handler = PluginFileHandler(self)
        for plugin_dir in PLUGIN_DIRS:
            if plugin_dir.exists():
                self._observer.schedule(handler, str(plugin_dir), recursive=False)
        self._observer.start()
        logger.info("Hot reload watcher started")

    def stop_hot_reload(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)

    def get_all_gestures(self) -> list[dict]:
        """Collect gesture definitions from all plugins."""
        gestures = []
        for plugin in self._plugins.values():
            gestures.extend(plugin.gestures)
        return gestures

    def get_action_handler(self, action_name: str) -> Any | None:
        """Find a custom action handler across all plugins."""
        for plugin in self._plugins.values():
            if action_name in plugin.actions:
                return plugin.actions[action_name]
        return None
```

### 1.3 Plugin Schema Validation

Each plugin's GESTURE_DEFINITIONS must conform to the same JSON schema used for `predefined_gestures.yaml`. The schema file lives at `data/gesture_schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "type", "states"],
  "properties": {
    "name": {"type": "string"},
    "type": {"type": "string", "enum": ["static", "dynamic", "continuous"]},
    "priority": {"type": "integer", "minimum": 1},
    "thresholds": {"type": "object"},
    "states": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id"],
        "properties": {
          "id": {"type": "string"},
          "is_terminal": {"type": "boolean"},
          "min_duration_ms": {"type": "number", "minimum": 0},
          "max_duration_ms": {"type": "number"},
          "cooldown_ms": {"type": "number", "minimum": 0},
          "action": {"type": "string"},
          "transitions": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["to", "condition"],
              "properties": {
                "to": {"type": "string"},
                "condition": {"type": "string"},
                "abort": {"type": "boolean"}
              }
            }
          }
        }
      }
    }
  }
}
```

### 1.4 Built-in Plugins to Implement

**`plugins/builtin/media_gestures.py`:**
- ThumbsUp -> Media:PlayPause (cooldown 1000ms)
- (Future: two-finger swipe up -> Volume Up, two-finger swipe down -> Volume Down)

**`plugins/builtin/window_gestures.py`:**
- (These are already in predefined_gestures.yaml as MVP, but the plugin format allows overriding)
- OpenPalm -> OS:ShowDesktop (cooldown 1500ms)
- PeaceSign -> Configurable (cooldown 800ms)

---

## 2. App-Specific Profile System

### 2.1 Profile Loading

App profiles are defined in `data/predefined_gestures.yaml` under `app_profiles:` and in user config. The ActionDispatcher resolves them at runtime.

```python
# In os_integration/action_dispatcher.py

class ActionDispatcher:
    def __init__(self, config: "ConfigManager", controller: "BaseController", event_bus: "EventBus"):
        self._config = config
        self._controller = controller
        self._profiles = self._load_profiles()

    def _load_profiles(self) -> dict[str, dict[str, str]]:
        """Load app_profiles from gesture config file."""
        gestures_path = Path(__file__).parent.parent / "data" / "predefined_gestures.yaml"
        if not gestures_path.exists():
            return {}
        with open(gestures_path) as f:
            data = yaml.safe_load(f)
        return data.get("app_profiles", {})

    def resolve_action(self, gesture_event: GestureEvent) -> str:
        """Check app-specific profile, return resolved action string."""
        if not self._config.get("profiles.auto_detect_app", True):
            return gesture_event.action

        foreground = self._controller.get_foreground_app()
        if not foreground:
            return gesture_event.action

        # Check exact match first
        if foreground in self._profiles:
            profile = self._profiles[foreground]
            if gesture_event.gesture_name in profile:
                return profile[gesture_event.gesture_name]

        # Check _default profile
        if "_default" in self._profiles:
            default = self._profiles["_default"]
            if gesture_event.gesture_name in default:
                return default[gesture_event.gesture_name]

        return gesture_event.action
```

### 2.2 Profile Editor in Settings UI

The settings window (M7/M8) will include a profile manager where users can:
- See detected foreground apps
- Map gestures to custom actions per app
- Add new profile entries
- Export/import profiles as JSON

For now, the backend logic is what matters. The UI is a later concern.

---

## 3. Custom Gesture System (M6)

### 3.1 DTW Matcher (`models/dtw_matcher.py`)

Full Numba-compiled implementation — see `gesture_spec.md` Section 7.3 for the exact code. Key points the agent must implement:

- `dtw_distance(a, b)` — Numba @njit, fastmath=True, 2-row cost matrix for memory efficiency
- `dtw_distance_batch(query, templates, thresholds)` — Compare one buffer against all templates
- `CustomGestureMatcher` class:

```python
class CustomGestureMatcher:
    def __init__(self, config: dict):
        self._templates: dict[str, dict] = {}  # name -> {"template": np.ndarray, "threshold": float, "action": str}
        self._buffer: np.ndarray = np.zeros((60, 63), dtype=np.float64)
        self._buffer_idx: int = 0
        self._buffer_full: bool = False
        self._frame_count: int = 0

    def load_templates(self, template_dir: Path) -> None:
        """Load all .json templates from data/custom_templates/."""
        for path in template_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
            template = np.array(data["template"], dtype=np.float64)
            self._templates[data["name"]] = {
                "template": template,
                "threshold": data.get("threshold", 0.15),
                "action": data["action"],
            }
        logger.info("Custom gesture templates loaded", count=len(self._templates))

    def update_buffer(self, hand: Hand) -> None:
        """Add current frame to rolling buffer. Buffer is in hand-centric coords."""
        normalized = to_hand_frame(hand.landmarks, hand.handedness)
        flat = np.array([l.x for l in normalized] + [l.y for l in normalized] + [l.z for l in normalized])
        self._buffer[self._buffer_idx] = flat
        self._buffer_idx = (self._buffer_idx + 1) % 60
        self._frame_count += 1
        if self._frame_count >= 60:
            self._buffer_full = True

    def match(self) -> GestureEvent | None:
        """Compare rolling buffer against all templates. Return best match or None."""
        if not self._buffer_full or not self._templates:
            return None

        # Reorder buffer: oldest first
        if self._buffer_idx == 0:
            query = self._buffer
        else:
            query = np.roll(self._buffer, -self._buffer_idx, axis=0)

        template_names = list(self._templates.keys())
        template_arrays = np.array([self._templates[n]["template"] for n in template_names])
        threshold_array = np.array([self._templates[n]["threshold"] for n in template_names])

        best_idx, best_dist = dtw_distance_batch(query, template_arrays, threshold_array)

        if best_idx >= 0:
            name = template_names[best_idx]
            return GestureEvent(
                gesture_name=name,
                gesture_type="custom",
                action=self._templates[name]["action"],
                confidence=1.0 - best_dist,
                hand="Right",
                timestamp=time.time(),
                gesture_source="dtw",
            )
        return None
```

### 3.2 Gesture Recorder UI (`gui/gesture_recorder.py`)

Built with PyQt6. Key components:

```python
class GestureRecorder(QDialog):
    """Dialog for recording custom gestures."""

    recording_complete = pyqtSignal(dict)  # Emits template data

    def __init__(self, parent=None, landmark_callback=None):
        super().__init__(parent)
        self._landmark_callback = landmark_callback  # Called to get current Hand from engine
        self._recordings: list[list[np.ndarray]] = []
        self._is_recording = False
        self._current_recording: list[np.ndarray] = []
        self._required_examples = 3
        self._frames_per_example = 60
        self._fps = 30
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Record Custom Gesture")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)

        # Name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Gesture Name:"))
        self._name_input = QLineEdit()
        name_layout.addWidget(self._name_input)
        layout.addLayout(name_layout)

        # Action input
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel("Action:"))
        self._action_input = QLineEdit()
        self._action_input.setPlaceholderText("e.g. KeyPress:Space")
        action_layout.addWidget(self._action_input)
        layout.addLayout(action_layout)

        # Recording progress
        self._progress_label = QLabel("Recordings: 0 / 3")
        self._progress_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._progress_label)

        # Visual feedback area
        self._canvas = GestureCanvas()  # Custom widget showing live hand skeleton
        layout.addWidget(self._canvas)

        # Record button
        self._record_btn = QPushButton("Start Recording (3s countdown)")
        self._record_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self._record_btn)

        # Threshold slider
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("DTW Threshold:"))
        self._threshold_slider = QSlider(Qt.Horizontal)
        self._threshold_slider.setRange(5, 50)
        self._threshold_slider.setValue(15)
        self._threshold_label = QLabel("0.15")
        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_label.setText(f"{v/100:.2f}")
        )
        thresh_layout.addWidget(self._threshold_slider)
        thresh_layout.addWidget(self._threshold_label)
        layout.addLayout(thresh_layout)

        # Save / Cancel
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Gesture")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_record_clicked(self):
        """Start a 3-second countdown, then record 2 seconds of landmarks."""
        self._record_btn.setEnabled(False)
        self._record_btn.setText("Get ready...")

        # Countdown timer
        self._countdown = 3
        self._timer = QTimer()
        self._timer.timeout.connect(self._countdown_tick)
        self._timer.start(1000)

    def _countdown_tick(self):
        self._countdown -= 1
        if self._countdown > 0:
            self._record_btn.setText(f"Recording in {self._countdown}...")
        else:
            self._timer.stop()
            self._start_recording()

    def _start_recording(self):
        self._is_recording = True
        self._current_recording = []
        self._record_btn.setText("Recording... (2 seconds)")
        self._record_timer = QTimer()
        self._record_timer.timeout.connect(self._capture_frame)
        self._record_timer.start(int(1000 / self._fps))

        # Auto-stop after 2 seconds
        QTimer.singleShot(2000, self._stop_recording)

    def _capture_frame(self):
        hand = self._landmark_callback()  # Get current Hand from engine
        if hand:
            landmarks = to_hand_frame(hand.landmarks, hand.handedness)
            flat = np.array([l.x for l in landmarks] + [l.y for l in landmarks] + [l.z for l in landmarks])
            self._current_recording.append(flat)
            self._canvas.update_hand(landmarks)

    def _stop_recording(self):
        self._is_recording = False
        self._record_timer.stop()
        if len(self._current_recording) >= 10:  # Minimum viable recording
            self._recordings.append(self._current_recording)
            self._progress_label.setText(
                f"Recordings: {len(self._recordings)} / {self._required_examples}"
            )
        self._record_btn.setEnabled(len(self._recordings) < self._required_examples)
        if self._recordings:
            self._record_btn.setText(
                f"Record Another ({self._required_examples - len(self._recordings)} remaining)"
            )
        else:
            self._record_btn.setText("Start Recording")

    def _on_save(self):
        if len(self._recordings) < self._required_examples:
            QMessageBox.warning(self, "Not Enough Recordings",
                f"Need {self._required_examples} recordings, have {len(self._recordings)}")
            return

        name = self._name_input.text().strip()
        action = self._action_input.text().strip()
        if not name or not action:
            QMessageBox.warning(self, "Missing Info", "Name and action are required")
            return

        # Normalize and average the recordings into a template
        normalized = [normalize_sequence(rec) for rec in self._recordings]
        template = np.mean(normalized, axis=0).tolist()

        threshold = self._threshold_slider.value() / 100.0

        template_data = {
            "version": "1.0",
            "name": name,
            "action": action,
            "hand": "Right",
            "threshold": threshold,
            "recorded_at": datetime.utcnow().isoformat() + "Z",
            "examples": [n.tolist() for n in normalized],
            "template": template,
        }

        self.recording_complete.emit(template_data)
        self.accept()
```

### 3.3 Template Management

Templates stored in user config directory:
```
~/.config/gesture_controller/custom_templates/
  my_wave.json
  thumbs_down.json
  circle_gesture.json
```

On app startup, CustomGestureMatcher.load_templates() scans this directory.
On save from recorder, template is written here.
On delete from settings UI, file is removed.
Changes are picked up by a filesystem watcher (or on next restart).

---

## 4. Tests for M5-M6

### M5 (Plugins) Tests:
- `tests/unit/test_plugin_loader.py`:
  - Load a valid plugin with PLUGIN_META and GESTURE_DEFINITIONS
  - Reject plugin missing PLUGIN_META
  - Reject plugin with invalid schema
  - Skip _prefixed files
  - Handle duplicate plugin names
  - Hot reload: modify file, verify plugin_reloaded event
  - get_all_gestures() merges from all plugins

- `tests/unit/test_plugin_schema.py`:
  - Validate gesture definition against JSON schema
  - Reject gesture missing required fields
  - Reject invalid state transition

- `tests/integration/test_plugin_discovery.py`:
  - Drop .py file in plugin dir -> discover -> validate -> appears in engine

### M6 (Custom Gestures) Tests:
- `tests/unit/test_dtw_matcher.py`:
  - Identical sequences return distance 0
  - Different sequences return distance > threshold
  - dtw_distance_batch returns correct index
  - Numba compilation succeeds
  - Empty buffer returns None from match()
  - Full buffer with no templates returns None

- `tests/unit/test_gesture_recorder.py`:
  - UI creation, countdown, recording flow (Qt test)
  - Save with insufficient recordings shows warning
  - Save produces valid JSON template

- `tests/integration/test_custom_gesture_flow.py`:
  - Record a gesture -> save template -> load template -> match same gesture

---

## 5. Acceptance Criteria for M5

- [ ] PluginLoader discovers and loads all .py files in plugin directories
- [ ] Invalid plugins are logged and skipped (no crash)
- [ ] GESTURE_DEFINITIONS from plugins are merged into the FSM engine
- [ ] Hot reload works: modify plugin file, new gestures appear without restart
- [ ] Plugin schema validation catches malformed gesture definitions
- [ ] App profiles resolve correctly per foreground application
- [ ] User can add custom profile entries in settings
- [ ] All plugin tests pass

## 6. Acceptance Criteria for M6

- [ ] DTW distance computes correctly (identical=0, orthogonal=high)
- [ ] Numba JIT compilation succeeds on first call
- [ ] Rolling 60-frame buffer fills and wraps correctly
- [ ] CustomGestureMatcher.match() returns GestureEvent when buffer matches template
- [ ] Gesture recorder UI: countdown, record, save, cancel all work
- [ ] Saved template JSON is valid and loadable
- [ ] Recording 3 examples and averaging produces a usable template
- [ ] DTW threshold is adjustable per gesture
- [ ] Template files can be added/removed from custom_templates/ directory
- [ ] All custom gesture tests pass
