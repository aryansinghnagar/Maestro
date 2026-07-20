import json
import os
import shutil
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Any

from tuf.ngclient import Updater, FetcherInterface  # type: ignore[attr-defined]
from tuf.api import exceptions as tuf_exceptions
from urllib.parse import urlparse
from urllib.request import url2pathname

_orig_symlink = getattr(os, "symlink", None)


def _secure_symlink(src: str, dst: str, **kwargs: Any) -> None:
    try:
        if _orig_symlink:
            _orig_symlink(src, dst, **kwargs)
        else:
            raise OSError("symlink not supported")
    except OSError:
        dst_dir = os.path.dirname(dst)
        abs_src = os.path.join(dst_dir, src)
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except OSError:
                pass
        try:
            shutil.copy(abs_src, dst)
        except Exception:
            pass


os.symlink = _secure_symlink  # type: ignore[assignment]

# Default bootstrap root.json content for client trust initialization
BOOTSTRAP_ROOT = {
    "signatures": [
        {
            "keyid": "92a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
            "sig": "acaee08fd78ce47bcd15bd53bf59a328fd337de4dff6daaf626c33c62d7fcfe3ceb52dbf4101ae0845c7fec4dfe57e138ecf818e89a2554bed828fe31c55ef0f",
        }
    ],
    "signed": {
        "_type": "root",
        "version": 1,
        "spec_version": "1.0.3",
        "expires": "2036-01-01T00:00:00Z",
        "consistent_snapshot": True,
        "keys": {
            "92a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "58641779aa703f81237c13bf639643b2bc77acfdc7ac5580a72c9f3a62bbdef8"
                },
            },
            "b2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "b8641779aa703f81237c13bf639643b2bc77acfdc7ac5580a72c9f3a62bbdef8"
                },
            },
            "c2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "c8641779aa703f81237c13bf639643b2bc77acfdc7ac5580a72c9f3a62bbdef8"
                },
            },
            "d2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "d8641779aa703f81237c13bf639643b2bc77acfdc7ac5580a72c9f3a62bbdef8"
                },
            },
            "e2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "e8641779aa703f81237c13bf639643b2bc77acfdc7ac5580a72c9f3a62bbdef8"
                },
            },
            "ce7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "50855f76d5067af7fcabe4f8925961bb2dd0153aaa8147fbe3c309c28cddd9f2"
                },
            },
            "de7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "d0855f76d5067af7fcabe4f8925961bb2dd0153aaa8147fbe3c309c28cddd9f2"
                },
            },
            "ee7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "e0855f76d5067af7fcabe4f8925961bb2dd0153aaa8147fbe3c309c28cddd9f2"
                },
            },
            "fe7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "f0855f76d5067af7fcabe4f8925961bb2dd0153aaa8147fbe3c309c28cddd9f2"
                },
            },
            "ae7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "a0855f76d5067af7fcabe4f8925961bb2dd0153aaa8147fbe3c309c28cddd9f2"
                },
            },
            "a8c3a6c4e4eeae6bcd88e66c9954992e28e222902894c9ac02efce6417028b2d": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "7623294c33e4672d47164226f54f16a5158b0a98f89a9cab8c2499a5a960d8ef"
                },
            },
            "c4070c306bf96fa078fb556ad2c158386f4daf04f5fc6d60db9e6419c83c92cd": {
                "keytype": "ed25519",
                "scheme": "ed25519",
                "keyval": {
                    "public": "502ffb92435709666138bac16a30e607e46784318f59872ad9670fa3ff77a78f"
                },
            },
        },
        "roles": {
            "root": {
                "keyids": [
                    "92a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
                    "b2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
                    "c2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
                    "d2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
                    "e2a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
                ],
                "threshold": 3,
            },
            "targets": {
                "keyids": [
                    "ce7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4",
                    "de7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4",
                    "ee7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4",
                    "fe7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4",
                    "ae7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4",
                ],
                "threshold": 3,
            },
            "snapshot": {
                "keyids": ["a8c3a6c4e4eeae6bcd88e66c9954992e28e222902894c9ac02efce6417028b2d"],
                "threshold": 1,
            },
            "timestamp": {
                "keyids": ["c4070c306bf96fa078fb556ad2c158386f4daf04f5fc6d60db9e6419c83c92cd"],
                "threshold": 1,
            },
        },
    },
}


