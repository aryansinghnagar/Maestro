import pytest
from unittest.mock import MagicMock, patch

# Setup mock constants
mock_evdev = MagicMock()
mock_fcntl = MagicMock()
mock_struct = MagicMock()

mock_evdev.ecodes.EV_KEY = 1
mock_evdev.ecodes.EV_REL = 2
mock_evdev.ecodes.EV_SYN = 0
mock_evdev.ecodes.SYN_REPORT = 0
mock_evdev.ecodes.REL_X = 0
mock_evdev.ecodes.REL_Y = 1
mock_evdev.ecodes.REL_WHEEL = 8
mock_evdev.ecodes.REL_HWHEEL = 6
mock_evdev.ecodes.BTN_LEFT = 272
mock_evdev.ecodes.BTN_RIGHT = 273

import gesture_controller.os_integration.linux_wayland_controller as linux_controller
from gesture_controller.os_integration.linux_wayland_controller import LinuxWaylandController

# Direct injection into module globals
linux_controller.evdev = mock_evdev
linux_controller.fcntl = mock_fcntl
linux_controller.struct = mock_struct

@pytest.fixture(autouse=True)
def reset_mocks() -> None:
    mock_evdev.reset_mock()
    mock_fcntl.reset_mock()
    mock_struct.reset_mock()

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
def test_linux_is_supported_on_linux(mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    assert ctrl.is_supported() is True

@patch("platform.system", return_value="Windows")
def test_linux_not_supported_on_windows(mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    assert ctrl.is_supported() is False

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
def test_linux_key_press_uinput(mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    assert ctrl._use_uinput is True
    
    ctrl.key_press("a", modifiers=["ctrl"])
    
    # Verify EV_KEY event written for ctrl (29) and a (30)
    assert mock_write.call_count >= 2

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
def test_linux_mouse_scroll_uinput(mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    ctrl.mouse_scroll(delta_y=-2)
    
    # Verify vertical scroll REL_WHEEL (8) event emitted
    assert mock_write.call_count >= 1

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_key_press_xdotool_fallback(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    # Force uinput creation failure to test xdotool fallback
    mock_open.side_effect = PermissionError()
    
    ctrl = LinuxWaylandController()
    assert ctrl._use_uinput is False
    
    ctrl.key_press("a", modifiers=["ctrl"])
    # Verify subprocess called xdotool keydown
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0][0] == "xdotool"
    assert mock_run.call_args[0][0][1] == "keydown"
    assert mock_run.call_args[0][0][2] == "ctrl+a"

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("os.environ", {"XDG_SESSION_TYPE": "wayland"})
@patch("subprocess.run")
def test_linux_get_foreground_app_sway(mock_run: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    ctrl._window_manager = "sway"
    
    # Mock swaymsg get_tree response
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = '{"focused": false, "nodes": [{"focused": true, "type": "con", "app_id": "Firefox"}]}'
    mock_run.return_value = mock_res
    
    assert ctrl.get_foreground_app() == "firefox"

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("os.environ", {"XDG_SESSION_TYPE": "wayland"})
@patch("subprocess.run")
def test_linux_get_foreground_app_hyprland(mock_run: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    ctrl._window_manager = "hyprland"
    
    # Mock hyprctl activewindow response
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = '{"class": "kitty"}'
    mock_run.return_value = mock_res
    
    assert ctrl.get_foreground_app() == "kitty"

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("subprocess.run")
def test_linux_minimize_active_window(mock_run: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    ctrl._window_manager = "sway"
    
    ctrl.minimize_active_window()
    # Verify swaymsg move scratchpad called
    mock_run.assert_called_once_with(["swaymsg", "[focused] move scratchpad"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("subprocess.run")
def test_linux_media_keys_playerctl(mock_run: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    # Force uinput failure
    mock_open.side_effect = PermissionError()
    
    ctrl = LinuxWaylandController()
    ctrl.media_play_pause()
    
    # Verify playerctl subprocess
    mock_run.assert_called_once_with(["playerctl", "play-pause"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_key_release_uinput_and_xdotool(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    # 1. uinput path
    ctrl = LinuxWaylandController()
    ctrl.key_release("a")
    assert mock_write.call_count >= 1
    
    # 2. xdotool fallback path
    mock_open.side_effect = PermissionError()
    ctrl_x = LinuxWaylandController()
    ctrl_x.key_release("a")
    mock_run.assert_called_with(["xdotool", "keyup", "a"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_key_combo(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    # 1. uinput path
    ctrl = LinuxWaylandController()
    ctrl.key_combo(["ctrl", "alt", "c"])
    assert mock_write.call_count >= 1
    
    # 2. xdotool path
    mock_open.side_effect = PermissionError()
    ctrl_x = LinuxWaylandController()
    ctrl_x.key_combo(["ctrl", "alt", "c"])
    mock_run.assert_called_with(["xdotool", "key", "ctrl+alt+c"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_mouse_double_click(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    # 1. uinput path
    ctrl = LinuxWaylandController()
    ctrl.mouse_double_click("left")
    assert mock_write.call_count >= 1
    
    # 2. xdotool path
    mock_open.side_effect = PermissionError()
    ctrl_x = LinuxWaylandController()
    ctrl_x.mouse_double_click("left", 100, 200)
    mock_run.assert_called_with(["xdotool", "click", "--repeat", "2", "1"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_mouse_move(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    # 1. uinput relative move
    ctrl = LinuxWaylandController()
    ctrl.mouse_move(10, -20, absolute=False)
    assert mock_write.call_count >= 2
    
    # 2. xdotool absolute move
    mock_open.side_effect = PermissionError()
    ctrl_x = LinuxWaylandController()
    ctrl_x.mouse_move(100, 200, absolute=True)
    mock_run.assert_called_with(["xdotool", "mousemove", "100", "200"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_mouse_scroll_xdotool(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    mock_open.side_effect = PermissionError()
    ctrl = LinuxWaylandController()
    ctrl.mouse_scroll(delta_y=2)
    # verify vertical scroll up button 4 clicked twice
    assert mock_run.call_count == 2
    mock_run.assert_called_with(["xdotool", "click", "4"], capture_output=True)

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("subprocess.run")
def test_linux_window_manager_actions(mock_run: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    ctrl._window_manager = "xdotool"
    
    ctrl.switch_window()
    # verify alt+tab triggered
    
    ctrl.show_desktop()
    # verify super+d triggered

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("subprocess.run")
def test_linux_media_keys_uinput(mock_run: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    ctrl.media_next()
    ctrl.media_previous()
    ctrl.media_volume_up()
    ctrl.media_volume_down()
    assert mock_write.call_count >= 4

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("shutil.which", return_value="/usr/bin/xdotool")
@patch("subprocess.run")
def test_linux_get_foreground_app_xdotool(mock_run: MagicMock, mock_which: MagicMock, mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    mock_open.side_effect = PermissionError()
    ctrl = LinuxWaylandController()
    
    mock_res_id = MagicMock()
    mock_res_id.returncode = 0
    mock_res_id.stdout = "12345\n"
    
    mock_res_class = MagicMock()
    mock_res_class.returncode = 0
    mock_res_class.stdout = "Gnome-terminal\n"
    
    mock_run.side_effect = [mock_res_id, mock_res_class]
    
    assert ctrl.get_foreground_app() == "gnome-terminal"

@patch("platform.system", return_value="Linux")
@patch("os.open", return_value=99)
@patch("os.write")
@patch("os.environ", {"KDE_SESSION_VERSION": "5"})
def test_linux_detect_window_manager_kde(mock_write: MagicMock, mock_open: MagicMock, mock_system: MagicMock) -> None:
    ctrl = LinuxWaylandController()
    assert ctrl._window_manager == "kwin"

