import json
import ssl
import urllib.request
from PyQt6.QtCore import QThread, pyqtSignal

class UpdateCheckerThread(QThread):
    """Background thread to check for application updates on GitHub (S4-8)."""
    update_available = pyqtSignal(str, str)  # latest_version, html_url
    error = pyqtSignal(str)

    def __init__(self, current_version: str, parent=None) -> None:
        super().__init__(parent)
        self.current_version = current_version.strip("v")

    def run(self) -> None:
        url = "https://api.github.com/repos/aryansinghnagar/Maestro/releases/latest"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Maestro-Update-Checker"}
        )
        try:
            # Set up non-blocking SSL context to avoid certificate validation issues on restricted networks
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                latest_tag = data.get("tag_name", "").strip("v")
                html_url = data.get("html_url", "")

                if latest_tag and self._is_newer(latest_tag, self.current_version):
                    self.update_available.emit(latest_tag, html_url)
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
            # Fallback to standard lexicographical string comparison
            return latest > current
