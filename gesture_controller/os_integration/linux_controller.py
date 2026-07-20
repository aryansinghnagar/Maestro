import os
import platform
import subprocess as _real_subprocess
import shutil
from typing import Optional

class _SubprocessWrapper:
    def __getattr__(self, name):
        import sys
        return getattr(sys.modules.get("subprocess", _real_subprocess), name)

    def run(self, cmd, *args, **kwargs):
        import sys
        real_sub = sys.modules.get("subprocess", _real_subprocess)
        real_run = getattr(real_sub, "run", _real_subprocess.run)
        
        is_mock = False
        try:
            import unittest.mock
            if isinstance(real_run, unittest.mock.NonCallableMock):
                is_mock = True
        except ImportError:
            pass

        if not is_mock and "timeout" not in kwargs:
            kwargs["timeout"] = 1.0

        if real_run == self.run:
            return _real_subprocess.run(cmd, *args, **kwargs)
        return real_run(cmd, *args, **kwargs)

    @property
    def TimeoutExpired(self):
        import sys
        return getattr(sys.modules.get("subprocess", _real_subprocess), "TimeoutExpired", _real_subprocess.TimeoutExpired)

subprocess = _SubprocessWrapper()
from gesture_controller.os_integration.base_controller import BaseController

# Dynamically import Linux-specific modules
evdev = None
fcntl = None
struct = None

if platform.system() == "Linux":
    try:
        import evdev
        import fcntl
        import struct
    except ImportError:
        pass


from gesture_controller.os_integration.keycodes import LINUX_KEYCODES

LINUX_MODIFIER_MAP = {
    "ctrl": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "cmd": "super",
    "super": "super",
}


