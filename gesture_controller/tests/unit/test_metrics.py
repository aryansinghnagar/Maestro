import pytest
from gesture_controller.core.metrics import MetricsCollector


def test_metrics_collector() -> None:
    collector = MetricsCollector()

    # Test counters
    collector.increment("counter_a")
    collector.increment("counter_a", 2)
    collector.increment("counter_b")

    # Test gauges
    collector.set_gauge("gauge_a", 42.5)

    # Test histograms
    collector.observe("latency_a", 0.1)
    collector.observe("latency_a", 0.2)
    collector.observe("latency_a", 0.3)

    summary = collector.get_summary()

    # Assert counters
    assert summary["counters"]["counter_a"] == 3
    assert summary["counters"]["counter_b"] == 1

    # Assert gauges
    assert summary["gauges"]["gauge_a"] == 42.5

    # Assert histograms
    hist = summary["histograms"]["latency_a"]
    assert hist["count"] == 3
    assert hist["min"] == 0.1
    assert hist["max"] == 0.3
    assert hist["mean"] == pytest.approx(0.2)
    assert hist["p50"] == 0.2
    assert hist["p90"] == 0.3
    assert hist["p99"] == 0.3

    # Emit
    collector.increment("counter_c")
    collector.emit()
