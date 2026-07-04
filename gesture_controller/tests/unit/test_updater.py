import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication

from gesture_controller.core.updater import UpdateCheckerThread

def test_updater_is_newer() -> None:
    updater = UpdateCheckerThread("0.1.0")
    
    # Standard comparisons
    assert updater._is_newer("1.0.0", "0.1.0") is True
    assert updater._is_newer("0.1.1", "0.1.0") is True
    assert updater._is_newer("0.2.0", "0.1.5") is True
    assert updater._is_newer("0.1.0", "0.1.0") is False
    assert updater._is_newer("0.0.9", "0.1.0") is False
    
    # Version string format differences
    assert updater._is_newer("1.0.0.0", "1.0.0") is False
    assert updater._is_newer("1.0", "1.0.0") is False
    
    # Value error fallbacks
    assert updater._is_newer("abc", "1.0.0") is True

@patch("urllib.request.urlopen")
def test_updater_network_check_success(mock_urlopen, qapp: QApplication) -> None:
    updater = UpdateCheckerThread("0.1.0")
    
    # Mock network response returning new release
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"tag_name": "v1.0.0", "html_url": "https://github.com/test/releases/tag/v1.0.0"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    updates = []
    updater.update_available.connect(lambda v, url: updates.append((v, url)))
    
    # Run the QThread execution synchronously for testing
    updater.run()
    
    assert len(updates) == 1
    assert updates[0][0] == "1.0.0"
    assert updates[0][1] == "https://github.com/test/releases/tag/v1.0.0"

@patch("urllib.request.urlopen")
def test_updater_network_check_no_update(mock_urlopen, qapp: QApplication) -> None:
    updater = UpdateCheckerThread("1.0.0") # already at latest
    
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"tag_name": "v0.9.0", "html_url": "https://github.com/test"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    updates = []
    updater.update_available.connect(lambda v, url: updates.append((v, url)))
    
    updater.run()
    assert len(updates) == 0

@patch("urllib.request.urlopen")
def test_updater_network_check_failure(mock_urlopen, qapp: QApplication) -> None:
    updater = UpdateCheckerThread("0.1.0")
    mock_urlopen.side_effect = Exception("Connection timed out")
    
    errors = []
    updater.error.connect(lambda e: errors.append(e))
    
    updater.run()
    
    assert len(errors) == 1
    assert "Connection timed out" in errors[0]
