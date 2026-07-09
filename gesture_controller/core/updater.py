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

# Patch os.symlink for Windows compatibility to prevent WinError 1314 privilege crashes
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
            os.remove(dst)
        shutil.copy(abs_src, dst)
os.symlink = _secure_symlink  # type: ignore[assignment]

# Default bootstrap root.json content for client trust initialization
BOOTSTRAP_ROOT = {
  "signatures": [
    {
      "keyid": "92a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd",
      "sig": "acaee08fd78ce47bcd15bd53bf59a328fd337de4dff6daaf626c33c62d7fcfe3ceb52dbf4101ae0845c7fec4dfe57e138ecf818e89a2554bed828fe31c55ef0f"
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
        }
      },
      "ce7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4": {
        "keytype": "ed25519",
        "scheme": "ed25519",
        "keyval": {
          "public": "50855f76d5067af7fcabe4f8925961bb2dd0153aaa8147fbe3c309c28cddd9f2"
        }
      },
      "a8c3a6c4e4eeae6bcd88e66c9954992e28e222902894c9ac02efce6417028b2d": {
        "keytype": "ed25519",
        "scheme": "ed25519",
        "keyval": {
          "public": "7623294c33e4672d47164226f54f16a5158b0a98f89a9cab8c2499a5a960d8ef"
        }
      },
      "c4070c306bf96fa078fb556ad2c158386f4daf04f5fc6d60db9e6419c83c92cd": {
        "keytype": "ed25519",
        "scheme": "ed25519",
        "keyval": {
          "public": "502ffb92435709666138bac16a30e607e46784318f59872ad9670fa3ff77a78f"
        }
      }
    },
    "roles": {
      "root": {
        "keyids": [
          "92a799aa87406d0d7fe43271474672e5299fc084b38a8d016b43503845f895dd"
        ],
        "threshold": 1
      },
      "targets": {
        "keyids": [
          "ce7d063e83bdf0c21347054c9e864117ea3b531bdddd201970e931c2d4b319a4"
        ],
        "threshold": 1
      },
      "snapshot": {
        "keyids": [
          "a8c3a6c4e4eeae6bcd88e66c9954992e28e222902894c9ac02efce6417028b2d"
        ],
        "threshold": 1
      },
      "timestamp": {
        "keyids": [
          "c4070c306bf96fa078fb556ad2c158386f4daf04f5fc6d60db9e6419c83c92cd"
        ],
        "threshold": 1
      }
    }
  }
}


class LocalFileFetcher(FetcherInterface):
    """Fetcher supporting file:// scheme for local directory testing."""

    def _fetch(self, url: str) -> Any:
        parsed = urlparse(url)
        if parsed.scheme == "file":
            filepath = url2pathname(parsed.path)
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
            self.cache_dir = Path(os.path.expanduser("~")) / ".config" / "gesture_controller" / "tuf_cache"
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
            if targets_obj and hasattr(targets_obj, "targets"):
                for filename, target_file in targets_obj.targets.items():
                    custom = target_file.unrecognized_fields.get("custom", {})
                    version = custom.get("version", "").strip("v")
                    release_url = custom.get("release_url", "")
                    
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
