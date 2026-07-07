import pytest
from unittest.mock import MagicMock, patch

# Setup mock constants
mock_quartz = MagicMock()
mock_appkit = MagicMock()
mock_appservices = MagicMock()

mock_quartz.kCGEventFlagMaskCommand = 0x0001
mock_quartz.kCGEventFlagMaskShift = 0x0002
mock_quartz.kCGEventFlagMaskControl = 0x0004
mock_quartz.kCGEventFlagMaskAlternate = 0x0008
mock_quartz.kCGHIDEventTap = 0
mock_quartz.kCGEventLeftMouseDown = 1
mock_quartz.kCGEventLeftMouseUp = 2
mock_quartz.kCGEventRightMouseDown = 3
mock_quartz.kCGEventRightMouseUp = 4
mock_quartz.kCGMouseButtonLeft = 0
mock_quartz.kCGMouseButtonRight = 1
mock_quartz.kCGMouseButtonCenter = 2
mock_quartz.kCGMouseEventClickState = 3

import gesture_controller.os_integration.macos_controller as macos_controller
from gesture_controller.os_integration.macos_controller import MacOSController

# Direct injection into module globals
macos_controller.Quartz = mock_quartz
macos_controller.AppKit = mock_appkit
macos_controller.ApplicationServices = mock_appservices
macos_controller.MAC_MODIFIER_FLAGS = {
    "cmd": 0x0001,
    "shift": 0x0002,
    "ctrl": 0x0004,
    "alt": 0x0008,
}


@pytest.fixture(autouse=True)
def reset_mocks() -> None:
    mock_quartz.reset_mock()
    mock_appkit.reset_mock()
    mock_appservices.reset_mock()


