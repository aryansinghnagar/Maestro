import os
import platform
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication
from gesture_controller.gui.onboarding import (
    OnboardingWizard,
    is_onboarded,
    get_onboarded_marker_path,
)


@pytest.fixture(autouse=True)
def clean_onboarding_marker():
    """Ensure the onboarding marker file is removed before and after testing."""
    marker = get_onboarded_marker_path()
    if marker.exists():
        try:
            marker.unlink()
        except OSError:
            pass
    yield
    if marker.exists():
        try:
            marker.unlink()
        except OSError:
            pass


def test_is_onboarded_initially_false() -> None:
    assert is_onboarded() is False


def test_get_onboarded_marker_path() -> None:
    path = get_onboarded_marker_path()
    assert isinstance(path, Path)
    assert path.name == ".onboarded"


def test_onboarding_wizard_completes(qapp) -> None:
    # Verify wizard writes marker file on accept
    wizard = OnboardingWizard()
    assert is_onboarded() is False

    wizard.complete_onboarding()
    assert is_onboarded() is True


@patch("platform.system", return_value="Windows")
@patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=1, create=True)
def test_onboarding_windows_admin(mock_admin, mock_sys, qapp) -> None:
    wizard = OnboardingWizard()
    wizard.check_permissions()
    assert wizard.os_status.text() == "✅ Running as Administrator"


@patch("platform.system", return_value="Windows")
@patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0, create=True)
def test_onboarding_windows_standard_user(mock_admin, mock_sys, qapp) -> None:
    wizard = OnboardingWizard()
    wizard.check_permissions()
    assert wizard.os_status.text() == "⚠️ Standard User (UIPI Enabled)"


@patch("platform.system", return_value="Darwin")
def test_onboarding_darwin_permissions(mock_sys, qapp) -> None:
    # Mock AVFoundation and ApplicationServices modules
    mock_av = MagicMock()
    mock_av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 3  # Authorized

    mock_app_serv = MagicMock()
    mock_app_serv.AXIsProcessTrusted.return_value = True

    import sys

    sys.modules["AVFoundation"] = mock_av
    sys.modules["ApplicationServices"] = mock_app_serv

    try:
        wizard = OnboardingWizard()
        wizard.check_permissions()
        assert wizard.cam_status.text() == "✅ Access Granted"
        assert wizard.os_status.text() == "✅ Process Trusted"
        assert wizard.next_btn.isEnabled() is True
    finally:
        sys.modules.pop("AVFoundation", None)
        sys.modules.pop("ApplicationServices", None)


@patch("platform.system", return_value="Linux")
@patch("os.access", return_value=True)
def test_onboarding_linux_permissions(mock_access, mock_sys, qapp) -> None:
    wizard = OnboardingWizard()
    wizard.check_permissions()
    assert wizard.os_status.text() == "✅ /dev/uinput Writable"


def test_onboarding_accessibility_names(qapp) -> None:
    wizard = OnboardingWizard()
    assert wizard.help_btn.accessibleName() == "Grant System Permission Button"
    assert wizard.check_btn.accessibleName() == "Re-check System Permissions Button"
    assert wizard.next_btn.accessibleName() == "Continue to Application Button"
