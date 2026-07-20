"""Cross-platform global hotkey registration."""
from __future__ import annotations

import platform
import threading
from typing import Callable, Any

# Windows key modifiers
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

VK_CODES = {
    "m": 0x4D,
    "tab": 0x09,
    "up": 0x26,
    "down": 0x28,
    "space": 0x20,
    "n": 0x4E,
    "p": 0x50,
    "d": 0x44,
    "w": 0x57,
    "esc": 0x1B,
    ",": 0xBC,
    "q": 0x51
}


class GlobalHotkeyManager:
    """Register global hotkeys (work even when Maestro is not focused)."""

    def __init__(self) -> None:
        self._system = platform.system()
        self._hotkeys: dict[str, Callable[[], None]] = {}
        self._registered_id_counter = 0

        if self._system == "Windows":
            self._impl: Any = _WindowsHotkeys()
        else:
            # Graceful fallback on macOS and Linux
            self._impl = _FallbackHotkeys()

    def register(self, hotkey: str, callback: Callable[[], None]) -> None:
        """Register a global hotkey.

        Args:
            hotkey: Hotkey string (e.g., "ctrl+shift+m")
            callback: Function to call when hotkey pressed
        """
        clean_hotkey = hotkey.lower().replace(" ", "")
        self._hotkeys[clean_hotkey] = callback
        self._impl.register(clean_hotkey, callback)

    def unregister(self, hotkey: str) -> None:
        """Unregister a global hotkey."""
        clean_hotkey = hotkey.lower().replace(" ", "")
        if clean_hotkey in self._hotkeys:
            del self._hotkeys[clean_hotkey]
            self._impl.unregister(clean_hotkey)

    def unregister_all(self) -> None:
        """Unregister all hotkeys."""
        for hotkey in list(self._hotkeys.keys()):
            self.unregister(hotkey)


class _FallbackHotkeys:
    """Fallback hotkey manager for non-supported platforms."""

    def register(self, hotkey: str, callback: Callable[[], None]) -> None:
        pass

    def unregister(self, hotkey: str) -> None:
        pass


class _WindowsHotkeys:
    """Windows global hotkeys via RegisterHotKey in a background thread."""

    def __init__(self) -> None:
        self._hotkeys = {}
        self._id_counter = 1
        self._thread = None
        self._running = False

    def _parse_hotkey(self, hotkey_str: str) -> tuple[int, int] | None:
        parts = hotkey_str.split("+")
        mods = 0
        vk = 0
        for p in parts:
            if p == "ctrl" or p == "control":
                mods |= MOD_CONTROL
            elif p == "shift":
                mods |= MOD_SHIFT
            elif p == "alt":
                mods |= MOD_ALT
            elif p == "super" or p == "win":
                mods |= MOD_WIN
            elif p in VK_CODES:
                vk = VK_CODES[p]
            elif len(p) == 1:
                vk = ord(p.upper())

        if vk == 0:
            return None
        return mods, vk

    def register(self, hotkey: str, callback: Callable[[], None]) -> None:
        parsed = self._parse_hotkey(hotkey)
        if not parsed:
            return

        mods, vk = parsed
        hk_id = self._id_counter
        self._id_counter += 1
        self._hotkeys[hotkey] = (hk_id, mods, vk, callback)

        # Restart thread with new hotkeys
        self.stop()
        self.start()

    def unregister(self, hotkey: str) -> None:
        if hotkey in self._hotkeys:
            del self._hotkeys[hotkey]
            self.stop()
            self.start()

    def start(self) -> None:
        if not self._hotkeys:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="win_hotkeys_loop")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        # Send a dummy hotkey or post a quit message to wake up GetMessageW
        if self._thread:
            import ctypes
            # WM_QUIT = 0x0012
            ctypes.windll.user32.PostThreadMessageW(self._thread.ident, 0x0012, 0, 0)
            self._thread.join(timeout=0.5)
            self._thread = None

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        registered_ids = []

        # Register all hotkeys in this thread context
        for hk_id, mods, vk, _ in self._hotkeys.values():
            if user32.RegisterHotKey(None, hk_id, mods, vk):
                registered_ids.append(hk_id)

        msg = wintypes.MSG()
        while self._running:
            # GetMessageW blocks until a message is received
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res == 0 or res == -1:
                break

            if msg.message == 0x0312:  # WM_HOTKEY
                hk_id = msg.wParam
                for hk_val in self._hotkeys.values():
                    if hk_val[0] == hk_id:
                        # Trigger callback on a separate thread to prevent blocking GetMessage
                        threading.Thread(target=hk_val[3], daemon=True).start()
                        break

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        for hk_id in registered_ids:
            user32.UnregisterHotKey(None, hk_id)
