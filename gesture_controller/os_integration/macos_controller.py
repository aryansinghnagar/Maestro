import sys
import platform
from typing import Optional
from gesture_controller.os_integration.base_controller import BaseController

# Dynamically import macOS modules if running on Darwin
Quartz = None
AppKit = None
ApplicationServices = None
MAC_MODIFIER_FLAGS = {}

if platform.system() == "Darwin":
    try:
        import Quartz
        import AppKit
        import ApplicationServices
        
        MAC_MODIFIER_FLAGS = {
            "cmd": Quartz.kCGEventFlagMaskCommand,
            "shift": Quartz.kCGEventFlagMaskShift,
            "ctrl": Quartz.kCGEventFlagMaskControl,
            "alt": Quartz.kCGEventFlagMaskAlternate,
        }
    except ImportError:
        pass

# virtual keycode mappings for macOS standard keyboard keys
MAC_KEYCODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05, "z": 0x06,
    "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E,
    "r": 0x0F, "y": 0x10, "t": 0x11, "u": 0x20, "i": 0x22, "o": 0x1F, "p": 0x23,
    "j": 0x26, "k": 0x28, "l": 0x25, "m": 0x2E, "n": 0x2D,
    "0": 0x1D, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15,
    "5": 0x17, "6": 0x16, "7": 0x1A, "8": 0x1C, "9": 0x19,
    "return": 0x24, "escape": 0x35, "space": 0x31,
    "tab": 0x30, "delete": 0x33, "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60, "f6": 0x61,
    "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
    "home": 0x73, "end": 0x77, "page_up": 0x74, "page_down": 0x79,
}

