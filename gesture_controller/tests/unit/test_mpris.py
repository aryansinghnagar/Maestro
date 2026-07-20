import sys
from unittest.mock import patch, MagicMock
import pytest

from gesture_controller.os_integration.mpris_media import (
    mpris_play_pause,
    mpris_next,
    mpris_previous,
)


@patch("subprocess.run")
@patch("subprocess.Popen")
def test_mpris_commands(mock_popen: MagicMock, mock_run: MagicMock) -> None:
    # Setup mocks
    mock_p = MagicMock()
    mock_p.communicate.return_value = (b'string "org.mpris.MediaPlayer2.vlc"', None)
    mock_popen.return_value = mock_p

    # Test Play/Pause
    mpris_play_pause()
    assert mock_run.called

    # Test Next
    mock_run.reset_mock()
    mpris_next()
    assert mock_run.called

    # Test Previous
    mock_run.reset_mock()
    mpris_previous()
    assert mock_run.called
