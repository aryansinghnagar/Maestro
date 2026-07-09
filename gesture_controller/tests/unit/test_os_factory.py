import sys
import platform
from unittest.mock import MagicMock, patch
import pytest

# Mock modules for Darwin/Linux to allow factory resolution without ImportError
mock_quartz = MagicMock()
mock_appkit = MagicMock()
mock_evdev = MagicMock()
mock_fcntl = MagicMock()

sys.modules["Quartz"] = mock_quartz
sys.modules["AppKit"] = mock_appkit
sys.modules["evdev"] = mock_evdev
sys.modules["fcntl"] = mock_fcntl

from gesture_controller.os_integration import create_controller
from gesture_controller.os_integration.windows_controller import WindowsController
from gesture_controller.os_integration.macos_controller import MacOSController
from gesture_controller.os_integration.linux_controller import LinuxController
from gesture_controller.os_integration.broker import BrokerClientController


def test_factory_returns_broker_controller_by_default() -> None:
    ctrl = create_controller()
    assert isinstance(ctrl, BrokerClientController)


@patch("platform.system", return_value="Windows")
@patch(
    "gesture_controller.os_integration.windows_controller.WindowsController.is_supported",
    return_value=True,
)
def test_factory_returns_windows_controller(
    mock_supported: MagicMock, mock_system: MagicMock
) -> None:
    ctrl = create_controller(use_broker=False)
    assert isinstance(ctrl, WindowsController)


@patch("platform.system", return_value="Darwin")
@patch(
    "gesture_controller.os_integration.macos_controller.MacOSController.is_supported",
    return_value=True,
)
def test_factory_returns_macos_controller(
    mock_supported: MagicMock, mock_system: MagicMock
) -> None:
    ctrl = create_controller(use_broker=False)
    assert isinstance(ctrl, MacOSController)


@patch("platform.system", return_value="Linux")
@patch(
    "gesture_controller.os_integration.linux_controller.LinuxController.is_supported",
    return_value=True,
)
def test_factory_returns_linux_controller(
    mock_supported: MagicMock, mock_system: MagicMock
) -> None:
    ctrl = create_controller(use_broker=False)
    assert isinstance(ctrl, LinuxController)


@patch("platform.system", return_value="FreeBSD")
def test_factory_raises_runtime_error_on_unsupported_os(mock_system: MagicMock) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        create_controller(use_broker=False)
    assert "No supported OS controller found for platform: FreeBSD" in str(excinfo.value)
