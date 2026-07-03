import sys
import platform
import pytest
from unittest.mock import MagicMock, patch

# Mock ctypes before importing WindowsController to avoid dependency errors on non-Windows
mock_windll = MagicMock()
mock_user32 = MagicMock()
mock_windll.user32 = mock_user32

# Set up ctypes mocks so they don't crash on import/init
sys.modules["ctypes.wintypes"] = MagicMock()

with patch("platform.system", return_value="Windows"), \
     patch("ctypes.windll", mock_windll):
    from gesture_controller.os_integration.windows_controller import WindowsController

@pytest.fixture
def mock_pyautogui():
    with patch("gesture_controller.os_integration.windows_controller.pyautogui") as mock_pag:
        yield mock_pag

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
def test_windows_key_press(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    
    # Simple key press
    ctrl.key_press("a")
    mock_pyautogui.press.assert_called_once_with("a")
    
    # Key press with modifiers
    mock_pyautogui.reset_mock()
    ctrl.key_press("a", modifiers=["ctrl", "alt"])
    mock_pyautogui.hotkey.assert_called_once_with("ctrl", "alt", "a")
    
    # Normalized key press
    mock_pyautogui.reset_mock()
    ctrl.key_press("super")
    mock_pyautogui.press.assert_called_once_with("win")

@patch("platform.system", return_value="Windows")
def test_windows_key_release(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    ctrl.key_release("super")
    mock_pyautogui.keyUp.assert_called_once_with("win")

@patch("platform.system", return_value="Windows")
def test_windows_key_combo(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    ctrl.key_combo(["ctrl", "alt", "delete"])
    mock_pyautogui.hotkey.assert_called_once_with("ctrl", "alt", "delete")

@patch("platform.system", return_value="Windows")
def test_windows_mouse_click(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    
    # Click at current position
    ctrl.mouse_click("left")
    mock_pyautogui.click.assert_called_once_with(button="left")
    
    # Click at coordinate
    mock_pyautogui.reset_mock()
    ctrl.mouse_click("right", x=100, y=200)
    mock_pyautogui.click.assert_called_once_with(100, 200, button="right")

@patch("platform.system", return_value="Windows")
def test_windows_mouse_double_click(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    ctrl.mouse_double_click("left", x=150, y=250)
    mock_pyautogui.doubleClick.assert_called_once_with(150, 250, button="left")

@patch("platform.system", return_value="Windows")
def test_windows_mouse_move(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    
    # Absolute move
    ctrl.mouse_move(10, 20, absolute=True)
    mock_pyautogui.moveTo.assert_called_once_with(10, 20)
    
    # Relative move
    mock_pyautogui.reset_mock()
    ctrl.mouse_move(5, -5, absolute=False)
    mock_pyautogui.move.assert_called_once_with(5, -5)

@patch("platform.system", return_value="Windows")
def test_windows_mouse_scroll(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    
    # Vertical scroll
    ctrl.mouse_scroll(delta_y=-5)
    mock_pyautogui.scroll.assert_called_once_with(-5)
    
    # Horizontal scroll
    mock_pyautogui.reset_mock()
    ctrl.mouse_scroll(delta_x=3)
    mock_pyautogui.hscroll.assert_called_once_with(3)

@patch("platform.system", return_value="Windows")
def test_windows_minimize_active_window(mock_sys, mock_ctypes) -> None:
    ctrl = WindowsController()
    ctrl.minimize_active_window()
    mock_ctypes.windll.user32.GetForegroundWindow.assert_called_once()
    mock_ctypes.windll.user32.ShowWindow.assert_called_once_with(12345, 6)

@patch("platform.system", return_value="Windows")
def test_windows_shortcuts(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    
    # switch_window
    ctrl.switch_window()
    mock_pyautogui.hotkey.assert_any_call("alt", "tab")
    
    # show_desktop
    ctrl.show_desktop()
    mock_pyautogui.hotkey.assert_any_call("win", "d")

@patch("platform.system", return_value="Windows")
def test_windows_media_controls(mock_sys, mock_pyautogui) -> None:
    ctrl = WindowsController()
    
    ctrl.media_play_pause()
    mock_pyautogui.press.assert_any_call("playpause")
    
    ctrl.media_next()
    mock_pyautogui.press.assert_any_call("nexttrack")
    
    ctrl.media_previous()
    mock_pyautogui.press.assert_any_call("prevtrack")
    
    ctrl.media_volume_up()
    assert mock_pyautogui.press.call_count == 6  # 3 volume up, plus previous presses
    
    ctrl.media_volume_down()
    assert mock_pyautogui.press.call_count == 9  # 3 volume down

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
