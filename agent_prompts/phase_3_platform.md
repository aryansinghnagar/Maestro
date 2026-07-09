# Phase 5 (M4) — Cross-Platform OS Integration — AI Agent Prompt

**Milestone:** M4 Cross-Platform Adapters
**Depends on:** M3 (FSM engine working on Windows with pyautogui)
**Agent task:** Implement macOS and Linux OS controllers behind the BaseController ABC. The Windows controller already exists; you are adding platform parity.

---

## 1. What Already Exists When You Start

- `os_integration/base_controller.py` — Abstract base class with the full interface
- `os_integration/windows_controller.py` — Working Windows implementation using pyautogui
- `os_integration/action_dispatcher.py` — Routes GestureEvent to controller method
- `core/event_bus.py` — Pub/sub for events
- All tests in `tests/unit/` and `tests/integration/` passing for Windows

Your job: create `macos_controller.py` and `linux_controller.py` that pass the same integration tests.

---

## 2. BaseController ABC (Reference — DO NOT MODIFY)

```python
# os_integration/base_controller.py
from abc import ABC, abstractmethod
from typing import Optional

class BaseController(ABC):
    @abstractmethod
    def key_press(self, key: str, modifiers: list[str] | None = None) -> None: ...

    @abstractmethod
    def key_release(self, key: str) -> None: ...

    @abstractmethod
    def key_combo(self, keys: list[str]) -> None:
        """Press multiple keys simultaneously, then release all."""
        ...

    @abstractmethod
    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None: ...

    @abstractmethod
    def mouse_double_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None: ...

    @abstractmethod
    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None: ...

    @abstractmethod
    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None: ...

    @abstractmethod
    def get_foreground_app(self) -> str:
        """Return the process name of the current foreground window."""
        ...

    @abstractmethod
    def minimize_active_window(self) -> None: ...

    @abstractmethod
    def switch_window(self) -> None: ...

    @abstractmethod
    def show_desktop(self) -> None: ...

    @abstractmethod
    def media_play_pause(self) -> None: ...

    @abstractmethod
    def media_next(self) -> None: ...

    @abstractmethod
    def media_previous(self) -> None: ...

    @abstractmethod
    def media_volume_up(self) -> None: ...

    @abstractmethod
    def media_volume_down(self) -> None: ...

    @abstractmethod
    def is_supported(self) -> bool:
        """Return True if this platform adapter can run on the current OS."""
        ...
```

---

## 3. MacOSController Implementation

### 3.1 File: `os_integration/macos_controller.py`

Dependencies: `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices`

Key APIs you will use:

**Window management (Quartz/CoreGraphics):**
- `Quartz.CGWindowListCopyWindowInfo` — get window list with process names
- `Quartz.CGWindowListCreateImage` — capture window (not needed here but good to know)
- `ApplicationServices.NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()` — foreground app name
- `ApplicationServices.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()` — PID

**Input injection (Quartz/CoreGraphics):**
- `Quartz.CGEventCreateKeyboardEvent(None, keycode, True)` — key down
- `Quartz.CGEventCreateKeyboardEvent(None, keycode, False)` — key up
- `Quartz.CGEventSetFlags(event, flags)` — modifiers (Cmd, Shift, Ctrl, Alt)
- `Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)` — inject event
- `Quartz.CGEventCreateMouseEvent(None, type, point, button)` — mouse events
- `Quartz.CGEventCreateScrollWheelEvent(None, units, count, delta)` — scroll

**Accessibility (ApplicationServices/AXUIElement):**
- `ApplicationServices.AXUIElementCreateApplication(pid)` — get app element
- `ApplicationServices.AXUIElementCopyAttributeValue(element, kAXMinimizeButtonAttribute, ...)` — minimize button
- `ApplicationServices.AXUIElementPerformAction(element, kAXPressAction)` — click the minimize button

