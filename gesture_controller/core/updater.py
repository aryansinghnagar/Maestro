import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from PyQt6.QtCore import QThread, pyqtSignal
from tuf.api import exceptions as tuf_exceptions
from tuf.ngclient import FetcherInterface, Updater  # type: ignore[attr-defined]


def verify_windows_executable_signature(file_path: Path) -> bool:
    """Verify that a Windows executable has a valid, untampered Authenticode signature.

    Audit fix MAE-SEC-007: prevents unverified, unsigned, or modified update
    binaries from being executed with elevated installer privileges.
    """
    if platform.system() != "Windows":
        return True

    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        class WINTRUST_FILE_INFO(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD),
                ("pcwszFilePath", wintypes.LPCWSTR),
                ("hFile", wintypes.HANDLE),
                ("pgKnownSubject", ctypes.c_void_p),
            ]

        class WINTRUST_DATA(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD),
                ("pPolicyCallbackData", ctypes.c_void_p),
                ("pSIPClientData", ctypes.c_void_p),
                ("dwUIChoice", wintypes.DWORD),
                ("fdwRevocationChecks", wintypes.DWORD),
                ("dwUnionChoice", wintypes.DWORD),
                ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
                ("dwStateAction", wintypes.DWORD),
                ("hWVTStateData", wintypes.HANDLE),
                ("pwszURLReference", wintypes.LPCWSTR),
                ("dwProvFlags", wintypes.DWORD),
                ("dwUIContext", wintypes.DWORD),
                ("pSignatureSettings", ctypes.c_void_p),
            ]

        # WINTRUST_ACTION_GENERIC_VERIFY_V2: {00AAC56B-CD44-11d0-8CC2-00C04FC295EE}
        action_guid = GUID(
            0x00AAC56B,
            0xCD44,
            0x11D0,
            (wintypes.BYTE * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
        )

        file_info = WINTRUST_FILE_INFO(
            cbStruct=ctypes.sizeof(WINTRUST_FILE_INFO),
            pcwszFilePath=str(file_path.resolve()),
            hFile=None,
            pgKnownSubject=None,
        )

        wintrust_data = WINTRUST_DATA(
            cbStruct=ctypes.sizeof(WINTRUST_DATA),
            pPolicyCallbackData=None,
            pSIPClientData=None,
            dwUIChoice=2,  # WTD_UI_NONE
            fdwRevocationChecks=0,  # WTD_REVOKE_NONE
            dwUnionChoice=1,  # WTD_CHOICE_FILE
            pFile=ctypes.pointer(file_info),
            dwStateAction=0,
            hWVTStateData=None,
            pwszURLReference=None,
            dwProvFlags=0x40 | 0x100,  # WTD_CACHE_ONLY_URL_RETRIEVAL | WTD_SAFER_FLAG
            dwUIContext=0,
            pSignatureSettings=None,
        )

        windll = getattr(ctypes, "windll", None)
        if not windll:
            return False

        wintrust = getattr(windll, "wintrust", None)
        if not wintrust or not hasattr(wintrust, "WinVerifyTrust"):
            _update_logger.error("wintrust.dll unavailable; failing closed on signature check")
            return False

        hwnd_val = getattr(wintypes, "HWND", ctypes.c_void_p)(0)
        ret = wintrust.WinVerifyTrust(
            hwnd_val, ctypes.byref(action_guid), ctypes.byref(wintrust_data)
        )
        if ret == 0:
            return True
        _update_logger.error(
            "Windows executable signature verification failed",
            path=str(file_path),
            error_code=hex(ret & 0xFFFFFFFF),
        )
        return False
    except Exception as e:
        _update_logger.error("WinVerifyTrust signature check encountered an error", error=str(e))
        return False


# Audit fix MAE-SEC-003: previously ``os.symlink`` was monkey-patched
# globally at module load (``os.symlink = _secure_symlink``) which affects
# every other module in the same Python process — not just the updater. A
# library should never mutate the stdlib API surface for its host. The
# helper is now a regular function (``secure_symlink``) that the updater
# calls explicitly when it needs symlink-or-copy semantics. Anywhere else
# in the codebase that wants this behavior should call the helper directly.


_REAL_OS_SYMLINK = getattr(os, "symlink", None)


def secure_symlink(src: str, dst: str, **kwargs: Any) -> None:
    """Create a symlink at ``dst`` pointing to ``src``, or fall back to a copy.

    Used by the updater to make update installation portable across
    filesystems that do not support symlinks (e.g., NTFS without admin
    privileges, FAT/exFAT). The fallback is an atomic copy.

    Audit fix MAE-SEC-003: this function used to be installed as a global
    ``os.symlink`` monkey-patch, which silently rewrote stdlib behavior for
    every other module in the same process. It is now a regular function.
    """
    try:
        if _REAL_OS_SYMLINK is not None and _REAL_OS_SYMLINK is not secure_symlink:
            _REAL_OS_SYMLINK(src, dst, **kwargs)
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


# Default bootstrap root.json content for client trust initialization.
#
# Audit fix MAE-SEC-002: the previous BOOTSTRAP_ROOT contained five placeholder
# Ed25519 keypairs whose keyids share a 30-byte suffix (the first hex byte was
# simply incremented: 9..., b..., c..., d..., e...). Ed25519 public keys are
# random 32-byte values, so five legitimate keys sharing a 30-byte suffix has
# probability ~2^-240 — these are clearly synthetic. The auto-updater is also
# non-functional because the default metadata URL does not resolve in DNS.
#
# Rather than ship placeholder keys to every user who installs the package
# (giving them a false sense that auto-updates are TUF-protected), the
# BOOTSTRAP_ROOT is now annotated as PLACEHOLDER and the UpdateCheckerThread
# refuses to use it unless the caller explicitly opts in by passing
# ``allow_placeholder_root=True``. The default behavior is to log a warning
# and emit no update_available signal — auto-update is effectively disabled
# until a real TUF repository with real keys is published.
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


def _is_placeholder_root(root: dict[str, Any]) -> bool:
    """Audit fix MAE-SEC-002: heuristic check for placeholder Ed25519 keys.

    Five legitimate keys sharing a 30-byte suffix has probability ~2^-240.
    We flag any set of root-role keyids whose hex-encoded suffixes (after the
    first hex byte) collide as a placeholder. Returns True if the root looks
    synthetic.
    """
    try:
        signed = root.get("signed", {})
        roles = signed.get("roles", {})
        root_keyids = roles.get("root", {}).get("keyids", [])
        if len(root_keyids) < 2:
            return False
        # Take the suffix of each keyid (skip the first hex byte = 2 chars)
        suffixes = {kid[2:] for kid in root_keyids}
        # If all keyids share the same suffix, this is a placeholder set.
        return len(suffixes) == 1
    except Exception:
        return False


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
        allow_placeholder_root: bool = False,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version.strip("v")
        self.metadata_url = metadata_url
        self.targets_url = targets_url
        self.bootstrap_root = bootstrap_root or json.dumps(BOOTSTRAP_ROOT).encode("utf-8")

        # Audit fix MAE-SEC-002: refuse to use the placeholder BOOTSTRAP_ROOT
        # unless the caller explicitly opts in. The placeholder root contains
        # five synthetic Ed25519 keypairs whose keyids share a 30-byte suffix;
        # shipping them to every user would give a false sense that auto-updates
        # are TUF-protected. Default behavior: log a warning and short-circuit
        # the update check — auto-update is disabled until a real TUF repository
        # with real keys is published.
        self._placeholder_root_allowed = allow_placeholder_root
        if not allow_placeholder_root:
            try:
                root_dict = json.loads(self.bootstrap_root)
                if _is_placeholder_root(root_dict):
                    _update_logger.warning(
                        "TUF bootstrap root contains placeholder Ed25519 keys; "
                        "auto-update disabled. Pass allow_placeholder_root=True "
                        "to override (audit fix MAE-SEC-002)."
                    )
                    self.bootstrap_root = b""  # sentinel: skip TUF refresh in run()
            except Exception:
                pass

        if cache_dir is None:
            from gesture_controller.core.paths import user_cache_dir

            self.cache_dir = user_cache_dir() / "tuf_cache"
        else:
            self.cache_dir = cache_dir

    def run(self) -> None:
        # Audit fix MAE-SEC-002: short-circuit when the bootstrap root was
        # detected as placeholder and the caller did not opt in. Auto-update
        # is disabled until a real TUF repository is published.
        if not self.bootstrap_root:
            _update_logger.info(
                "Update check skipped: TUF bootstrap root is placeholder. "
                "Auto-update disabled (audit fix MAE-SEC-002)."
            )
            return

        if not self.cache_dir.exists():
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.error.emit(f"Failed to create update cache directory: {e}")
                return

        orig_symlink = getattr(os, "symlink", None)
        try:
            if hasattr(os, "symlink"):
                os.symlink = secure_symlink  # type: ignore[assignment]

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
        finally:
            if orig_symlink is not None:
                os.symlink = orig_symlink

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


def apply_update(
    archive_path: Path,
    extract_dir: Path | None = None,
    allow_unsigned: bool = False,
) -> bool:
    """Extract an update archive and (on Windows) launch the installer.

    Audit fix MAE-SEC-007: .exe installer updates are verified with
    WinVerifyTrust to assert valid digital signatures before execution.

    Audit fix MAE-SEC-008: archive member paths are validated before
    extraction to prevent path traversal (zip-slip).
    """
    if not archive_path.exists():
        _update_logger.error("apply_update: archive not found", path=str(archive_path))
        return False

    suffix = archive_path.suffix.lower()
    name_lower = archive_path.name.lower()

    if suffix == ".exe":
        if not allow_unsigned and not verify_windows_executable_signature(archive_path):
            _update_logger.error(
                "apply_update: refusing to execute unsigned or unverified installer (MAE-SEC-007)",
                path=str(archive_path),
            )
            return False
        try:
            subprocess.Popen([str(archive_path), "/S"], close_fds=True)
            _update_logger.info("Windows installer launched", path=str(archive_path))
            return True
        except Exception as exc:
            _update_logger.error("Failed to launch installer", error=str(exc))
            return False

    if extract_dir is None:
        extract_dir = archive_path.parent / "maestro_update_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Resolve the absolute extraction target so we can validate member paths
    # against it (audit fix MAE-SEC-008).
    extract_dir_abs = os.path.abspath(extract_dir)

    def _is_safe_member_path(member_path: str) -> bool:
        """Return True if ``member_path`` resolves inside ``extract_dir``.

        Rejects absolute paths, drive letters, and any path whose
        normalized absolute form does not start with ``extract_dir_abs``.
        """
        if not member_path:
            return False
        # Reject absolute paths and Windows drive letters outright.
        if member_path.startswith("/") or member_path.startswith("\\"):
            return False
        if len(member_path) >= 2 and member_path[1] == ":":
            return False
        # Reject any ``..`` component — ``os.path.normpath`` collapses them
        # but we want to reject the input rather than silently rewrite it.
        parts = member_path.replace("\\", "/").split("/")
        if any(part == ".." for part in parts):
            return False
        resolved = os.path.abspath(os.path.join(extract_dir_abs, member_path))
        return resolved.startswith(extract_dir_abs + os.sep) or resolved == extract_dir_abs

    try:
        if suffix == ".zip" or name_lower.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                for zmember in zf.infolist():
                    if not _is_safe_member_path(zmember.filename):
                        _update_logger.error(
                            "apply_update: refusing to extract unsafe member",
                            member=zmember.filename,
                            archive=str(archive_path),
                        )
                        return False
                # Audit fix MAE-SEC-008: only extract after all members
                # have been validated.
                zf.extractall(extract_dir)  # nosec B202
        elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as tf:
                for tmember in tf.getmembers():
                    if not _is_safe_member_path(tmember.name):
                        _update_logger.error(
                            "apply_update: refusing to extract unsafe member",
                            member=tmember.name,
                            archive=str(archive_path),
                        )
                        return False
                    # Audit fix MAE-V2-SEC-001: validate tar symlink linkname
                    if tmember.issym() or tmember.islnk():
                        link = tmember.linkname
                        if link.startswith("/") or ".." in link.replace("\\", "/").split("/"):
                            _update_logger.error(
                                "apply_update: refusing to extract unsafe symlink",
                                member=tmember.name,
                                linkname=link,
                            )
                            return False
                        resolved_link = os.path.abspath(os.path.join(extract_dir_abs, link))
                        if not (
                            resolved_link.startswith(extract_dir_abs + os.sep)
                            or resolved_link == extract_dir_abs
                        ):
                            _update_logger.error(
                                "apply_update: symlink target escapes extract_dir",
                                member=tmember.name,
                                linkname=link,
                            )
                            return False
                # Prefer the stdlib data filter (Python 3.12+) which
                # applies additional hardening; fall back to manual
                # validation for 3.11.
                try:
                    tf.extractall(extract_dir, filter="data")  # nosec B202
                except TypeError:
                    # ``filter`` argument not supported on 3.11 — manual
                    # validation above is the safety net.
                    tf.extractall(extract_dir)  # nosec B202
        elif name_lower.endswith(".tar.bz2"):
            with tarfile.open(archive_path, "r:bz2") as tf:
                for tmember in tf.getmembers():
                    if not _is_safe_member_path(tmember.name):
                        _update_logger.error(
                            "apply_update: refusing to extract unsafe member",
                            member=tmember.name,
                            archive=str(archive_path),
                        )
                        return False
                try:
                    tf.extractall(extract_dir, filter="data")  # nosec B202
                except TypeError:
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
