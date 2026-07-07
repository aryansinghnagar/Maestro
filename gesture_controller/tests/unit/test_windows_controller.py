import sys
import platform
import pytest
from unittest.mock import MagicMock, patch, call

# Mock ctypes before importing WindowsController to avoid dependency errors on non-Windows
mock_windll = MagicMock()
mock_user32 = MagicMock()
mock_windll.user32 = mock_user32

sys.modules["ctypes.wintypes"] = MagicMock()

with (
    patch("platform.system", return_value="Windows"),
    patch("ctypes.windll", mock_windll, create=True),
):
    from gesture_controller.os_integration.windows_controller import WindowsController


@pytest.fixture
def mock_ctypes():
    with patch("gesture_controller.os_integration.windows_controller.ctypes") as mock_c:
        # Mock GetForegroundWindow to return a dummy handle
        mock_c.windll.user32.GetForegroundWindow.return_value = 12345
        mock_c.windll.user32.GetWindowTextLengthW.return_value = 10
        # Mock Unicode buffer for GetWindowTextW
        buf = MagicMock()
        buf.value = "Test Window"
        mock_c.create_unicode_buffer.return_value = buf
        mock_c.windll.user32.GetWindowTextW.return_value = None
        mock_c.c_ulong.return_value = MagicMock()
        mock_c.windll.user32.GetWindowThreadProcessId.return_value = None
        yield mock_c


@patch("platform.system", return_value="Windows")
def test_windows_is_supported(mock_sys) -> None:
    ctrl = WindowsController()
    assert ctrl.is_supported() is True


@patch("platform.system", return_value="Linux")
def test_windows_not_supported_on_linux(mock_sys) -> None:
    with pytest.raises(RuntimeError):
        WindowsController()


@patch("platform.system", return_value="Windows")
def test_windows_key_press(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()

    # Simple key press
    ctrl.key_press("a")
    # Should call SendInput twice (keydown, keyup)
    assert mock_ctypes.windll.user32.SendInput.call_count == 2

    # Key press with modifiers
    mock_ctypes.windll.user32.SendInput.reset_mock()
    ctrl.key_press("a", modifiers=["ctrl", "alt"])
    # 2 modifiers keydown, 1 key keydown, 1 key keyup, 2 modifiers keyup = 6 SendInput calls
    assert mock_ctypes.windll.user32.SendInput.call_count == 6


@patch("platform.system", return_value="Windows")
def test_windows_key_release(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()
    ctrl.key_release("super")
    assert mock_ctypes.windll.user32.SendInput.call_count == 1


@patch("platform.system", return_value="Windows")
def test_windows_key_combo(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()
    ctrl.key_combo(["ctrl", "alt", "delete"])
    # 3 keydowns, 3 keyups = 6 SendInput calls
    assert mock_ctypes.windll.user32.SendInput.call_count == 6


@patch("platform.system", return_value="Windows")
def test_windows_mouse_click(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()

    # Click at current position
    ctrl.mouse_click("left")
    # 1 down, 1 up = 2 SendInput calls
    assert mock_ctypes.windll.user32.SendInput.call_count == 2

    # Click at coordinate
    mock_ctypes.windll.user32.SendInput.reset_mock()
    ctrl.mouse_click("right", x=100, y=200)
    mock_ctypes.windll.user32.SetCursorPos.assert_called_once_with(100, 200)
    assert mock_ctypes.windll.user32.SendInput.call_count == 2


@patch("platform.system", return_value="Windows")
def test_windows_mouse_double_click(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()
    ctrl.mouse_double_click("left", x=150, y=250)
    mock_ctypes.windll.user32.SetCursorPos.assert_has_calls([call(150, 250), call(150, 250)])
    # 2 clicks * (1 down + 1 up) = 4 SendInput calls
    assert mock_ctypes.windll.user32.SendInput.call_count == 4


@patch("platform.system", return_value="Windows")
def test_windows_mouse_move(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()

    # Absolute move
    ctrl.mouse_move(10, 20, absolute=True)
    mock_ctypes.windll.user32.SetCursorPos.assert_called_once_with(10, 20)

    # Relative move
    mock_ctypes.windll.user32.SendInput.reset_mock()
    ctrl.mouse_move(5, -5, absolute=False)
    assert mock_ctypes.windll.user32.SendInput.call_count == 1


@patch("platform.system", return_value="Windows")
def test_windows_mouse_scroll(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()

    # Vertical scroll
    ctrl.mouse_scroll(delta_y=-5)
    assert mock_ctypes.windll.user32.SendInput.call_count == 1

    # Horizontal scroll
    mock_ctypes.windll.user32.SendInput.reset_mock()
    ctrl.mouse_scroll(delta_x=3)
    assert mock_ctypes.windll.user32.SendInput.call_count == 1


@patch("platform.system", return_value="Windows")
def test_windows_minimize_active_window(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()
    ctrl.minimize_active_window()
    mock_ctypes.windll.user32.GetForegroundWindow.assert_called_once()
    mock_ctypes.windll.user32.ShowWindow.assert_called_once_with(12345, 6)


@patch("platform.system", return_value="Windows")
def test_windows_shortcuts(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()

    # switch_window
    ctrl.switch_window()
    assert mock_ctypes.windll.user32.SendInput.call_count == 4  # alt down, tab down, tab up, alt up

    # show_desktop
    mock_ctypes.windll.user32.SendInput.reset_mock()
    ctrl.show_desktop()
    assert mock_ctypes.windll.user32.SendInput.call_count == 4  # win down, d down, d up, win up


@patch("platform.system", return_value="Windows")
def test_windows_media_controls(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()

    ctrl.media_play_pause()
    assert mock_ctypes.windll.user32.SendInput.call_count == 2

    ctrl.media_next()
    assert mock_ctypes.windll.user32.SendInput.call_count == 4

    ctrl.media_previous()
    assert mock_ctypes.windll.user32.SendInput.call_count == 6

    ctrl.media_volume_up()
    # 3 presses * 2 events = 6 events + 6 previous = 12 events
    assert mock_ctypes.windll.user32.SendInput.call_count == 12

    ctrl.media_volume_down()
    assert mock_ctypes.windll.user32.SendInput.call_count == 18


@patch("platform.system", return_value="Windows")
@patch("psutil.Process")
def test_windows_get_foreground_app(mock_psutil_proc, mock_sys, mock_ctypes) -> None:
    # Set up mock process name
    mock_proc = MagicMock()
    mock_proc.name.return_value = "Chrome.exe"
    mock_psutil_proc.return_value = mock_proc

    ctrl = WindowsController()
    app = ctrl.get_foreground_app()
    assert app == "chrome.exe"

    # Test traceback fallback to window title
    mock_psutil_proc.side_effect = Exception()
    app = ctrl.get_foreground_app()
    assert app == "test window"
