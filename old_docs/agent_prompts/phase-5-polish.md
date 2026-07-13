# Phase 8-9 (M7-M8) — UI, Testing, Packaging & Release — AI Agent Prompt

**Milestones:** M7 (Full UI & Test Suite) + M8 (Release Prep)
**Duration:** Weeks 8-10
**Agent task:** Build the PyQt6 system tray, translucent overlay HUD, settings window; complete the full test suite; set up PyInstaller packaging for all 3 platforms; write ADRs; produce the first beta build.

**Depends on:** M6 (custom gestures working), M5 (plugins loaded), M4 (all OS controllers)

---

## 1. System Tray Icon (`gui/tray_icon.py`)

### Key Requirements
- QSystemTrayIcon with context menu: Pause/Resume, Camera Status, Settings, Quit
- Green/red icon indicating active/paused state
- Double-click opens settings
- Balloon notifications on camera disconnect/reconnect
- Subscribe to EventBus for camera status and gesture events
- Update tooltip with live FPS and gesture count

### Signals
```python
class TrayController(QObject):
    pause_toggled = pyqtSignal(bool)     # True = paused
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
```

### Implementation Notes
- Create tray icon programmatically (QPainter hand silhouette) — no external icon file dependency
- Pause action toggles a flag that the engine checks each frame
- Camera status updated via EventBus subscription to camera_disconnected/camera_recovered
- FPS/gesture stats updated via a QTimer polling the engine every 500ms

---

## 2. Overlay HUD (`gui/overlay.py`)

### 2.1 Window Properties

The overlay is a frameless, translucent, click-through QWidget that floats over all other windows.

```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient

class OverlayHUD(QWidget):
    """Translucent, click-through overlay showing gesture tracking visualization."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # Click-through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentMouseEvents)

        # Screen geometry — cover entire virtual desktop
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self._config = config
        self._hands: list[tuple] = []  # (landmarks, handedness, fsm_states)
        self._active_gesture: str | None = None
        self._action_feedback: str | None = None
        self._action_feedback_time: float = 0

    def set_hand_data(self, hands: list, fsm_states: dict | None = None):
        """Called from engine thread (via signal) with current hand tracking data."""
        self._hands = hands
        if fsm_states:
            for name, (state, progress) in fsm_states.items():
                if state not in ("Idle",):
                    self._active_gesture = name
        self.update()

    def show_action_feedback(self, gesture_name: str, action: str):
        """Flash action name on screen for confirmation_duration_ms."""
        self._action_feedback = f"{gesture_name}: {action}"
        self._action_feedback_time = time.monotonic()
        QTimer.singleShot(
            self._config.get("hud", {}).get("confirmation_duration_ms", 800),
            self._clear_feedback,
        )
        self.update()

    def _clear_feedback(self):
        self._action_feedback = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        hud_enabled = self._config.get("hud", {}).get("enabled", True)
        if not hud_enabled:
            return

        opacity = self._config.get("hud", {}).get("opacity", 0.3)
        painter.setOpacity(opacity)

        for landmarks, handedness in self._hands:
            self._draw_hand_skeleton(painter, landmarks)

        if self._action_feedback:
            self._draw_action_text(painter, self._action_feedback)

        if self._active_gesture:
            self._draw_progress_ring(painter, self._active_gesture)

    def _draw_hand_skeleton(self, painter: QPainter, landmarks):
        """Draw circles at each landmark and lines between connected joints."""
        if not self._config.get("hud", {}).get("show_tracking_points", True):
            return

        screen = self.geometry()
        painter.setPen(QPen(QColor(0, 255, 150, 200), 2))
        painter.setBrush(QBrush(QColor(0, 255, 150, 150)))

        # Connections (bone pairs)
        CONNECTIONS = [
            (0,1),(1,2),(2,3),(3,4),       # Thumb
            (0,5),(5,6),(6,7),(7,8),       # Index
            (0,9),(9,10),(10,11),(11,12),   # Middle (0->9 via 5 or 17)
            (0,13),(13,14),(14,15),(15,16), # Ring
            (0,17),(17,18),(18,19),(19,20), # Pinky
            (5,9),(9,13),(13,17),           # Palm
        ]

        points = [(int(lm.x * screen.width()), int(lm.y * screen.height())) for lm in landmarks]

        # Draw bones
        for i, j in CONNECTIONS:
            painter.drawLine(points[i][0], points[i][1], points[j][0], points[j][1])

        # Draw joints
        for px, py in points:
            painter.drawEllipse(QPointF(px, py), 4, 4)

    def _draw_action_text(self, painter: QPainter, text: str):
        """Show action confirmation text at bottom center of screen."""
        painter.setOpacity(0.8)
        painter.setPen(QPen(QColor(255, 255, 255, 230)))
        font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        painter.setFont(font)

        screen = self.geometry()
        rect = QRectF(screen.width() / 2 - 200, screen.height() - 120, 400, 50)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_progress_ring(self, painter: QPainter, gesture_name: str):
        """Draw a circular progress indicator showing FSM state progression."""
        if not self._config.get("hud", {}).get("show_progress_ring", True):
            return

        # Progress ring in bottom-right corner
        center_x = self.geometry().width() - 80
        center_y = self.geometry().height() - 80
        radius = 30

        painter.setPen(QPen(QColor(0, 200, 255, 150), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        # Progress arc (simplified — actual progress from FSM state)
        painter.setPen(QPen(QColor(0, 255, 150, 230), 6))
        rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawArc(rect, 90 * 16, -180 * 16)  # Half circle = half progress

        # Gesture name
        painter.setPen(QColor(255, 255, 255, 180))
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.drawText(QRectF(center_x - 50, center_y + radius + 5, 100, 20),
                         Qt.AlignmentFlag.AlignCenter, gesture_name)
```

