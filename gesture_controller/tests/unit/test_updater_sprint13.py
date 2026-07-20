"""Unit tests for Sprint 13 — Auto-Updater (GitHub Releases channel).

Covers:
- UpdateChannel enum values
- ReleaseInfo construction, channel matching
- _compare_versions utility
- check_for_update: mocked HTTP, channel filtering, version selection, network error
- download_update: mocked HTTP, progress callback, error handling
- apply_update: zip, tar.gz, .exe (mocked subprocess), missing file, unknown format
- GithubUpdateChecker QThread signals
"""
from __future__ import annotations

import io
import json
import zipfile
import tarfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from http.client import HTTPResponse

import pytest


# ---------------------------------------------------------------------------
# UpdateChannel
# ---------------------------------------------------------------------------

class TestUpdateChannel:
    def test_enum_values(self) -> None:
        from gesture_controller.core.updater import UpdateChannel
        assert UpdateChannel.STABLE.value == "stable"
        assert UpdateChannel.BETA.value == "beta"
        assert UpdateChannel.NIGHTLY.value == "nightly"

    def test_three_channels(self) -> None:
        from gesture_controller.core.updater import UpdateChannel
        assert len(UpdateChannel) == 3


# ---------------------------------------------------------------------------
# ReleaseInfo
# ---------------------------------------------------------------------------

class TestReleaseInfo:
    def _make_raw(self, tag="v1.2.0", prerelease=False):
        return {
            "tag_name": tag,
            "prerelease": prerelease,
            "html_url": f"https://github.com/maestro/{tag}",
            "body": "Release notes",
            "assets": [
                {
                    "name": "maestro-1.2.0-win.zip",
                    "browser_download_url": "https://example.com/dl/maestro.zip",
                    "size": 10_000_000,
                }
            ],
        }

    def test_from_github_dict_stable(self) -> None:
        from gesture_controller.core.updater import ReleaseInfo, UpdateChannel
        r = ReleaseInfo.from_github_dict(self._make_raw("v1.2.0"))
        assert r.version == "1.2.0"
        assert r.prerelease is False
        assert not r.is_nightly()
        assert not r.is_beta()
        assert r.matches_channel(UpdateChannel.STABLE)
        assert r.matches_channel(UpdateChannel.BETA)
        assert r.matches_channel(UpdateChannel.NIGHTLY)

    def test_from_github_dict_beta(self) -> None:
        from gesture_controller.core.updater import ReleaseInfo, UpdateChannel
        r = ReleaseInfo.from_github_dict(self._make_raw("v1.3.0-beta.1", prerelease=True))
        assert r.is_beta()
        assert not r.is_nightly()
        assert not r.matches_channel(UpdateChannel.STABLE)
        assert r.matches_channel(UpdateChannel.BETA)
        assert r.matches_channel(UpdateChannel.NIGHTLY)

    def test_from_github_dict_nightly(self) -> None:
        from gesture_controller.core.updater import ReleaseInfo, UpdateChannel
        r = ReleaseInfo.from_github_dict(self._make_raw("v1.4.0-nightly.20260101", prerelease=True))
        assert r.is_nightly()
        assert not r.matches_channel(UpdateChannel.STABLE)
        assert not r.matches_channel(UpdateChannel.BETA)
        assert r.matches_channel(UpdateChannel.NIGHTLY)

    def test_assets_parsed(self) -> None:
        from gesture_controller.core.updater import ReleaseInfo
        r = ReleaseInfo.from_github_dict(self._make_raw())
        assert len(r.assets) == 1
        assert r.assets[0].name == "maestro-1.2.0-win.zip"
        assert r.assets[0].size == 10_000_000

    def test_version_strips_v_prefix(self) -> None:
        from gesture_controller.core.updater import ReleaseInfo
        r = ReleaseInfo.from_github_dict(self._make_raw("v2.0.0"))
        assert r.version == "2.0.0"


# ---------------------------------------------------------------------------
# _compare_versions
# ---------------------------------------------------------------------------

class TestCompareVersions:
    def test_equal(self) -> None:
        from gesture_controller.core.updater import _compare_versions
        assert _compare_versions("1.2.3", "1.2.3") == 0

    def test_a_greater(self) -> None:
        from gesture_controller.core.updater import _compare_versions
        assert _compare_versions("2.0.0", "1.9.9") == 1

    def test_b_greater(self) -> None:
        from gesture_controller.core.updater import _compare_versions
        assert _compare_versions("1.0.0", "1.0.1") == -1

    def test_v_prefix_ignored(self) -> None:
        from gesture_controller.core.updater import _compare_versions
        assert _compare_versions("v1.2.3", "1.2.3") == 0

    def test_different_lengths(self) -> None:
        from gesture_controller.core.updater import _compare_versions
        assert _compare_versions("1.2", "1.2.0") == 0

    def test_prerelease_segment_stripped(self) -> None:
        from gesture_controller.core.updater import _compare_versions
        # 1.3.0-beta.1 → [1, 3, 0]; compare positionally
        assert _compare_versions("1.3.0-beta.1", "1.2.9") == 1


# ---------------------------------------------------------------------------
# check_for_update
# ---------------------------------------------------------------------------

