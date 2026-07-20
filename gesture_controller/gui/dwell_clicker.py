"""Dwell click — automatic click when cursor dwells in one spot for N ms."""
from __future__ import annotations

import time
import threading
from typing import Callable
from PyQt6.QtGui import QCursor


class DwellClicker:
    """Triggers a left mouse click when the cursor remains within a small radius."""

    def __init__(self, config_manager, on_click: Callable[[int, int], None]) -> None:
        self._config = config_manager
        self._on_click = on_click
        self._radius = 20  # pixels
        self._cursor_pos: tuple[int, int] | None = None
        self._dwell_start: float | None = None
        self._clicked_for_current_dwell = False
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the dwell checking thread loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="dwell_clicker_loop")
        self._thread.start()

    def stop(self) -> None:
        """Stop the dwell checking thread loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self) -> None:
        """Check cursor position periodically."""
        while self._running:
            try:
                enabled = self._config.get("a11y.dwell_click_enabled", False)
                if not enabled:
                    time.sleep(0.1)
                    continue

                pos = QCursor.pos()
                self.update_cursor(pos.x(), pos.y())
            except Exception:
                pass
            time.sleep(0.05)  # 20 Hz polling rate

    def update_cursor(self, x: int, y: int) -> None:
        """Update cursor tracking and evaluate dwell trigger."""
        duration = self._config.get("a11y.dwell_duration_ms", 800) / 1000.0

        if (
            self._cursor_pos
            and abs(x - self._cursor_pos[0]) < self._radius
            and abs(y - self._cursor_pos[1]) < self._radius
        ):
            # Cursor is dwelling in the same spot
            if not self._clicked_for_current_dwell:
                if self._dwell_start and (time.monotonic() - self._dwell_start) >= duration:
                    self._on_click(x, y)
                    self._clicked_for_current_dwell = True
        else:
            # Cursor moved beyond radius
            self._cursor_pos = (x, y)
            self._dwell_start = time.monotonic()
            self._clicked_for_current_dwell = False
