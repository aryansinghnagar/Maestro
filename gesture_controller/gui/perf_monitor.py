"""Performance monitor overlay widget.

Renders a compact semi-transparent HUD in the bottom-left corner of the screen
showing live FPS, per-stage latency, and dropped-frame count.
Updated every second from a QTimer.
"""

from __future__ import annotations

import time
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QApplication


class PerfMonitorOverlay(QWidget):
    """Floating performance HUD widget (click-through, always-on-top)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName("Performance monitor overlay")

        # ── Data ────────────────────────────────────────────────────────────
        self._fps: float = 0.0
        self._frame_times: list[float] = []
        self._dropped_frames: int = 0
        self._stage_stats: dict[str, dict[str, float]] = {}

        self._last_fps_ts = time.monotonic()
        self._frame_count_since_ts = 0

        # ── Refresh timer ────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)  # Update display every second

        self._resize_to_screen()

    def _resize_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.setGeometry(geom)

    # ── Public API ───────────────────────────────────────────────────────────

    def record_frame(self, processing_time_s: float, dropped: bool = False) -> None:
        """Called by the engine each frame to track FPS and latency."""
        self._frame_times.append(processing_time_s)
        if len(self._frame_times) > 300:
            self._frame_times.pop(0)
        self._frame_count_since_ts += 1
        if dropped:
            self._dropped_frames += 1

    def update_stage_stats(self, stats: dict[str, dict[str, float]]) -> None:
        """Feed FrameTimeBudget.snapshot() output."""
        self._stage_stats = stats

    # ── Internal ─────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_fps_ts
        if elapsed > 0:
            self._fps = self._frame_count_since_ts / elapsed
        self._frame_count_since_ts = 0
        self._last_fps_ts = now
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Build display lines
        lines: list[str] = [
            f"FPS: {self._fps:.1f}",
            f"Dropped: {self._dropped_frames}",
        ]
        if self._frame_times:
            mean_ms = sum(self._frame_times) / len(self._frame_times) * 1000
            max_ms = max(self._frame_times) * 1000
            lines.append(f"Latency  mean={mean_ms:.1f}ms  max={max_ms:.1f}ms")

        for stage, stats in sorted(self._stage_stats.items()):
            lines.append(
                f"  {stage}: {stats.get('mean_ms', 0):.1f}ms "
                f"(p95={stats.get('p95_ms', 0):.1f}ms)"
            )

        # Draw background pill
        line_h = 16
        padding = 8
        w = 300
        h = padding * 2 + line_h * len(lines)
        x, y = 12, self.height() - h - 12

        bg = QColor(10, 10, 10, 180)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x, y, w, h), 6, 6)

        # Draw text
        fps_color = (
            QColor("#00ff88")
            if self._fps >= 25
            else QColor("#ffaa00") if self._fps >= 15 else QColor("#ff4444")
        )
        font = QFont("Consolas", 9)
        painter.setFont(font)

        for i, line in enumerate(lines):
            ty = y + padding + i * line_h + line_h - 2
            color = fps_color if i == 0 else QColor("#dddddd")
            painter.setPen(QPen(color))
            painter.drawText(int(x + padding), int(ty), line)
