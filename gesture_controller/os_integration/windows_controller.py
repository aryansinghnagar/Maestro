import platform
import structlog
import ctypes
from ctypes import wintypes

from gesture_controller.os_integration.base_controller import BaseController

logger = structlog.get_logger(__name__)

# Virtual Key (VK) codes mapping (Imported from keycodes)


# Win32 SendInput Structures
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        (
            "dwExtraInfo",
            ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong,
        ),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        (
            "dwExtraInfo",
            ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong,
        ),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


def get_vk_code(key: str) -> int:
    from gesture_controller.os_integration.keycodes import get_windows_vkcode
    return get_windows_vkcode(key)


def send_key_event(vk_code: int, is_up: bool = False) -> None:
    if vk_code == 0:
        return
    flags = 0x0002 if is_up else 0  # KEYEVENTF_KEYUP = 0x0002
    ki = KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    union = INPUT_UNION(ki=ki)
    input_struct = INPUT(type=1, u=union)  # INPUT_KEYBOARD = 1
    ctypes.windll.user32.SendInput(  # type: ignore[attr-defined]
        1, ctypes.byref(input_struct), ctypes.sizeof(input_struct)
    )


def send_mouse_event(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> None:
    mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0, dwExtraInfo=0)
    union = INPUT_UNION(mi=mi)
    input_struct = INPUT(type=0, u=union)  # INPUT_MOUSE = 0
    ctypes.windll.user32.SendInput(  # type: ignore[attr-defined]
        1, ctypes.byref(input_struct), ctypes.sizeof(input_struct)
    )


class WindowsController(BaseController):
    """Windows OS controller using native Win32 SendInput APIs (ADR-005)."""

    def __init__(self) -> None:
        if not self.is_supported():
            raise RuntimeError("WindowsController is only supported on Windows operating systems.")
        logger.info("WindowsController initialized with native SendInput support")

    def is_supported(self) -> bool:
        return platform.system() == "Windows"

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        vk = get_vk_code(key)
        mods_vks = [get_vk_code(m) for m in (modifiers or [])]

        # Press modifiers
        for m_vk in mods_vks:
            send_key_event(m_vk, is_up=False)

        # Press key
        send_key_event(vk, is_up=False)
        send_key_event(vk, is_up=True)

        # Release modifiers (reverse order)
        for m_vk in reversed(mods_vks):
            send_key_event(m_vk, is_up=True)

    def key_release(self, key: str) -> None:
        vk = get_vk_code(key)
        send_key_event(vk, is_up=True)

    def key_combo(self, keys: list[str]) -> None:
        vks = [get_vk_code(k) for k in keys]

        # Press all in order
        for vk in vks:
            send_key_event(vk, is_up=False)

        # Release all in reverse order
        for vk in reversed(vks):
            send_key_event(vk, is_up=True)

    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self.mouse_move(x, y, absolute=True)

        btn_lower = button.lower()
        if btn_lower == "left":
            send_mouse_event(0x0002)  # MOUSEEVENTF_LEFTDOWN
            send_mouse_event(0x0004)  # MOUSEEVENTF_LEFTUP
        elif btn_lower == "right":
            send_mouse_event(0x0008)  # MOUSEEVENTF_RIGHTDOWN
            send_mouse_event(0x0010)  # MOUSEEVENTF_RIGHTUP
        elif btn_lower == "middle":
            send_mouse_event(0x0020)  # MOUSEEVENTF_MIDDLEDOWN
            send_mouse_event(0x0040)  # MOUSEEVENTF_MIDDLEUP

    def mouse_double_click(
        self, button: str = "left", x: int | None = None, y: int | None = None
    ) -> None:
        self.mouse_click(button, x, y)
        import time

        time.sleep(0.05)
        self.mouse_click(button, x, y)

    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        if absolute:
            ctypes.windll.user32.SetCursorPos(x, y)  # type: ignore[attr-defined]
        else:
            send_mouse_event(0x0001, x, y)  # MOUSEEVENTF_MOVE

    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        if delta_y != 0:
            send_mouse_event(0x0800, data=delta_y * 120)  # MOUSEEVENTF_WHEEL
        if delta_x != 0:
            send_mouse_event(0x1000, data=delta_x * 120)  # MOUSEEVENTF_HWHEEL

    def get_foreground_app(self) -> str:
        """Query foreground window and return its process executable name."""
        hwnd = ctypes.windll.user32.GetForegroundWindow()  # type: ignore[attr-defined]
        if not hwnd:
            return ""

        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)  # type: ignore[attr-defined]
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)  # type: ignore[attr-defined]
            title = buf.value

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))  # type: ignore[attr-defined]

        import psutil

        try:
            return str(psutil.Process(pid.value).name().lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return str(title.lower())

    def minimize_active_window(self) -> None:
        hwnd = ctypes.windll.user32.GetForegroundWindow()  # type: ignore[attr-defined]
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # type: ignore[attr-defined]  # SW_MINIMIZE = 6

    def switch_window(self) -> None:
        self.key_combo(["alt", "tab"])

    def show_desktop(self) -> None:
        self.key_combo(["win", "d"])

    def media_play_pause(self) -> None:
        send_key_event(get_vk_code("playpause"), is_up=False)
        send_key_event(get_vk_code("playpause"), is_up=True)

    def media_next(self) -> None:
        send_key_event(get_vk_code("nexttrack"), is_up=False)
        send_key_event(get_vk_code("nexttrack"), is_up=True)

    def media_previous(self) -> None:
        send_key_event(get_vk_code("prevtrack"), is_up=False)
        send_key_event(get_vk_code("prevtrack"), is_up=True)

    def media_volume_up(self) -> None:
        for _ in range(3):
            send_key_event(get_vk_code("volumeup"), is_up=False)
            send_key_event(get_vk_code("volumeup"), is_up=True)

    def media_volume_down(self) -> None:
        for _ in range(3):
            send_key_event(get_vk_code("volumedown"), is_up=False)
            send_key_event(get_vk_code("volumedown"), is_up=True)