@patch("platform.system", return_value="Darwin")
def test_macos_is_supported_on_darwin(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    assert ctrl.is_supported() is True


@patch("platform.system", return_value="Windows")
def test_macos_not_supported_on_windows(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    assert ctrl.is_supported() is False


@patch("platform.system", return_value="Darwin")
def test_macos_key_press(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    ctrl.key_press("a", modifiers=["ctrl"])

    mock_quartz.CGEventCreateKeyboardEvent.assert_called_once_with(None, 0x00, True)
    mock_quartz.CGEventSetFlags.assert_called_once_with(
        mock_quartz.CGEventCreateKeyboardEvent.return_value, 0x0004
    )
    mock_quartz.CGEventPost.assert_called_once()


@patch("platform.system", return_value="Darwin")
def test_macos_key_combo(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    # command + shift + a
    ctrl.key_combo(["cmd", "shift", "a"])

    # Verify modifiers down called
    assert mock_quartz.CGEventCreateKeyboardEvent.call_count >= 4
    # Modifiers key codes: cmd=55, shift=56
    # Main key: a=0x00
    calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
    assert any(call[0][1] == 55 and call[0][2] is True for call in calls)
    assert any(call[0][1] == 56 and call[0][2] is True for call in calls)
    assert any(call[0][1] == 0x00 and call[0][2] is True for call in calls)


@patch("platform.system", return_value="Darwin")
def test_macos_mouse_click(mock_system: MagicMock) -> None:
    ctrl = MacOSController()

    # Mock mouse position
    mock_loc = MagicMock()
    mock_loc.x = 150.0
    mock_loc.y = 250.0
    mock_quartz.CGEventGetLocation.return_value = mock_loc

    ctrl.mouse_click("left")

    # Verify mouseDown and mouseUp events created
    assert mock_quartz.CGEventCreateMouseEvent.call_count == 2
    assert mock_quartz.CGEventPost.call_count == 2


@patch("platform.system", return_value="Darwin")
def test_macos_mouse_scroll(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    ctrl.mouse_scroll(delta_y=-3)

    # Verify vertical scroll event posted
    mock_quartz.CGEventCreateScrollWheelEvent.assert_called_once_with(None, 0, 1, -3)
    mock_quartz.CGEventPost.assert_called_once()


@patch("platform.system", return_value="Darwin")
def test_macos_get_foreground_app(mock_system: MagicMock) -> None:
    ctrl = MacOSController()

    # Mock NSWorkspace active application info
    mock_app = MagicMock()
    mock_app.localizedName.return_value = "Google Chrome"
    mock_appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication.return_value = (
        mock_app
    )

    assert ctrl.get_foreground_app() == "google chrome"


@patch("platform.system", return_value="Darwin")
def test_macos_minimize_active_window(mock_system: MagicMock) -> None:
    ctrl = MacOSController()

    mock_app = MagicMock()
    mock_app.processIdentifier.return_value = 1234
    mock_appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication.return_value = (
        mock_app
    )

    # Mock accessibility API
    mock_window = MagicMock()
    mock_btn = MagicMock()

    # AXUIElementCopyAttributeValue mock response
    # 1. Focused window query: return window
    # 2. Minimize button query: return btn
    mock_appservices.AXUIElementCopyAttributeValue.side_effect = [(0, mock_window), (0, mock_btn)]

    ctrl.minimize_active_window()

    # Verify Accessibility perform action was called
    mock_appservices.AXUIElementPerformAction.assert_called_once_with(mock_btn, "AXPress")


@patch("platform.system", return_value="Darwin")
def test_macos_key_release(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    ctrl.key_release("a")
    mock_quartz.CGEventCreateKeyboardEvent.assert_called_once_with(None, 0x00, False)


@patch("platform.system", return_value="Darwin")
def test_macos_mouse_double_click(mock_system: MagicMock) -> None:
    ctrl = MacOSController()

    mock_loc = MagicMock()
    mock_loc.x = 100.0
    mock_loc.y = 200.0
    mock_quartz.CGEventGetLocation.return_value = mock_loc

    ctrl.mouse_double_click("left")
    assert mock_quartz.CGEventCreateMouseEvent.call_count == 2
    # Verify click state set to 2 for double click
    mock_quartz.CGEventSetIntegerValueField.assert_any_call(
        mock_quartz.CGEventCreateMouseEvent.return_value, mock_quartz.kCGMouseEventClickState, 2
    )


@patch("platform.system", return_value="Darwin")
def test_macos_mouse_move(mock_system: MagicMock) -> None:
    ctrl = MacOSController()

    # 1. Absolute move
    ctrl.mouse_move(300, 400, absolute=True)
    mock_quartz.CGEventCreateMouseEvent.assert_called_with(
        None, mock_quartz.kCGEventMouseMoved, mock_quartz.CGPoint(300, 400), 0
    )

    # 2. Relative move
    mock_loc = MagicMock()
    mock_loc.x = 100.0
    mock_loc.y = 100.0
    mock_quartz.CGEventGetLocation.return_value = mock_loc
    ctrl.mouse_move(50, 50, absolute=False)
    # Expected target is 100 + 50 = 150, 100 + 50 = 150
    mock_quartz.CGEventCreateMouseEvent.assert_called_with(
        None, mock_quartz.kCGEventMouseMoved, mock_quartz.CGPoint(150, 150), 0
    )


@patch("platform.system", return_value="Darwin")
def test_macos_switch_window(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    ctrl.switch_window()
    # verify cmd + tab sent
    assert mock_quartz.CGEventCreateKeyboardEvent.call_count >= 2


@patch("platform.system", return_value="Darwin")
def test_macos_show_desktop(mock_system: MagicMock) -> None:
    ctrl = MacOSController()
    ctrl.show_desktop()
    # verify f11 sent (keycode 0x67)
    calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
    assert any(call[0][1] == 0x67 for call in calls)


@patch("platform.system", return_value="Darwin")
def test_macos_media_controls(mock_system: MagicMock) -> None:
    ctrl = MacOSController()

    # Mock NSEvent creation
    mock_appkit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_.return_value = (
        MagicMock()
    )

    ctrl.media_play_pause()
    ctrl.media_next()
    ctrl.media_previous()
    ctrl.media_volume_up()
    ctrl.media_volume_down()

    # Verify that mock_appkit NSEvent was called 10 times (2 calls each for down/up states)
    assert (
        mock_appkit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_.call_count
        == 10
    )
