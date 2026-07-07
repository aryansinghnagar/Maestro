"""Integration tests for scripts/verify_install.py.
Verifies that all diagnostics report correctly.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gesture_controller.cli import verify_install


def test_verify_install_success() -> None:
    """Verify verify_install.main returns 0 when all sub-checks pass."""
    with patch("cv2.VideoCapture") as mock_capture:
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        exit_code = verify_install.main()
        assert exit_code == 0


def test_verify_install_camera_fails() -> None:
    """Verify verify_install.main returns 1 when camera check fails."""
    with patch("cv2.VideoCapture") as mock_capture:
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = False
        mock_capture.return_value = mock_cap_instance

        exit_code = verify_install.main()
        assert exit_code == 1
