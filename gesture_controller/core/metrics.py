import time
import threading
from typing import Dict, List, Any
import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Thread-safe collector for structured metrics (counters, gauges, and histograms)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric."""
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        """Observe a value for a histogram metric."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)

    def get_summary(self) -> Dict[str, Any]:
        """Compute summaries for all metrics and reset histograms."""
        with self._lock:
            summary: Dict[str, Any] = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
            }
            # Calculate histogram statistics
            for name, values in self._histograms.items():
                if not values:
                    continue
                sorted_vals = sorted(values)
                count = len(sorted_vals)
                total = sum(sorted_vals)
                mean = total / count
                min_val = sorted_vals[0]
                max_val = sorted_vals[-1]
                # Simple percentiles (p50, p90, p99)
                p50 = sorted_vals[int(count * 0.5)]
                p90 = sorted_vals[int(count * 0.9)]
                p99 = sorted_vals[int(count * 0.99)]

                summary["histograms"][name] = {
                    "count": count,
                    "min": min_val,
                    "max": max_val,
                    "mean": mean,
                    "p50": p50,
                    "p90": p90,
                    "p99": p99,
                }
            # Reset histograms to prevent memory leaking
            self._histograms.clear()
            return summary

    def emit(self) -> None:
        """Emit structured metrics summary to log."""
        summary = self.get_summary()
        logger.info("structured_metrics", summary=summary)
