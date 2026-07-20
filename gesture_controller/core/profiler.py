"""Frame-time budget profiler for Maestro.

Two responsibilities:
1. Lightweight per-stage wall-clock timing that feeds MetricsCollector.
2. Optional cProfile session that can be started/stopped programmatically
   (wired to the ``--profile`` CLI flag).
"""

from __future__ import annotations

import cProfile
import io
import pstats
import time
import threading
import contextlib
from collections import deque
from pathlib import Path
from typing import Generator, Optional

import structlog

logger = structlog.get_logger(__name__)

# ── Singleton profile session ──────────────────────────────────────────────────
_profiler: Optional[cProfile.Profile] = None
_profiler_lock = threading.Lock()


def start_profiling() -> None:
    """Start the global cProfile session (idempotent)."""
    global _profiler
    with _profiler_lock:
        if _profiler is None:
            _profiler = cProfile.Profile()
            _profiler.enable()
            logger.info("cProfile session started")


def stop_profiling(output_path: Optional[Path] = None) -> str:
    """Stop the global cProfile session and return a top-30 human-readable report.

    Args:
        output_path: If provided, also write the raw ``pstats`` dump to this path.

    Returns:
        Formatted stats string (top 30 cumulative entries).
    """
    global _profiler
    with _profiler_lock:
        if _profiler is None:
            return "(no profiling session active)"
        _profiler.disable()
        stream = io.StringIO()
        ps = pstats.Stats(_profiler, stream=stream)
        ps.sort_stats("cumulative")
        ps.print_stats(30)
        report = stream.getvalue()
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            _profiler.dump_stats(str(output_path))
            logger.info("cProfile stats dumped", path=str(output_path))
        _profiler = None
        return report


def is_profiling() -> bool:
    """Return True if a cProfile session is currently active."""
    return _profiler is not None


# ── FrameTimeBudget: per-stage timing ─────────────────────────────────────────


class FrameTimeBudget:
    """Track wall-clock timing for named pipeline stages.

    Thread-safe; designed for 30 Hz call rates.
    """

    _MAX_HISTORY = 300  # ~10 seconds of history at 30 FPS

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # stage_name → deque of float (seconds)
        self._histories: dict[str, deque[float]] = {}
        self._stage_start: dict[str, float] = {}

    @contextlib.contextmanager
    def measure(self, stage: str) -> Generator[None, None, None]:
        """Context manager that records wall-clock time for a named stage."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self._record(stage, elapsed)

    def begin(self, stage: str) -> None:
        """Manual timing start (alternative to the context manager)."""
        self._stage_start[stage] = time.perf_counter()

    def end(self, stage: str) -> float:
        """Manual timing end. Returns elapsed seconds."""
        t0 = self._stage_start.pop(stage, None)
        if t0 is None:
            return 0.0
        elapsed = time.perf_counter() - t0
        self._record(stage, elapsed)
        return elapsed

    def _record(self, stage: str, elapsed: float) -> None:
        with self._lock:
            if stage not in self._histories:
                self._histories[stage] = deque(maxlen=self._MAX_HISTORY)
            self._histories[stage].append(elapsed)

    def snapshot(self) -> dict[str, dict[str, float]]:
        """Return current stats for all stages (mean, min, max, p95 in ms)."""
        result: dict[str, dict[str, float]] = {}
        with self._lock:
            for stage, history in self._histories.items():
                if not history:
                    continue
                vals = sorted(history)
                n = len(vals)
                result[stage] = {
                    "mean_ms": sum(vals) / n * 1000,
                    "min_ms": vals[0] * 1000,
                    "max_ms": vals[-1] * 1000,
                    "p95_ms": vals[int(n * 0.95)] * 1000,
                    "count": float(n),
                }
        return result

    def reset(self) -> None:
        """Clear all timing history."""
        with self._lock:
            self._histories.clear()
            self._stage_start.clear()


# ── Module-level shared instance ───────────────────────────────────────────────
frame_budget = FrameTimeBudget()