### 2.2 High-DPI Scaling

```python
# In gui/app_entry.py, before creating QApplication:
import sys
if hasattr(Qt, "AA_EnableHighDpiScaling"):
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
if hasattr(Qt, "AA_UseHighDpiPixmaps"):
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

# Multi-monitor: overlay covers the primary monitor
# For multi-monitor, either:
# (a) Cover all virtual desktop: self.setGeometry(QApplication.primaryScreen().virtualGeometry())
# (b) Cover only primary: self.setGeometry(QApplication.primaryScreen().geometry())
# Default: (a) with a config option to switch
```

---

## 3. Settings Window (`gui/settings_window.py`)

### 3.1 Tab Structure

```
SettingsWindow (QDialog or QMainWindow)
  |- Tab: General
  |    - Camera device selection (dropdown)
  |    - Camera resolution (dropdown: 640x480, 1280x720, 1920x1080)
  |    - Target FPS (slider: 15, 30, 60)
  |    - Auto-reconnect toggle
  |    - Pause hotkey (key capture widget)
  |
  |- Tab: Sensitivity & Filtering
  |    - Global sensitivity multiplier (slider 0.1 - 3.0)
  |    - One-Euro min_cutoff (slider)
  |    - One-Euro beta (slider)
  |    - Dynamic adaptation toggles (lighting, depth)
  |
  |- Tab: Gestures
  |    - List of all gestures (tree: name, type, action, cooldown)
  |    - Toggle enable/disable per gesture
  |    - Edit gesture thresholds (expand to edit FSM states)
  |    - "Custom Gestures" button -> opens GestureRecorder dialog
  |    - Custom gestures list with delete button
  |
  |- Tab: App Profiles
  |    - Detected apps list
  |    - Select app -> show gesture-to-action mapping table
  |    - Edit/add/remove mappings
  |    - Import/export profile as JSON
  |
  |- Tab: HUD & Display
  |    - Enable/disable HUD overlay
  |    - Opacity slider
  |    - Show tracking points toggle
  |    - Show progress ring toggle
  |    - Show action confirmation toggle
  |    - Confirmation duration slider
  |
  |- Tab: Advanced
  |    - Logging level (dropdown)
  |    - Structured logging toggle
  |    - Log rotation (daily/weekly/size)
  |    - Max log files
  |    - Telemetry opt-in
  |    - Reset to defaults button
  |    - Open log directory button
  |    - Open config directory button
```

### 3.2 Config Change Flow

```python
class SettingsWindow(QDialog):
    config_changed = pyqtSignal(dict)

    def __init__(self, config_manager: "ConfigManager", parent=None):
        super().__init__(parent)
        self._config = config_manager
        self._setup_ui()
        self._load_current_config()

    def _load_current_config(self):
        """Populate all widgets from current config."""
        self._camera_device.setCurrentIndex(self._config.get("camera.device_id", 0))
        self._sensitivity_slider.setValue(
            int(self._config.get("sensitivity.global_multiplier", 1.0) * 100)
        )
        # ... etc for all settings

    def _on_apply(self):
        """Collect all widget values, write to user config, emit signal."""
        new_config = {
            "camera": {
                "device_id": self._camera_device.currentIndex(),
                "fps_target": self._fps_combo.currentData(),
            },
            "sensitivity": {
                "global_multiplier": self._sensitivity_slider.value() / 100.0,
            },
            # ... etc
        }
        self._config.set_bulk(new_config)
        self._config.save_user_config()
        self.config_changed.emit(new_config)
        logger.info("Settings applied", config=new_config)
```

### 3.3 Pause Hotkey Capture Widget

