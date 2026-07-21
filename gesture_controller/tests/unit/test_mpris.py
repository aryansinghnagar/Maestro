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
def test_mpris_commands_dbus_send(mock_popen: MagicMock, mock_run: MagicMock) -> None:
    mock_p = MagicMock()
    mock_p.communicate.return_value = (b'string "org.mpris.MediaPlayer2.vlc"', None)
    mock_popen.return_value = mock_p

    mpris_play_pause()
    assert mock_run.called

    mock_run.reset_mock()
    mpris_next()
    assert mock_run.called

    mock_run.reset_mock()
    mpris_previous()
    assert mock_run.called


def test_mpris_commands_python_dbus_mock() -> None:
    mock_dbus = MagicMock()
    mock_bus = MagicMock()
    mock_player = MagicMock()

    mock_bus.list_names.return_value = ["org.mpris.MediaPlayer2.spotify"]
    mock_bus.get_object.return_value = mock_player
    mock_dbus.SessionBus.return_value = mock_bus

    with patch.dict("sys.modules", {"dbus": mock_dbus}):
        mpris_play_pause()
        mock_player.PlayPause.assert_called_once()

        mpris_next()
        mock_player.Next.assert_called_once()

        mpris_previous()
        mock_player.Previous.assert_called_once()


@patch("subprocess.run")
@patch("subprocess.Popen", side_effect=OSError("dbus-send not found"))
def test_mpris_commands_playerctl_fallback(mock_popen: MagicMock, mock_run: MagicMock) -> None:
    mpris_play_pause()
    mock_run.assert_called_with(["playerctl", "play-pause"], capture_output=True)

    mock_run.reset_mock()
    mpris_next()
    mock_run.assert_called_with(["playerctl", "next"], capture_output=True)

    mock_run.reset_mock()
    mpris_previous()
    mock_run.assert_called_with(["playerctl", "previous"], capture_output=True)
