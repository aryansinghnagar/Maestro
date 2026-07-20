import sys
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from gesture_controller.cli.cli import main


@patch("urllib.request.urlopen")
@patch("sys.argv")
def test_cli_trigger_and_status(mock_argv: MagicMock, mock_urlopen: MagicMock) -> None:
    # 1. Test trigger subcommand
    mock_argv.copy.return_value = ["maestro", "trigger", "SwipeLeft"]
    # Setup mock urlopen response
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "ok", "message": "Triggered SwipeLeft"}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    with patch("sys.argv", ["maestro", "trigger", "SwipeLeft"]):
        main()

    assert mock_urlopen.called

    # 2. Test status subcommand
    mock_urlopen.reset_mock()
    mock_resp.read.return_value = b'{"status": "running"}'

    with patch("sys.argv", ["maestro", "status"]):
        main()

    assert mock_urlopen.called


@patch("sys.argv")
def test_cli_package_manager(mock_argv: MagicMock, tmp_path: Path) -> None:
    # Test search command
    with patch("sys.argv", ["maestro", "search", "media"]), patch("builtins.print") as mock_print:
        main()
        # Should print matching plugin names
        mock_print.assert_any_call("Found 1 matching plugin(s):")

    # Test install command
    # Mock data directories to use tmp_path
    with patch("gesture_controller.core.compliance.get_user_data_dirs", return_value=[tmp_path]):
        with patch("sys.argv", ["maestro", "install", "test-plugin"]):
            main()
            plugin_dir = tmp_path / "plugins" / "test-plugin"
            assert plugin_dir.exists()
            assert (plugin_dir / "maestro.toml").exists()

        # Test remove command
        with patch("sys.argv", ["maestro", "remove", "test-plugin"]):
            main()
            assert not plugin_dir.exists()