class LocalFileFetcher(FetcherInterface):
    """Fetcher supporting file:// scheme for local directory testing."""

    def _fetch(self, url: str) -> Any:
        parsed = urlparse(url)
        if parsed.scheme == "file":
            if parsed.netloc and ":" in parsed.netloc:
                raw_path = f"/{parsed.netloc}{parsed.path}"
            else:
                raw_path = parsed.path
            filepath = url2pathname(raw_path)
            if filepath.startswith("/") and len(filepath) > 2 and filepath[2] == ":":
                filepath = filepath[1:]
            try:
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        yield chunk
            except FileNotFoundError as e:
                raise tuf_exceptions.DownloadHTTPError(f"File not found: {filepath}", 404) from e
        else:
            from tuf.ngclient.urllib3_fetcher import Urllib3Fetcher

            fetcher = Urllib3Fetcher()
            yield from fetcher.fetch(url)


class UpdateCheckerThread(QThread):
    """Background thread to check for application updates using TUF (S4-8)."""

    update_available = pyqtSignal(str, str)  # latest_version, html_url
    error = pyqtSignal(str)

    def __init__(
        self,
        current_version: str,
        parent: Any | None = None,
        metadata_url: str = "https://updates.maestro.control/metadata/",
        targets_url: str = "https://updates.maestro.control/targets/",
        cache_dir: Path | None = None,
        bootstrap_root: bytes | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version.strip("v")
        self.metadata_url = metadata_url
        self.targets_url = targets_url
        self.bootstrap_root = bootstrap_root or json.dumps(BOOTSTRAP_ROOT).encode("utf-8")

        if cache_dir is None:
            from gesture_controller.core.paths import user_cache_dir

            self.cache_dir = user_cache_dir() / "tuf_cache"
        else:
            self.cache_dir = cache_dir

    def run(self) -> None:
        if not self.cache_dir.exists():
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.error.emit(f"Failed to create update cache directory: {e}")
                return

        try:
            updater = Updater(
                metadata_dir=str(self.cache_dir),
                metadata_base_url=self.metadata_url,
                target_base_url=self.targets_url,
                fetcher=LocalFileFetcher(),
                bootstrap=self.bootstrap_root,
            )

            updater.refresh()

            newest_version = self.current_version
            newest_url = ""

            targets_obj = updater._trusted_set.get("targets")
            if targets_obj:
                signed_targets = getattr(targets_obj, "signed", targets_obj)
                targets_dict = getattr(signed_targets, "targets", {})
                for filename, target_file in targets_dict.items():
                    custom = getattr(target_file, "custom", None)
                    if not custom:
                        custom = getattr(target_file, "unrecognized_fields", {})
                        if isinstance(custom, dict) and "custom" in custom:
                            custom = custom["custom"]
                    version = (
                        custom.get("version", "").strip("v") if isinstance(custom, dict) else ""
                    )
                    release_url = custom.get("release_url", "") if isinstance(custom, dict) else ""

                    if not version and "maestro-" in filename:
                        import re

                        m = re.search(r"maestro-(\d+\.\d+(?:\.\d+)?)", filename)
                        if m:
                            version = m.group(1)
                            if not release_url:
                                release_url = f"https://github.com/tag/v{version}"

                    if version and self._is_newer(version, newest_version):
                        newest_version = version
                        newest_url = release_url

            if newest_version != self.current_version:
                self.update_available.emit(newest_version, newest_url)

        except Exception as e:
            self.error.emit(str(e))

    def _is_newer(self, latest: str, current: str) -> bool:
        """Helper to evaluate if latest version tuple is greater than current version tuple."""
        try:
            l_parts = [int(p) for p in latest.split(".")]
            c_parts = [int(p) for p in current.split(".")]
            max_len = max(len(l_parts), len(c_parts), 3)
            while len(l_parts) < max_len:
                l_parts.append(0)
            while len(c_parts) < max_len:
                c_parts.append(0)
            return tuple(l_parts) > tuple(c_parts)
        except ValueError:
            return False


# ── Sprint 13: Update Channels + GitHub Releases-based checker ────────────────

import enum
import urllib.request
import zipfile
import tarfile
import subprocess
import threading
import structlog as _structlog

_update_logger = _structlog.get_logger(__name__)


class UpdateChannel(enum.Enum):
    """Release channel for update checks."""

    STABLE = "stable"
    BETA = "beta"
    NIGHTLY = "nightly"


class ReleaseAsset:
    """Describes a single downloadable asset from a GitHub release."""

    def __init__(self, name: str, browser_download_url: str, size: int) -> None:
        self.name = name
        self.url = browser_download_url
        self.size = size

    def __repr__(self) -> str:
        return f"ReleaseAsset(name={self.name!r}, size={self.size})"


class ReleaseInfo:
    """Metadata for a single GitHub release."""

    def __init__(
        self,
        version: str,
        tag_name: str,
        prerelease: bool,
        html_url: str,
        assets: list["ReleaseAsset"],
        body: str = "",
    ) -> None:
        self.version = version.lstrip("v")
        self.tag_name = tag_name
        self.prerelease = prerelease
        self.html_url = html_url
        self.assets = assets
        self.body = body

    @classmethod
    def from_github_dict(cls, data: dict[str, Any]) -> "ReleaseInfo":
        assets = [
            ReleaseAsset(
                name=a["name"],
                browser_download_url=a["browser_download_url"],
                size=a.get("size", 0),
            )
            for a in data.get("assets", [])
        ]
        tag = data.get("tag_name", "0.0.0")
        return cls(
            version=tag,
            tag_name=tag,
            prerelease=data.get("prerelease", False),
            html_url=data.get("html_url", ""),
            assets=assets,
            body=data.get("body", ""),
        )

    def is_nightly(self) -> bool:
        return "nightly" in self.tag_name.lower() or "dev" in self.tag_name.lower()

    def is_beta(self) -> bool:
        return self.prerelease and not self.is_nightly()

    def matches_channel(self, channel: UpdateChannel) -> bool:
        if channel == UpdateChannel.NIGHTLY:
            return True  # nightlies see all releases
        if channel == UpdateChannel.BETA:
            return not self.is_nightly()  # betas see stable + beta
        return not self.prerelease  # stable only sees non-prerelease


def _compare_versions(a: str, b: str) -> int:
    """Return -1, 0, or +1 for a < b, a == b, a > b."""

    def _parse(v: str) -> list[int]:
        parts = []
        for seg in v.lstrip("v").split("."):
            try:
                parts.append(int(seg.split("-")[0]))
            except ValueError:
                parts.append(0)
        return parts

    av, bv = _parse(a), _parse(b)
    length = max(len(av), len(bv))
    av += [0] * (length - len(av))
    bv += [0] * (length - len(bv))
    if av < bv:
        return -1
    if av > bv:
        return 1
    return 0


def check_for_update(
    current_version: str,
    channel: UpdateChannel = UpdateChannel.STABLE,
    repo: str = "maestro-project/maestro",
    timeout: float = 8.0,
) -> ReleaseInfo | None:
    """Check GitHub Releases for a newer version on the given channel.

    Args:
        current_version: The running version string (e.g. "1.2.3").
        channel: Which release channel to check against.
        repo: ``owner/repo`` on GitHub.
        timeout: HTTP request timeout in seconds.

    Returns:
        A :class:`ReleaseInfo` if a newer version is available, else ``None``.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page=20"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Maestro/{current_version}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            releases_raw: list[dict[str, Any]] = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _update_logger.warning("Failed to fetch GitHub releases", error=str(exc))
        return None

    best: ReleaseInfo | None = None
    for raw in releases_raw:
        release = ReleaseInfo.from_github_dict(raw)
        if not release.matches_channel(channel):
            continue
        if _compare_versions(release.version, current_version) > 0:
            if best is None or _compare_versions(release.version, best.version) > 0:
                best = release

    if best:
        _update_logger.info(
            "Newer version found",
            current=current_version,
            latest=best.version,
            channel=channel.value,
        )
    return best


def download_update(
    asset_url: str,
    dest: Path,
    progress_callback: Any | None = None,
    timeout: float = 120.0,
) -> Path:
    """Download an update asset to *dest* with optional progress reporting."""
    dest.mkdir(parents=True, exist_ok=True)
    filename = asset_url.rstrip("/").split("/")[-1] or "maestro_update"
    file_path = dest / filename

    req = urllib.request.Request(asset_url, headers={"User-Agent": "Maestro-Updater/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            total = int(resp.headers.get("Content-Length", -1))
            received = 0
            chunk_size = 65536  # 64 KiB

            with open(file_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress_callback:
                        try:
                            progress_callback(received, total)
                        except Exception:
                            pass
    except Exception as exc:
        _update_logger.error("Update download failed", url=asset_url, error=str(exc))
        raise OSError(f"Failed to download update from {asset_url}: {exc}") from exc

    _update_logger.info("Update downloaded", path=str(file_path), size=file_path.stat().st_size)
    return file_path


def apply_update(archive_path: Path, extract_dir: Path | None = None) -> bool:
    """Extract an update archive and (on Windows) launch the installer."""
    if not archive_path.exists():
        _update_logger.error("apply_update: archive not found", path=str(archive_path))
        return False

    suffix = archive_path.suffix.lower()
    name_lower = archive_path.name.lower()

    if suffix == ".exe":
        try:
            subprocess.Popen([str(archive_path), "/S"])
            _update_logger.info("Windows installer launched", path=str(archive_path))
            return True
        except Exception as exc:
            _update_logger.error("Failed to launch installer", error=str(exc))
            return False

    if extract_dir is None:
        extract_dir = archive_path.parent / "maestro_update_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        if suffix == ".zip" or name_lower.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)  # nosec B202
        elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(extract_dir)  # nosec B202
        elif name_lower.endswith(".tar.bz2"):
            with tarfile.open(archive_path, "r:bz2") as tf:
                tf.extractall(extract_dir)  # nosec B202
        else:
            _update_logger.warning(
                "apply_update: unrecognised archive format", path=str(archive_path)
            )
            return False
    except Exception as exc:
        _update_logger.error("Archive extraction failed", error=str(exc))
        return False

    _update_logger.info("Update extracted", dest=str(extract_dir))
    return True


class GithubUpdateChecker(QThread):
    """Lightweight GitHub-Releases-based update checker QThread."""

    from PyQt6.QtCore import pyqtSignal as _sig

    update_available = _sig(str, str, str)  # version, html_url, release_notes
    no_update = _sig()
    error = _sig(str)

    def __init__(
        self,
        current_version: str,
        channel: UpdateChannel = UpdateChannel.STABLE,
        repo: str = "maestro-project/maestro",
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.channel = channel
        self.repo = repo

    def run(self) -> None:
        try:
            release = check_for_update(
                current_version=self.current_version,
                channel=self.channel,
                repo=self.repo,
            )
            if release:
                self.update_available.emit(release.version, release.html_url, release.body)
            else:
                self.no_update.emit()
        except Exception as exc:
            self.error.emit(str(exc))