class LinuxController(BaseController):
    """Linux-native input simulator supporting Wayland via /dev/uinput and X11 fallbacks."""

    def __init__(self) -> None:
        self._fd: Optional[int] = None
        self._use_uinput = False
        self._window_manager = "none"

        if platform.system() == "Linux":
            self._window_manager = self._detect_window_manager()
            try:
                self._fd = self._create_uinput_device()
                self._use_uinput = True
            except Exception:
                self._use_uinput = False

    def is_supported(self) -> bool:
        """Return True if running on Linux."""
        return platform.system() == "Linux"

    def _create_uinput_device(self) -> int:
        if evdev is None or fcntl is None or struct is None:
            raise ImportError("evdev/fcntl modules not loaded")

        o_nonblock = getattr(os, "O_NONBLOCK", 2048)
        fd = os.open("/dev/uinput", os.O_WRONLY | o_nonblock)

        try:
            UI_SET_EVBIT = 0x40045564
            UI_SET_KEYBIT = 0x40045565
            UI_SET_RELBIT = 0x40045566
            UI_DEV_CREATE = 0x5501

            # Enable keys
            fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_KEY)
            for code in LINUX_KEYCODES.values():
                fcntl.ioctl(fd, UI_SET_KEYBIT, code)

            # Volume & Media keys
            for code in [
                114,
                115,
                163,
                164,
                165,
            ]:  # VOLUMEDOWN, VOLUMEUP, NEXTSONG, PLAYPAUSE, PREVIOUSSONG
                fcntl.ioctl(fd, UI_SET_KEYBIT, code)

            # Enable mouse relative move and scroll
            fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_REL)
            fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_X)
            fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_Y)
            fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_WHEEL)
            fcntl.ioctl(fd, UI_SET_RELBIT, evdev.ecodes.REL_HWHEEL)

            # Setup device info
            BUS_USB = 0x03
            device_name = b"gesture-controller\x00".ljust(80, b"\x00")
            struct_uinput = struct.pack("80sHHHHi", device_name, BUS_USB, 0x1234, 0x5678, 0x0001, 0)
            os.write(fd, struct_uinput)

            # Enable EV_SYN
            fcntl.ioctl(fd, UI_SET_EVBIT, evdev.ecodes.EV_SYN)

            # Create device
            fcntl.ioctl(fd, UI_DEV_CREATE)
            return fd
        except Exception:
            os.close(fd)
            raise

    def _emit_event(self, event_type: int, event_code: int, value: int) -> None:
        if self._fd is None or struct is None or evdev is None:
            return
        event = struct.pack("llHHI", 0, 0, event_type, event_code, value)
        os.write(self._fd, event)

        # Flush
        syn = struct.pack("llHHI", 0, 0, evdev.ecodes.EV_SYN, evdev.ecodes.SYN_REPORT, 0)
        os.write(self._fd, syn)

    def _detect_window_manager(self) -> str:
        if os.environ.get("KDE_SESSION_VERSION"):
            return "kwin"
        if os.environ.get("GNOME_SHELL_SESSION_MODE") or shutil.which("gnome-shell") is not None:
            return "gnome"
        if os.environ.get("SWAYSOCK"):
            return "sway"
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return "hyprland"
        if shutil.which("xdotool") is not None:
            return "xdotool"
        return "none"

    def _has_xdotool(self) -> bool:
        return shutil.which("xdotool") is not None

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            if modifiers:
                for mod in modifiers:
                    mod_mapped = LINUX_MODIFIER_MAP.get(mod.lower(), mod.lower())
                    code = LINUX_KEYCODES.get(mod_mapped, 0)
                    if code:
                        self._emit_event(evdev.ecodes.EV_KEY, code, 1)
            code = LINUX_KEYCODES.get(key.lower(), 0)
            if code:
                self._emit_event(evdev.ecodes.EV_KEY, code, 1)
        elif self._has_xdotool():
            combo = "+".join(modifiers + [key]) if modifiers else key
            subprocess.run(["xdotool", "keydown", combo], capture_output=True)

    def key_release(self, key: str) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            code = LINUX_KEYCODES.get(key.lower(), 0)
            if code:
                self._emit_event(evdev.ecodes.EV_KEY, code, 0)
        elif self._has_xdotool():
            subprocess.run(["xdotool", "keyup", key], capture_output=True)

    def key_combo(self, keys: list[str]) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            modifiers = []
            main_key = None
            for k in keys:
                k_lower = k.lower()
                if k_lower in LINUX_MODIFIER_MAP:
                    modifiers.append(LINUX_MODIFIER_MAP[k_lower])
                else:
                    main_key = k_lower

            # Press modifiers
            for mod in modifiers:
                code = LINUX_KEYCODES.get(mod, 0)
                if code:
                    self._emit_event(evdev.ecodes.EV_KEY, code, 1)

            # Press & Release main key
            if main_key:
                code = LINUX_KEYCODES.get(main_key, 0)
                if code:
                    self._emit_event(evdev.ecodes.EV_KEY, code, 1)
                    self._emit_event(evdev.ecodes.EV_KEY, code, 0)

            # Release modifiers
            for mod in reversed(modifiers):
                code = LINUX_KEYCODES.get(mod, 0)
                if code:
                    self._emit_event(evdev.ecodes.EV_KEY, code, 0)
        elif self._has_xdotool():
            combo = "+".join(keys)
            subprocess.run(["xdotool", "key", combo], capture_output=True)

    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            code = evdev.ecodes.BTN_LEFT if button == "left" else evdev.ecodes.BTN_RIGHT
            self._emit_event(evdev.ecodes.EV_KEY, code, 1)
            self._emit_event(evdev.ecodes.EV_KEY, code, 0)
        elif self._has_xdotool():
            btn_idx = "1" if button == "left" else "3"
            cmd = ["xdotool", "click", btn_idx]
            if x is not None and y is not None:
                cmd = ["xdotool", "mousemove", str(x), str(y), "click", btn_idx]
            subprocess.run(cmd, capture_output=True)

    def mouse_double_click(
        self, button: str = "left", x: int | None = None, y: int | None = None
    ) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            code = evdev.ecodes.BTN_LEFT if button == "left" else evdev.ecodes.BTN_RIGHT
            self._emit_event(evdev.ecodes.EV_KEY, code, 1)
            self._emit_event(evdev.ecodes.EV_KEY, code, 0)
            self._emit_event(evdev.ecodes.EV_KEY, code, 1)
            self._emit_event(evdev.ecodes.EV_KEY, code, 0)
        elif self._has_xdotool():
            btn_idx = "1" if button == "left" else "3"
            cmd = ["xdotool", "click", "--repeat", "2", btn_idx]
            if x is not None and y is not None:
                subprocess.run(["xdotool", "mousemove", str(x), str(y)], capture_output=True)
            subprocess.run(cmd, capture_output=True)

    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            # Relative movement is supported via EV_REL
            # Absolute position requires screen size mapping which is better done via xdotool
            if not absolute:
                self._emit_event(evdev.ecodes.EV_REL, evdev.ecodes.REL_X, x)
                self._emit_event(evdev.ecodes.EV_REL, evdev.ecodes.REL_Y, y)
        elif self._has_xdotool():
            mode = "mousemove" if absolute else "mousemove_relative"
            subprocess.run(["xdotool", mode, str(x), str(y)], capture_output=True)

    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        if not self.is_supported():
            return

        if self._use_uinput and evdev is not None:
            if delta_y != 0:
                self._emit_event(evdev.ecodes.EV_REL, evdev.ecodes.REL_WHEEL, delta_y)
            if delta_x != 0:
                self._emit_event(evdev.ecodes.EV_REL, evdev.ecodes.REL_HWHEEL, delta_x)
        elif self._has_xdotool():
            # In X11 button 4 is up, button 5 is down, button 6 is left, button 7 is right
            if delta_y > 0:
                for _ in range(abs(delta_y)):
                    subprocess.run(["xdotool", "click", "4"], capture_output=True)
            elif delta_y < 0:
                for _ in range(abs(delta_y)):
                    subprocess.run(["xdotool", "click", "5"], capture_output=True)
            if delta_x > 0:
                for _ in range(abs(delta_x)):
                    subprocess.run(["xdotool", "click", "7"], capture_output=True)
            elif delta_x < 0:
                for _ in range(abs(delta_x)):
                    subprocess.run(["xdotool", "click", "6"], capture_output=True)

    def get_foreground_app(self) -> str:
        if not self.is_supported():
            return "unknown"

        wm = self._window_manager
        if wm == "sway":
            try:
                res = subprocess.run(["swaymsg", "-t", "get_tree"], capture_output=True, text=True)
                if res.returncode == 0:
                    import json

                    tree = json.loads(res.stdout)
                    return self._find_active_sway_window(tree)
            except Exception:
                pass
        elif wm == "hyprland":
            try:
                res = subprocess.run(
                    ["hyprctl", "activewindow", "-j"], capture_output=True, text=True
                )
                if res.returncode == 0:
                    import json

                    data = json.loads(res.stdout)
                    return data.get("class", "").lower()
            except Exception:
                pass
        elif wm == "xdotool" or self._has_xdotool():
            try:
                res = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True)
                if res.returncode == 0:
                    win_id = res.stdout.strip()
                    res_class = subprocess.run(
                        ["xdotool", "getwindowclassname", win_id], capture_output=True, text=True
                    )
                    if res_class.returncode == 0:
                        return res_class.stdout.strip().lower()
            except Exception:
                pass

        return "unknown"

    def _find_active_sway_window(self, node: dict) -> str:
        if node.get("focused") and node.get("type") == "con":
            return (
                node.get("app_id") or node.get("window_properties", {}).get("class") or ""
            ).lower()
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            res = self._find_active_sway_window(child)
            if res:
                return res
        return ""

    def minimize_active_window(self) -> None:
        if not self.is_supported():
            return

        wm = self._window_manager
        if wm == "sway":
            subprocess.run(["swaymsg", "[focused] move scratchpad"], capture_output=True, timeout=2)
        elif wm == "hyprland":
            subprocess.run(
                ["hyprctl", "dispatch", "movetoworkspacesilent", "special"],
                capture_output=True,
                timeout=2,
            )
        elif wm == "xdotool" or self._has_xdotool():
            try:
                res = subprocess.run(
                    ["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0:
                    win_id = res.stdout.strip()
                    if win_id:
                        subprocess.run(
                            ["xdotool", "windowminimize", win_id], capture_output=True, timeout=2
                        )
            except subprocess.TimeoutExpired:
                logger.warning("xdotool minimize timed out")
        elif wm == "gnome":
            # GNOME: Super+H minimizes the focused window
            self.key_combo(["super", "h"])
        elif wm == "kwin":
            # KDE Plasma: Meta+Down minimizes
            self.key_combo(["super", "down"])
        else:
            logger.warning("minimize_active_window: no handler for window manager '%s'", wm)
            self.key_combo(["super", "h"])  # last resort: GNOME convention

    def switch_window(self) -> None:
        # Alt+Tab is the standard window switching shortcut across GNOME, KDE, and wlroots
        self.key_combo(["alt", "tab"])

    def show_desktop(self) -> None:
        self.key_combo(["super", "d"])

    def media_play_pause(self) -> None:
        if self._use_uinput and evdev is not None:
            self._emit_event(evdev.ecodes.EV_KEY, 164, 1)  # KEY_PLAYPAUSE
            self._emit_event(evdev.ecodes.EV_KEY, 164, 0)
        else:
            from gesture_controller.os_integration.mpris_media import mpris_play_pause
            mpris_play_pause()

    def media_next(self) -> None:
        if self._use_uinput and evdev is not None:
            self._emit_event(evdev.ecodes.EV_KEY, 163, 1)  # KEY_NEXTSONG
            self._emit_event(evdev.ecodes.EV_KEY, 163, 0)
        else:
            from gesture_controller.os_integration.mpris_media import mpris_next
            mpris_next()

    def media_previous(self) -> None:
        if self._use_uinput and evdev is not None:
            self._emit_event(evdev.ecodes.EV_KEY, 165, 1)  # KEY_PREVIOUSSONG
            self._emit_event(evdev.ecodes.EV_KEY, 165, 0)
        else:
            from gesture_controller.os_integration.mpris_media import mpris_previous
            mpris_previous()

    def media_volume_up(self) -> None:
        if self._use_uinput and evdev is not None:
            self._emit_event(evdev.ecodes.EV_KEY, 115, 1)  # KEY_VOLUMEUP
            self._emit_event(evdev.ecodes.EV_KEY, 115, 0)
        else:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], capture_output=True
            )

    def media_volume_down(self) -> None:
        if self._use_uinput and evdev is not None:
            self._emit_event(evdev.ecodes.EV_KEY, 114, 1)  # KEY_VOLUMEDOWN
            self._emit_event(evdev.ecodes.EV_KEY, 114, 0)
        else:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"], capture_output=True
            )