class MacOSController(BaseController):
    """macOS-native input simulation and window management controller using Quartz."""

    def __init__(self) -> None:
        pass

    def is_supported(self) -> bool:
        """Return True if running on macOS with PyObjC bindings loaded."""
        return platform.system() == "Darwin" and Quartz is not None and AppKit is not None

    def _post_keyboard_event(self, keycode: int, down: bool, flags: int = 0) -> None:
        if not self.is_supported():
            return
        event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        if flags:
            Quartz.CGEventSetFlags(event, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _get_mouse_position(self) -> tuple[int, int]:
        if not self.is_supported():
            return (0, 0)
        event = Quartz.CGEventCreate(None)
        loc = Quartz.CGEventGetLocation(event)
        return (int(loc.x), int(loc.y))

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        if not self.is_supported():
            return
        keycode = MAC_KEYCODES.get(key.lower(), 0)
        flags = 0
        if modifiers:
            for mod in modifiers:
                flags |= MAC_MODIFIER_FLAGS.get(mod.lower(), 0)
        self._post_keyboard_event(keycode, True, flags)

    def key_release(self, key: str) -> None:
        if not self.is_supported():
            return
        keycode = MAC_KEYCODES.get(key.lower(), 0)
        self._post_keyboard_event(keycode, False, 0)

    def key_combo(self, keys: list[str]) -> None:
        if not self.is_supported():
            return

        modifiers = []
        main_key = None
        for k in keys:
            k_lower = k.lower()
            if k_lower in ["cmd", "shift", "ctrl", "alt"]:
                modifiers.append(k_lower)
            else:
                main_key = k_lower

        flags = 0
        for mod in modifiers:
            flags |= MAC_MODIFIER_FLAGS.get(mod, 0)
            mod_code = {
                "cmd": 55, "shift": 56, "ctrl": 59, "alt": 58
            }.get(mod, 0)
            if mod_code:
                self._post_keyboard_event(mod_code, True)

        if main_key:
            main_code = MAC_KEYCODES.get(main_key, 0)
            self._post_keyboard_event(main_code, True, flags)
            self._post_keyboard_event(main_code, False, flags)

        for mod in reversed(modifiers):
            mod_code = {
                "cmd": 55, "shift": 56, "ctrl": 59, "alt": 58
            }.get(mod, 0)
            if mod_code:
                self._post_keyboard_event(mod_code, False)

    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        if not self.is_supported():
            return

        if x is None or y is None:
            x, y = self._get_mouse_position()
        point = Quartz.CGPoint(x, y)

        if button == "left":
            down_type = Quartz.kCGEventLeftMouseDown
            up_type = Quartz.kCGEventLeftMouseUp
            cg_button = Quartz.kCGMouseButtonLeft
        elif button == "right":
            down_type = Quartz.kCGEventRightMouseDown
            up_type = Quartz.kCGEventRightMouseUp
            cg_button = Quartz.kCGMouseButtonRight
        else:
            down_type = Quartz.kCGEventOtherMouseDown
            up_type = Quartz.kCGEventOtherMouseUp
            cg_button = Quartz.kCGMouseButtonCenter

        event_down = Quartz.CGEventCreateMouseEvent(None, down_type, point, cg_button)
        event_up = Quartz.CGEventCreateMouseEvent(None, up_type, point, cg_button)

        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)

    def mouse_double_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        if not self.is_supported():
            return

        if x is None or y is None:
            x, y = self._get_mouse_position()
        point = Quartz.CGPoint(x, y)

        if button == "left":
            down_type = Quartz.kCGEventLeftMouseDown
            up_type = Quartz.kCGEventLeftMouseUp
            cg_button = Quartz.kCGMouseButtonLeft
        elif button == "right":
            down_type = Quartz.kCGEventRightMouseDown
            up_type = Quartz.kCGEventRightMouseUp
            cg_button = Quartz.kCGMouseButtonRight
        else:
            down_type = Quartz.kCGEventOtherMouseDown
            up_type = Quartz.kCGEventOtherMouseUp
            cg_button = Quartz.kCGMouseButtonCenter

        event_down = Quartz.CGEventCreateMouseEvent(None, down_type, point, cg_button)
        event_up = Quartz.CGEventCreateMouseEvent(None, up_type, point, cg_button)

        Quartz.CGEventSetIntegerValueField(event_down, Quartz.kCGMouseEventClickState, 2)
        Quartz.CGEventSetIntegerValueField(event_up, Quartz.kCGMouseEventClickState, 2)

        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)

    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        if not self.is_supported():
            return

        if not absolute:
            curr_pos = self._get_mouse_position()
            x += curr_pos[0]
            y += curr_pos[1]

        point = Quartz.CGPoint(x, y)
        event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, point, 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        if not self.is_supported():
            return

        if delta_y != 0:
            event = Quartz.CGEventCreateScrollWheelEvent(None, 0, 1, delta_y)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

        if delta_x != 0:
            event = Quartz.CGEventCreateScrollWheelEvent(None, 0, 2, 0, delta_x)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def get_foreground_app(self) -> str:
        if not self.is_supported():
            return "unknown"

        workspace = AppKit.NSWorkspace.sharedWorkspace()
        front_app = workspace.frontmostApplication()
        if front_app:
            name = front_app.localizedName()
            if name:
                return name.lower()
        return "unknown"

    def minimize_active_window(self) -> None:
        if not self.is_supported() or ApplicationServices is None:
            return

        workspace = AppKit.NSWorkspace.sharedWorkspace()
        front_app = workspace.frontmostApplication()
        if not front_app:
            return

        pid = front_app.processIdentifier()
        app_ref = ApplicationServices.AXUIElementCreateApplication(pid)
        if app_ref:
            kAXFocusedWindowAttribute = "AXFocusedWindow"
            kAXMinimizeButtonAttribute = "AXMinimizeButton"
            kAXPressAction = "AXPress"

            err, window = ApplicationServices.AXUIElementCopyAttributeValue(
                app_ref, kAXFocusedWindowAttribute, None
            )
            if err == 0 and window:
                err, min_btn = ApplicationServices.AXUIElementCopyAttributeValue(
                    window, kAXMinimizeButtonAttribute, None
                )
                if err == 0 and min_btn:
                    ApplicationServices.AXUIElementPerformAction(min_btn, kAXPressAction)
                    return

        # Fallback to standard command+M shortcut if accessibility API minimizes fails
        self.key_combo(["cmd", "m"])

    def switch_window(self) -> None:
        # Standard app switching shortcut
        self.key_combo(["cmd", "tab"])

    def show_desktop(self) -> None:
        # F11 is the macOS default key to show desktop
        self.key_combo(["f11"])

    def _post_media_key(self, key_code: int) -> None:
        # NSSystemDefined event (type 14) for media key presses
        # subtype 8 is auxiliary control buttons
        # 0xA is key down, 0xB is key up
        for state in [0xA, 0xB]:
            data1 = (key_code << 16) | (state << 8)
            event = AppKit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                14, (0, 0), 0, 0, 0, None, 8, data1, -1
            )
            cg_event = event.CGEvent()
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, cg_event)

    def media_play_pause(self) -> None:
        if self.is_supported():
            self._post_media_key(16)  # NX_KEYTYPE_PLAY

    def media_next(self) -> None:
        if self.is_supported():
            self._post_media_key(17)  # NX_KEYTYPE_FAST

    def media_previous(self) -> None:
        if self.is_supported():
            self._post_media_key(18)  # NX_KEYTYPE_REWIND

    def media_volume_up(self) -> None:
        if self.is_supported():
            self._post_media_key(0)   # NX_KEYTYPE_SOUND_UP

    def media_volume_down(self) -> None:
        if self.is_supported():
            self._post_media_key(1)   # NX_KEYTYPE_SOUND_DOWN