**Key code mapping (macOS virtual keycodes):**
```python
MAC_KEYCODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05, "z": 0x06,
    "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E,
    "r": 0x0F, "y": 0x10, "t": 0x11, "return": 0x24, "escape": 0x35, "space": 0x31,
    "tab": 0x30, "delete": 0x33, "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60, "f6": 0x61,
    "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
}

MAC_MODIFIER_FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate,
}
```

**Media keys (macOS uses special keycodes):**
```python
MAC_MEDIA_KEYCODES = {
    "play_pause": 0x00B0,  # NX_KEYTYPE_PLAY
    "next": 0x00B3,         # NX_KEYTYPE_FAST
    "previous": 0x00B2,    # NX_KEYTYPE_REWIND
    "volume_up": 0x00B5,   # NX_KEYTYPE_SOUND_UP
    "volume_down": 0x00B6, # NX_KEYTYPE_SOUND_DOWN
}

# Media keys on macOS require posting to a specific HID tap
def _post_media_key(keycode: int) -> None:
    # NSEvent.otherEventWithType with type 10 (NSSystemDefined)
    # Construct event with (0xA << 16) | (0x40 << 8) | keycode
    # This is the standard way to inject media keys on macOS
    pass
```

### 3.2 Implementation Details

**`minimize_active_window()`:**
```
1. Get frontmost application PID via NSWorkspace
2. Create AXUIElement for that application
3. Get the AXWindow attribute
4. Get the kAXMinimizeButtonAttribute
5. Perform kAXPressAction on it
6. Fall back to: CGEventPost Cmd+M if accessibility fails
```

**`switch_window()`:**
```
1. Use CGEventPost Cmd+Tab (keycode 0x30 with kCGEventFlagMaskCommand)
2. Alternatively: enumerate windows via CGWindowListCopyWindowInfo, find next window, AXUIElement raise
3. Cmd+Tab approach is simpler but may trigger app switcher UI briefly
4. Preference: use CGWindowListCopyWindowInfo + AXUIElementSetAttributeValue(kAXRaisedAttribute) for cleaner switch
```

**`show_desktop()`:**
```
1. CGEventPost with F11 key (keycode 0x67)
2. Or use Mission Control API if available
```

**`get_foreground_app()`:**
```
1. NSWorkspace.sharedWorkspace().frontmostApplication()
2. Return .localizedName() (lowered for profile matching)
```

### 3.3 macOS Permissions Required

The app MUST request these permissions on first run:
- **Camera:** NSCameraUsageDescription in Info.plist (handled by PyQt6 camera_stream.py)
- **Accessibility:** Prompt user via `AXIsProcessTrusted()` — if False, show dialog directing to System Preferences > Privacy > Accessibility
- **Input Monitoring:** Required for keyboard event injection — System Preferences > Privacy > Input Monitoring

Add to `Info.plist` (for PyInstaller bundle):
```xml
<key>NSCameraUsageDescription</key>
<string>Gesture Controller needs camera access to detect hand gestures.</string>
<key>NSAccessibilityUsageDescription</key>
<string>Gesture Controller needs accessibility access to control windows and send input.</string>
```

### 3.4 Tests to Write

```
tests/unit/test_macos_controller.py:
  - test_key_press_a: inject "a", verify CGEventPost called with correct keycode
  - test_key_combo_cmd_c: inject ["cmd", "c"], verify both flags set
  - test_mouse_click: verify CGEventPost called with kCGEventLeftMouseDown + kCGEventLeftMouseUp
  - test_mouse_scroll: verify CGEventCreateScrollWheelEvent called
  - test_get_foreground_app: mock NSWorkspace, verify process name returned
  - test_minimize_active_window: mock AXUIElement, verify kAXPressAction called
  - test_switch_window: mock CGWindowList, verify correct window raised
  - test_media_play_pause: verify special media key event posted
  - test_is_supported: returns True on macOS (Darwin), False elsewhere
```

---

## 4. LinuxController Implementation

### 4.1 File: `os_integration/linux_controller.py`

This is the most complex adapter because Wayland deliberately restricts input injection. You need two paths:

**Wayland path (primary):** `/dev/uinput` via `python-evdev`
**X11 fallback:** `python-xlib` or `xdotool` subprocess

### 4.2 Wayland via /dev/uinput

**Setup:**
```python
import evdev
import struct
import fcntl
import os

UINPUT_PATH = "/dev/uinput"

# Key codes (Linux input event codes, from input-event-codes.h)
LINUX_KEYCODES = {
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34, "h": 35,
    "i": 23, "j": 36, "k": 37, "l": 38, "m": 50, "n": 49, "o": 24, "p": 25,
    "q": 16, "r": 19, "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45,
    "y": 21, "z": 44, "return": 28, "escape": 1, "space": 57, "tab": 15,
    "delete": 111, "up": 103, "down": 108, "left": 105, "right": 106,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    "leftctrl": 29, "leftshift": 42, "leftalt": 56, "leftmeta": 125,
}

LINUX_MODIFIER_MAP = {
    "ctrl": "leftctrl", "shift": "leftshift", "alt": "leftalt", "super": "leftmeta",
}
```

**UInput device setup:**
```python
def _create_uinput_device() -> int:
    """Create a virtual input device via /dev/uinput. Returns file descriptor."""
    import ctypes
    import struct

    # uinput_user_dev struct: name[80], id (bus, vendor, product, version), ff_effects_max
    UINPUT_SET_EVBIT = 0x40045564
    UINPUT_SET_KEYBIT = 0x40045565
    UI_SET_EVBIT = 0x401C5504
    UI_SET_KEYBIT = 0x401C5505
    UI_DEV_CREATE = 0x5501

    BUS_USB = 0x03

    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)

    # Enable EV_KEY event type
    fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_KEY)

    # Enable all key codes we need
    for code in set(LINUX_KEYCODES.values()):
        fcntl.ioctl(fd, UI_SET_KEYBIT, code)

    # Enable EV_REL for relative mouse movement
    fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_REL)
    fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_X)
    fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_Y)
    fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_WHEEL)

    # Enable EV_ABS for absolute mouse positioning
    fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_ABS)
    fcntl.ioctl(fd, UI_SET_ABSBIT, evdev.ecodes.ABS_X)
    fcntl.ioctl(fd, UI_SET_ABSBIT, evdev.ecodes.ABS_Y)

    # Setup device info
    device_name = b"gesture-controller\x00".ljust(80, b"\x00")
    struct_uinput = struct.pack("80sHHiH", device_name, BUS_USB, 0x1234, 0x5678, 0x0001)
    os.write(fd, struct_uinput)

    # Enable EV_SYN
    fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_SYN)

    # Create the device
    fcntl.ioctl(fd, UI_DEV_CREATE)
    return fd
```

**Key injection pattern:**
```python
def _emit_event(fd: int, event_type: int, event_code: int, value: int) -> None:
    """Write a single input event to /dev/uinput."""
    # struct input_event { struct timeval time; unsigned short type; unsigned short code; unsigned int value; }
    event = struct.pack("llHHI", 0, 0, event_type, event_code, value)
    os.write(fd, event)
    # SYN_REPORT to signal end of event
    os.write(fd, struct.pack("llHHI", 0, 0, evdev.ecodes.EV_SYN, 0, 0))
```

**`key_press(key, modifiers)`:**
```python
def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
    if modifiers:
        for mod in modifiers:
            mod_key = LINUX_MODIFIER_MAP.get(mod.lower(), mod.lower())
            code = LINUX_KEYCODES[mod_key]
            self._emit(self.fd, EV_KEY, code, 1)  # key down
    code = LINUX_KEYCODES[key.lower()]
    self._emit(self.fd, EV_KEY, code, 1)
```

**`mouse_scroll(delta_x, delta_y)`:**
```python
def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
    if delta_x:
        self._emit(self.fd, EV_REL, REL_HWHEEL, delta_x)
    if delta_y:
        self._emit(self.fd, EV_REL, REL_WHEEL, delta_y)
```