```python
class HotkeyCaptureWidget(QPushButton):
    """Button that captures the next key combination pressed."""
    hotkey_captured = pyqtSignal(str)

    def __init__(self, current_hotkey: str = "", parent=None):
        super().__init__(current_hotkey or "Click to capture...", parent)
        self._capturing = False
        self._modifiers = []
        self.clicked.connect(self._start_capture)

    def _start_capture(self):
        self._capturing = True
        self.setText("Press key combination...")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def keyPressEvent(self, event):
        if not self._capturing:
            return super().keyPressEvent(event)
        self._modifiers = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._modifiers.append("Ctrl")
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._modifiers.append("Shift")
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._modifiers.append("Alt")
        if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            self._modifiers.append("Super")
        key = event.text() or event.key()
        if not self._modifiers and not event.text():
            return  # Ignore modifier-only presses

        hotkey = "+".join(self._modifiers + [str(key)])
        self.setText(hotkey)
        self._capturing = False
        self.hotkey_captured.emit(hotkey)
```

---

## 4. App Entry Point (`gui/app_entry.py`)

```python
import sys
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import structlog

logger = structlog.get_logger(__name__)

class GestureControllerApp:
    def __init__(self, config_path: str | None = None):
        # Enable high-DPI
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)  # Tray keeps app alive

        # Initialize engine
        from core.engine import GestureEngine
        from core.event_bus import EventBus
        from core.config_manager import ConfigManager

        self._config = ConfigManager(config_path)
        self._event_bus = EventBus()
        self._engine = GestureEngine(self._config, self._event_bus)

        # Initialize GUI components
        from gui.tray_icon import TrayController
        from gui.overlay import OverlayHUD
        from gui.settings_window import SettingsWindow

        self._tray = TrayController(self._event_bus)
        self._overlay = OverlayHUD(self._config._config)
        self._settings = SettingsWindow(self._config)

        # Wire signals
        self._tray.pause_toggled.connect(self._engine.set_paused)
        self._tray.settings_requested.connect(self._settings.show)
        self._tray.quit_requested.connect(self._shutdown)
        self._settings.config_changed.connect(self._on_config_changed)

        # Engine -> GUI bridge (engine runs in main process, uses QTimer for polling)
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_engine)
        self._poll_timer.start(16)  # ~60 FPS GUI update rate

        # Show tray
        self._tray.show()
        self._overlay.show()

        logger.info("Gesture Controller started")

    def _poll_engine(self):
        """Bridge: get latest data from engine, push to GUI."""
        hands = self._engine.get_current_hands()
        if hands:
            self._overlay.set_hand_data(hands, self._engine.get_fsm_states())
        fps = self._engine.get_fps()
        self._tray.update_status(fps, self._engine.get_gesture_count())

    def _on_config_changed(self, new_config: dict):
        self._event_bus.publish("config_changed", new_config)
        self._engine.reload_config()

    def _shutdown(self):
        logger.info("Shutting down")
        self._engine.shutdown()
        self._app.quit()

    def run(self):
        signal.signal(signal.SIGINT, lambda *_: self._shutdown())
        return self._app.exec()

def main():
    app = GestureControllerApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()
```

---

## 5. PyInstaller Packaging

### 5.1 Spec File (`gesture_controller.spec`)

```python
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "data"), "data"),
        (str(project_root / "gui" / "resources"), "gui/resources") if (project_root / "gui" / "resources").exists() else None,
    ],
    hiddenimports=[
        "mediapipe",
        "numpy",
        "PyQt6",
        "yaml",
        "jsonschema",
        "structlog",
        "numba",
        "evdev",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "scipy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GestureController",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "packaging" / "icon.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GestureController",
)
```

### 5.2 Platform-Specific Packaging

**Windows (.exe via NSIS):**
```bash
pyinstaller gesture_controller.spec --distpath dist/windows
makensis packaging/windows_installer.nsi
# Output: GestureController-Setup-0.1.0.exe
```

**macOS (.app via DMG):**
```bash
pyinstaller gesture_controller.spec --distpath dist/macos --windowed
# Create .app bundle manually or via py2app
hdiutil create -volname "Gesture Controller" -srcfolder dist/macos/GestureController.app -ov GestureController.dmg
# Output: GestureController.dmg
```

**Linux (deb/rpm):**
```bash
pyinstaller gesture_controller.spec --distpath dist/linux
# Use fpm to create packages
fpm -s dir -t deb -n gesture-controller -v 0.1.0 --description "Hand gesture desktop controller" dist/linux/=/opt/gesture-controller/
# Also create udev rules package
fpm -s dir -t deb -n gesture-controller-udev -v 0.1.0 packaging/99-gesture-controller-uinput.rules=/etc/udev/rules.d/99-gesture-controller-uinput.rules
```

### 5.3 Install Size Budget

