"""
Gesture Controller package.
"""

from __future__ import annotations
from typing import Any

__version__ = "1.1.1"

# Apply Windows ctypes patch for MediaPipe on Python 3.14+.
# Gate behind env var so tests and non-MediaPipe consumers can opt out.
import os

if os.name == "nt":
    import ctypes

    if os.environ.get("MAESTRO_PATCH_CDLL", "1") == "1":
        _orig_cdll_init = ctypes.CDLL.__init__
        _msvcrt = ctypes.CDLL("msvcrt")
        _msvcrt_free = _msvcrt.free

        def _patched_cdll_init(self: Any, name: str | None, *args: Any, **kwargs: Any) -> None:
            _orig_cdll_init(self, name, *args, **kwargs)
            if name and "libmediapipe" in name and not hasattr(self, "free"):
                self.free = _msvcrt_free  # Reuse a single msvcrt handle

        ctypes.CDLL.__init__ = _patched_cdll_init  # type: ignore[method-assign]