### 4.3 X11 Fallback

If `/dev/uinput` is not available (permissions, kernel module not loaded), fall back to X11:

```python
class LinuxX11Controller(BaseController):
    """Fallback for X11 sessions. Uses python-xlib."""

    def __init__(self):
        from Xlib.display import Display
        self.display = Display()
        self.screen = self.display.screen()

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        keycode = self._key_to_keycode(key)
        if modifiers:
            for mod in modifiers:
                self.display.xtest_fake_input(Xlib.X.KeyPress, self._key_to_keycode(mod))
        self.display.xtest_fake_input(Xlib.X.KeyPress, keycode)
        self.display.sync()
```

### 4.4 Window Management on Linux

**Window management is compositor-dependent on Wayland.** This is the hardest part.

**Approach:**
1. Try `wlr-foreign-toplevel-management` protocol (wlroots-based compositors: Sway, Hyprland)
2. Try `org_kde_kwin_scripting` (KWin/KDE)
3. Try `gnome-shell extensions` via D-Bus (GNOME)
4. Fall back to `xdotool` or `wmctrl` subprocess (X11 only)
5. If none work: log warning, skip window management actions, still support key/mouse/scroll

**Implementation strategy — abstract behind a `WindowManager` helper:**

```python
# os_integration/linux_window_manager.py
class LinuxWindowManager(ABC):
    @abstractmethod
    def minimize_active(self) -> bool: ...  # returns True if succeeded
    @abstractmethod
    def switch_window(self) -> bool: ...
    @abstractmethod
    def get_foreground_app(self) -> str | None: ...

class WlrForeignToplevelManager(LinuxWindowManager):
    """For wlroots compositors (Sway, Hyprland)."""
    ...

class KWinScriptingManager(LinuxWindowManager):
    """For KDE Plasma."""
    ...

class GnomeDBusManager(LinuxWindowManager):
    """For GNOME Shell via D-Bus."""
    ...

class XdotoolFallbackManager(LinuxWindowManager):
    """For X11 via xdotool subprocess."""
    ...

def get_window_manager() -> LinuxWindowManager:
    """Auto-detect available window management method."""
    import subprocess
    # Check Wayland vs X11
    xdg_session = os.environ.get("XDG_SESSION_TYPE", "")
    if xdg_session == "wayland":
        # Try wlr-foreign-toplevel-management
        if _has_wlr_protocol():
            return WlrForeignToplevelManager()
        # Try KDE
        if os.environ.get("KDE_SESSION_VERSION"):
            return KWinScriptingManager()
        # Try GNOME
        if _has_gnome_shell():
            return GnomeDBusManager()
        return NullWindowManager()  # Window management not available
    else:
        # X11
        if _has_xdotool():
            return XdotoolFallbackManager()
        return NullWindowManager()
```

### 4.5 Media Keys on Linux

Media keys on Linux via /dev/uinput:
```python
LINUX_MEDIA_KEYCODES = {
    "play_pause": 164,   # KEY_PLAYPAUSE
    "next": 163,         # KEY_NEXTSONG
    "previous": 165,     # KEY_PREVIOUSSONG
    "volume_up": 115,    # KEY_VOLUMEUP
    "volume_down": 114,  # KEY_VOLUMEDOWN
}
```

### 4.6 udev Rules (Required for Non-Root Access)

Create file for packaging at `packaging/99-gesture-controller-uinput.rules`:
```
# Allow the gesture-controller user to access /dev/uinput
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"
```

Installation instructions:
```bash
sudo cp packaging/99-gesture-controller-uinput.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
# User must be in the 'input' group
sudo usermod -aG input $USER
# Log out and back in
```

### 4.7 Foreground App Detection on Linux

