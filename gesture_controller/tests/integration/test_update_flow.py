"""Integration tests: Auto-updater end-to-end flow (Sprint 15).

Tests the full sequence:
1. check_for_update() finds a newer version via mocked GitHub API
2. download_update() streams the asset to disk
3. apply_update() extracts the archive

All network calls are mocked so tests run fully offline.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_release(tag: str, prerelease: bool = False) -> dict:
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "html_url": f"https://github.com/test/maestro/releases/tag/{tag}",
        "body": f"Release notes for {tag}",
        "assets": [
            {
                "name": f"maestro-{tag.lstrip('v')}-win.zip",
                "browser_download_url": f"https://example.com/dl/maestro-{tag.lstrip('v')}-win.zip",
                "size": 50_000,
            }
        ],
    }


def _mock_urlopen_releases(releases: list[dict]):
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(releases).encode("utf-8")
    return mock_resp


def _make_zip_bytes(filename: str = "app.txt", content: bytes = b"app content") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _mock_urlopen_download(payload: bytes, content_length: int | None = None):
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.headers.get.return_value = str(content_length or len(payload))
    # Simulate chunked reads: first call returns payload, then empty bytes
    mock_resp.read.side_effect = [payload, b""]
    return mock_resp


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestUpdateFlow:
    def test_check_finds_newer_stable_release(self) -> None:
        """check_for_update returns ReleaseInfo when a newer stable release exists."""
        from gesture_controller.core.updater import check_for_update, UpdateChannel

        releases = [_fake_release("v2.0.0"), _fake_release("v1.5.0")]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_releases(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)

        assert result is not None
        assert result.version == "2.0.0"

    def test_check_returns_none_when_current(self) -> None:
        """check_for_update returns None when no newer release exists."""
        from gesture_controller.core.updater import check_for_update, UpdateChannel

        releases = [_fake_release("v1.0.0")]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_releases(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)

        assert result is None

    def test_check_stable_skips_prerelease(self) -> None:
        """Stable channel does not pick up beta releases."""
        from gesture_controller.core.updater import check_for_update, UpdateChannel

        releases = [_fake_release("v2.0.0-beta", prerelease=True)]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_releases(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)

        assert result is None

    def test_check_nightly_includes_prereleases(self) -> None:
        """Nightly channel picks up prerelease builds."""
        from gesture_controller.core.updater import check_for_update, UpdateChannel

        releases = [_fake_release("v2.0.0-nightly.001", prerelease=True)]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_releases(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.NIGHTLY)

        assert result is not None

    def test_download_creates_file_on_disk(self, tmp_path) -> None:
        """download_update streams the asset and writes it to the destination."""
        from gesture_controller.core.updater import download_update

        payload = _make_zip_bytes()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_download(payload)):
            path = download_update("https://example.com/dl/maestro-2.0.0-win.zip", dest=tmp_path)

        assert path.exists()
        assert path.name == "maestro-2.0.0-win.zip"
        assert path.stat().st_size > 0

    def test_download_progress_callback_receives_updates(self, tmp_path) -> None:
        """Progress callback is invoked during download."""
        from gesture_controller.core.updater import download_update

        payload = _make_zip_bytes(content=b"x" * 100_000)
        progress_calls = []

        with patch("urllib.request.urlopen", return_value=_mock_urlopen_download(payload)):
            download_update(
                "https://example.com/dl/update.zip",
                dest=tmp_path,
                progress_callback=lambda r, t: progress_calls.append((r, t)),
            )

        assert len(progress_calls) >= 1
        assert all(r > 0 for r, _ in progress_calls)

    def test_apply_extracts_zip(self, tmp_path) -> None:
        """apply_update extracts a zip archive correctly."""
        from gesture_controller.core.updater import apply_update

        archive = tmp_path / "maestro-2.0.0.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("maestro/app.txt", "app content here")

        extract_dir = tmp_path / "extracted"
        result = apply_update(archive, extract_dir=extract_dir)

        assert result is True
        assert (extract_dir / "maestro" / "app.txt").exists()

    def test_full_check_download_apply_flow(self, tmp_path) -> None:
        """End-to-end: check finds release → download asset → apply archive."""
        from gesture_controller.core.updater import check_for_update, download_update, apply_update, UpdateChannel

        # 1. Check
        releases = [_fake_release("v3.0.0")]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_releases(releases)):
            release = check_for_update("2.0.0", channel=UpdateChannel.STABLE)
        assert release is not None
        assert release.version == "3.0.0"

        # 2. Build a fake asset
        asset_url = release.assets[0].url
        payload = _make_zip_bytes("maestro/README.txt", b"Maestro v3.0.0")

        # 3. Download
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_download(payload)):
            archive = download_update(asset_url, dest=tmp_path)
        assert archive.exists()

        # 4. Apply
        extract_dir = tmp_path / "extracted"
        assert apply_update(archive, extract_dir=extract_dir) is True
        assert (extract_dir / "maestro" / "README.txt").exists()

    def test_network_error_during_check_handled_gracefully(self) -> None:
        """check_for_update returns None (not raises) on network failure."""
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)
        assert result is None

    def test_network_error_during_download_raises_oserror(self, tmp_path) -> None:
        """download_update raises OSError on network failure."""
        from gesture_controller.core.updater import download_update
        with patch("urllib.request.urlopen", side_effect=OSError("connection reset")):
            with pytest.raises(OSError):
                download_update("https://example.com/dl/update.zip", dest=tmp_path)
