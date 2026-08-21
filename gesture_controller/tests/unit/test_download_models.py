import pytest
from pathlib import Path
from unittest.mock import patch

from scripts import download_models


@pytest.fixture
def temp_model_path(tmp_path: Path):
    """Provide a temporary model file path for testing download behavior."""
    original_file = download_models.TARGET_FILE
    temp_file = tmp_path / "hand_landmarker.task"
    download_models.TARGET_FILE = temp_file
    yield temp_file
    download_models.TARGET_FILE = original_file


def test_download_model_already_exists(temp_model_path: Path) -> None:
    # Create the dummy file
    temp_model_path.touch()
    assert temp_model_path.exists()

    # Run downloader with verified sha256 mock: should skip download and return 0
    with (
        patch("scripts.download_models.verify_sha256", return_value=True),
        patch("urllib.request.urlretrieve") as mock_retrieve,
    ):
        code = download_models.download_model()
        assert code == 0
        mock_retrieve.assert_not_called()


def test_download_model_performs_download(temp_model_path: Path) -> None:
    # Target file does not exist
    assert not temp_model_path.exists()

    # Run downloader: should call urlretrieve, verify sha256, and return 0
    with (
        patch("scripts.download_models.verify_sha256", return_value=True),
        patch("urllib.request.urlretrieve") as mock_retrieve,
    ):

        def side_effect(url, filepath, reporthook=None):
            Path(filepath).touch()

        mock_retrieve.side_effect = side_effect

        code = download_models.download_model()
        assert code == 0
        mock_retrieve.assert_called_once()
        assert temp_model_path.exists()


def test_download_model_checksum_mismatch(temp_model_path: Path) -> None:
    assert not temp_model_path.exists()

    # If verification fails, download must be aborted and return 1
    with (
        patch("scripts.download_models.verify_sha256", return_value=False),
        patch("urllib.request.urlretrieve") as mock_retrieve,
    ):

        def side_effect(url, filepath, reporthook=None):
            Path(filepath).touch()

        mock_retrieve.side_effect = side_effect

        code = download_models.download_model()
        assert code == 1
        assert not temp_model_path.exists()


def test_download_model_reports_exception(temp_model_path: Path) -> None:
    assert not temp_model_path.exists()

    # Run downloader: should catch exception and return 1
    with patch("urllib.request.urlretrieve", side_effect=ValueError("Network down")):
        code = download_models.download_model()
        assert code == 1