```python
def get_foreground_app(self) -> str:
    """Get the process name of the active window on Linux."""
    xdg_session = os.environ.get("XDG_SESSION_TYPE", "")
    if xdg_session == "wayland":
        # GNOME: D-Bus call to org.gnome.Shell
        # KDE: D-Bus call to org.kde.KWin
        # Sway: swaymsg -t get_tree
        # Hyprland: hyprctl activewindow
        return self._wayland_foreground_app()
    else:
        # X11: xdotool getactivewindow getwindowname
        # Or: xprop _NET_WM_PID
        return self._x11_foreground_app()
```

### 4.8 Tests to Write

```
tests/unit/test_linux_controller.py:
  - test_create_uinput_device: mock /dev/uinput open, verify ioctl calls
  - test_key_press: verify EV_KEY event written with correct code
  - test_key_combo_ctrl_c: verify ctrl down, c down, c up, ctrl up
  - test_mouse_scroll: verify REL_WHEEL events
  - test_is_supported_wayland: mock /dev/uinput exists, XDG_SESSION_TYPE=wayland
  - test_is_supported_x11: mock /dev/uinput absent, XDG_SESSION_TYPE=x11
  - test_window_manager_auto_detect_wlr: mock swaymsg available
  - test_window_manager_auto_detect_kde: mock KDE_SESSION_VERSION set
  - test_window_manager_auto_detect_gnome: mock gnome-shell D-Bus
  - test_window_manager_fallback_null: mock nothing available
  - test_media_volume_up: verify KEY_VOLUMEUP event
```

---

## 5. Controller Factory

### 5.1 File: `os_integration/__init__.py`

```python
import sys
import platform
from os_integration.base_controller import BaseController

def create_controller() -> BaseController:
    """Factory function that returns the correct platform controller."""
    system = platform.system()
    if system == "Windows":
        from os_integration.windows_controller import WindowsController
        ctrl = WindowsController()
        if ctrl.is_supported():
            return ctrl
    elif system == "Darwin":
        from os_integration.macos_controller import MacOSController
        ctrl = MacOSController()
        if ctrl.is_supported():
            return ctrl
    elif system == "Linux":
        from os_integration.linux_controller import LinuxController
        ctrl = LinuxController()
        if ctrl.is_supported():
            return ctrl

    raise RuntimeError(f"No supported OS controller for {system}")
```

### 5.2 Update `engine.py`

In `core/engine.py`, change the controller initialization to use the factory:

```python
# Before:
# from os_integration.windows_controller import WindowsController
# self.controller = WindowsController()

# After:
from os_integration import create_controller
self.controller = create_controller()
```

---

## 6. Platform-Specific Config

Add to `data/default_config.yaml`:

```yaml
os_integration:
  linux:
    input_method: "auto"  # "auto", "uinput", "x11", "xdotool"
    window_manager: "auto"  # "auto", "wlr", "kwin", "gnome", "xdotool", "none"
    udev_rules_path: "/etc/udev/rules.d/99-gesture-controller-uinput.rules"
  macos:
    use_axui_element: true  # Use AXUIElement for window management (requires Accessibility permission)
    accessibility_prompt_on_start: true
  windows:
    use_sendinput: false  # If true, upgrade from pyautogui to SendInput via ctypes
    foreground_tracking: "win32gui"  # or "ctypes"
```

---

## 7. Acceptance Criteria for M4

- [ ] MacOSController passes all unit tests on macOS
- [ ] LinuxController passes all unit tests on Linux
- [ ] LinuxController falls back to X11 when /dev/uinput unavailable
- [ ] LinuxWindowManager tries wlr -> kwin -> gnome -> xdotool -> null
- [ ] `create_controller()` factory returns correct controller for current OS
- [ ] Minimize, switch window, scroll, and media keys work on all 3 platforms
- [ ] `get_foreground_app()` returns process name on all 3 platforms
- [ ] udev rules file created for packaging
- [ ] Permission requirements documented per platform (macOS Accessibility, Linux input group)
- [ ] Integration tests pass: GestureEvent -> ActionDispatcher -> MacOSController/LinuxController
- [ ] No regressions on WindowsController (all existing tests still pass)
