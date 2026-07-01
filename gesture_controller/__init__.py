"""
Gesture Controller package.
"""

__version__ = "0.1.0"

# Apply Windows ctypes patch for MediaPipe on Python 3.14+
import os
if os.name == "nt":
    import ctypes
    _orig_cdll_init = ctypes.CDLL.__init__
    def _patched_cdll_init(self, name: str | None, *args: Any, **kwargs: Any) -> None:
        _orig_cdll_init(self, name, *args, **kwargs)
        if name and "libmediapipe" in name:
            if not hasattr(self, "free"):
                try:
                    self.free = ctypes.CDLL("msvcrt").free
                except Exception:
                    pass
    # Avoid type annotation issues by bypassing strict checks for monkeypatching
    from typing import Any
    ctypes.CDLL.__init__ = _patched_cdll_init  # type: ignore
