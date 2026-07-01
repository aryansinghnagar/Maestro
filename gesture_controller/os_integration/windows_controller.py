import pyautogui
import platform
import structlog
import ctypes
from typing import Any

from gesture_controller.os_integration.base_controller import BaseController

logger = structlog.get_logger(__name__)

# Configure PyAutoGUI safety features
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

class WindowsController(BaseController):
    """Windows OS controller using PyAutoGUI and ctypes Win32 bindings."""

    def __init__(self) -> None:
        if not self.is_supported():
            raise RuntimeError("WindowsController is only supported on Windows operating systems.")
        logger.info("WindowsController initialized")

    def is_supported(self) -> bool:
        return platform.system() == "Windows"

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        if modifiers:
            # pyautogui.hotkey accepts list of strings
            pyautogui.hotkey(*(modifiers + [key]))
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
        if delta_y != 0:
            pyautogui.scroll(int(delta_y))
        if delta_x != 0:
            pyautogui.hscroll(int(delta_x))

    def get_foreground_app(self) -> str:
        """Query foreground window and return its process executable name."""
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""

        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        import psutil
        try:
            return psutil.Process(pid.value).name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return title.lower()

    def minimize_active_window(self) -> None:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6

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