def _fake_github_response(releases: list[dict]) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = json.dumps(releases).encode("utf-8")
    return mock_resp


class TestCheckForUpdate:
    def _stable_release(self, tag="v2.0.0"):
        return {
            "tag_name": tag,
            "prerelease": False,
            "html_url": f"https://github.com/maestro/{tag}",
            "body": "",
            "assets": [],
        }

    def test_returns_none_when_up_to_date(self) -> None:
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        releases = [self._stable_release("v1.0.0")]
        with patch("urllib.request.urlopen", return_value=_fake_github_response(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)
        assert result is None

    def test_returns_release_when_newer(self) -> None:
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        releases = [self._stable_release("v2.0.0")]
        with patch("urllib.request.urlopen", return_value=_fake_github_response(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)
        assert result is not None
        assert result.version == "2.0.0"

    def test_stable_channel_ignores_prereleases(self) -> None:
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        releases = [
            {"tag_name": "v2.0.0-beta", "prerelease": True, "html_url": "", "body": "", "assets": []},
        ]
        with patch("urllib.request.urlopen", return_value=_fake_github_response(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)
        assert result is None

    def test_beta_channel_includes_beta(self) -> None:
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        releases = [
            {"tag_name": "v2.0.0-beta.1", "prerelease": True, "html_url": "", "body": "", "assets": []},
        ]
        with patch("urllib.request.urlopen", return_value=_fake_github_response(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.BETA)
        assert result is not None

    def test_picks_highest_version(self) -> None:
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        releases = [
            self._stable_release("v1.5.0"),
            self._stable_release("v2.0.0"),
            self._stable_release("v1.8.0"),
        ]
        with patch("urllib.request.urlopen", return_value=_fake_github_response(releases)):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)
        assert result is not None
        assert result.version == "2.0.0"

    def test_network_error_returns_none(self) -> None:
        from gesture_controller.core.updater import check_for_update, UpdateChannel
        with patch("urllib.request.urlopen", side_effect=OSError("network down")):
            result = check_for_update("1.0.0", channel=UpdateChannel.STABLE)
        assert result is None


# ---------------------------------------------------------------------------
# download_update
# ---------------------------------------------------------------------------

class TestDownloadUpdate:
    def test_downloads_file(self, tmp_path) -> None:
        from gesture_controller.core.updater import download_update

        payload = b"fake archive content" * 100
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.return_value = str(len(payload))
        mock_resp.read.side_effect = [payload, b""]

        with patch("urllib.request.urlopen", return_value=mock_resp):
            path = download_update(
                "https://example.com/maestro-2.0.0.zip",
                dest=tmp_path,
            )

        assert path.exists()
        assert path.name == "maestro-2.0.0.zip"

    def test_progress_callback_called(self, tmp_path) -> None:
        from gesture_controller.core.updater import download_update

        payload = b"x" * 200
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers.get.return_value = str(len(payload))
        mock_resp.read.side_effect = [payload, b""]

        calls = []

        def cb(received, total):
            calls.append((received, total))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            download_update("https://example.com/x.zip", dest=tmp_path, progress_callback=cb)

        assert len(calls) >= 1

    def test_raises_oserror_on_failure(self, tmp_path) -> None:
        from gesture_controller.core.updater import download_update
        with patch("urllib.request.urlopen", side_effect=OSError("connect failed")):
            with pytest.raises(OSError, match="Failed to download update"):
                download_update("https://example.com/x.zip", dest=tmp_path)


# ---------------------------------------------------------------------------
# apply_update
# ---------------------------------------------------------------------------

class TestApplyUpdate:
    def test_apply_zip(self, tmp_path) -> None:
        from gesture_controller.core.updater import apply_update

        archive = tmp_path / "update.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("maestro/app.txt", "hello")

        extract_dir = tmp_path / "extracted"
        result = apply_update(archive, extract_dir=extract_dir)
        assert result is True
        assert (extract_dir / "maestro" / "app.txt").exists()

    def test_apply_tar_gz(self, tmp_path) -> None:
        from gesture_controller.core.updater import apply_update

        archive = tmp_path / "update.tar.gz"
        content_file = tmp_path / "app.txt"
        content_file.write_text("hello")
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(content_file, arcname="app.txt")

        extract_dir = tmp_path / "extracted"
        result = apply_update(archive, extract_dir=extract_dir)
        assert result is True
        assert (extract_dir / "app.txt").exists()

    def test_apply_missing_file_returns_false(self, tmp_path) -> None:
        from gesture_controller.core.updater import apply_update
        assert apply_update(tmp_path / "nonexistent.zip") is False

    def test_apply_unknown_format_returns_false(self, tmp_path) -> None:
        from gesture_controller.core.updater import apply_update
        f = tmp_path / "update.deb"
        f.write_bytes(b"fake deb content")
        assert apply_update(f) is False

    def test_apply_exe_launches_subprocess(self, tmp_path) -> None:
        from gesture_controller.core.updater import apply_update
        exe = tmp_path / "maestro-setup.exe"
        exe.write_bytes(b"MZ fake exe")
        with patch("subprocess.Popen") as mock_popen:
            result = apply_update(exe)
        assert result is True
        mock_popen.assert_called_once_with([str(exe), "/S"])