| Component | Budget |
|---|---|
| Python runtime + stdlib | ~30 MB |
| MediaPipe models + lib | ~15 MB |
| PyQt6 | ~40 MB |
| NumPy + Numba | ~20 MB |
| OpenCV | ~15 MB |
| App code + data | ~2 MB |
| **Total compressed** | **< 80 MB** |
| **Total installed** | **< 150 MB** |

### 5.4 Post-Install Verification Script

```python
# scripts/verify_install.py
"""Run after installation to verify everything works."""
import sys

def check_imports():
    try:
        import cv2, mediapipe, numpy, PyQt6, yaml, jsonschema, structlog
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False

def check_camera():
    import cv2
    cap = cv2.VideoCapture(0)
    ok = cap.isOpened()
    cap.release()
    return ok

def check_mediapipe():
    import mediapipe as mp
    hands = mp.solutions.hands
    return hands is not None

def check_config():
    from pathlib import Path
    import yaml
    config_path = Path(__file__).parent / "data" / "default_config.yaml"
    return config_path.exists() and yaml.safe_load(open(config_path))

def main():
    checks = [
        ("Dependencies", check_imports),
        ("Camera", check_camera),
        ("MediaPipe", check_mediapipe),
        ("Config", check_config),
    ]
    all_ok = True
    for name, fn in checks:
        try:
            ok = fn()
            status = "OK" if ok else "FAIL"
            if not ok:
                all_ok = False
            print(f"  [{status}] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            all_ok = False
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## 6. ADRs to Write (M8)

Write these in `adr/` directory as `adr/NNNN-title.md` using the [ADR format](https://adr.github.io/):

| # | Title | Status | Key Decision |
|---|---|---|---|
| 001 | Multiprocessing over Threading | Accepted | SharedMemory bypasses GIL, single-slot for freshness |
| 002 | PyQt6 over Electron | Accepted | Native tray, no Chromium overhead, smaller binary |
| 003 | FSM over ML Classification | Accepted | Deterministic, no false positives from single frames |
| 004 | AST Condition Parsing | Accepted | No eval/exec, safe user-configurable conditions |
| 005 | pyautogui with SendInput Upgrade Path | Accepted | Start simple, upgrade if latency requires |
| 006 | In-Process EventBus over IPC | Accepted | Gerik proved WebSocket IPC causes latency |
| 007 | /dev/uinput for Linux Wayland | Accepted | X11 fallback for legacy compositors |
| 008 | DTW for Custom Gestures | Accepted | Numba-compiled, template averaging from 3 examples |
| 009 | Privacy by Design | Accepted | No cloud, no frame storage, telemetry opt-in |
| 010 | Plugin System with Hot Reload | Accepted | watchdog-based file watching, schema validation |

---

## 7. Tests for M7-M8

### M7 (UI) Tests:
- `tests/unit/test_tray_icon.py` — pause toggle, settings signal, quit signal, camera status update
- `tests/unit/test_overlay.py` — paint with hand data, paint without data, opacity config
- `tests/unit/test_settings_window.py` — load config, apply changes, emit config_changed
- `tests/unit/test_hotkey_capture.py` — capture single key, capture combo, release capture

### M8 (Packaging) Tests:
- `tests/integration/test_full_pipeline.py` — Start app, verify tray appears, verify overlay renders
- `tests/integration/test_install_verification.py` — Run verify_install.py, all checks pass
- `tests/e2e/test_minimize_gesture.py` — Full E2E with virtual camera

### Test Coverage:
- Run `pytest --cov=gesture_controller --cov-report=html`
- Target: >= 80% overall, >= 90% for core/, vision/, models/
- Generate coverage badge for README

---

## 8. Acceptance Criteria for M7

- [ ] System tray icon shows on all 3 platforms
- [ ] Pause/Resume works via tray menu
- [ ] Settings window opens with all 6 tabs populated
- [ ] Config changes in settings persist after restart
- [ ] Overlay HUD renders hand skeleton on screen
- [ ] Action confirmation text flashes on gesture trigger
- [ ] Progress ring shows during gesture FSM progression
- [ ] Overlay is click-through (does not block mouse events)
- [ ] High-DPI scaling works (test on 150% and 200% displays)
- [ ] Pause hotkey works (Win+Shift+G, Cmd+Shift+G)
- [ ] All UI tests pass

## 9. Acceptance Criteria for M8

- [ ] PyInstaller builds successfully on Windows, macOS, Linux
- [ ] Installed app starts in < 2 seconds
- [ ] All 3 MVP gestures work on packaged app (not just dev mode)
- [ ] Camera auto-reconnect works on packaged app
- [ ] udev rules file included in Linux package
- [ ] macOS Accessibility permission prompt works
- [ ] 10 ADRs written in adr/ directory
- [ ] verify_install.py passes all checks
- [ ] Install size < 150 MB on all platforms
- [ ] All E2E tests pass on at least one platform
- [ ] CHANGELOG.md updated with v0.1.0-beta.1 entries
