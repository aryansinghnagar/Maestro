import pytest
import time
import threading
from typing import Callable
from gesture_controller.core.event_bus import EventBus


def wait_for(condition: Callable[[], bool], timeout: float = 2.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return
        time.sleep(0.01)


def test_sync_publish() -> None:
    bus = EventBus()
    events = []
    current_thread_id = threading.get_ident()
    handler_thread_id = None

    def handler(event: str) -> None:
        nonlocal handler_thread_id
        handler_thread_id = threading.get_ident()
        events.append(event)

    bus.subscribe("gesture_triggered", handler)
    bus.publish("gesture_triggered", "click")

    wait_for(lambda: len(events) == 1)

    assert events == ["click"]
    assert handler_thread_id is not None
    assert handler_thread_id != current_thread_id


def test_async_publish() -> None:
    bus = EventBus()
    events = []
    current_thread_id = threading.get_ident()
    handler_thread_id = None

    def handler(event: str) -> None:
        nonlocal handler_thread_id
        handler_thread_id = threading.get_ident()
        events.append(event)

    bus.subscribe("test_event", handler)
    bus.publish("test_event", "hello")

    wait_for(lambda: len(events) == 1)

    assert events == ["hello"]
    assert handler_thread_id is not None
    assert handler_thread_id != current_thread_id


def test_unsubscribe() -> None:
    bus = EventBus()
    events = []

    def handler(event: str) -> None:
        events.append(event)

    bus.subscribe("gesture_triggered", handler)
    bus.publish("gesture_triggered", "first")

    wait_for(lambda: len(events) == 1)

    bus.unsubscribe("gesture_triggered", handler)
    bus.publish("gesture_triggered", "second")
    time.sleep(0.1)

    assert events == ["first"]


def test_multiple_subscribers() -> None:
    bus = EventBus()
    results = {"h1": 0, "h2": 0}

    def h1(event: int) -> None:
        results["h1"] += event

    def h2(event: int) -> None:
        results["h2"] += event * 2

    bus.subscribe("gesture_triggered", h1)
    bus.subscribe("gesture_triggered", h2)
    bus.publish("gesture_triggered", 5)

    wait_for(lambda: results["h1"] == 5 and results["h2"] == 10)

    assert results["h1"] == 5
    assert results["h2"] == 10


def test_handler_exception_does_not_crash_publisher() -> None:
    bus = EventBus()
    events = []

    def bad_handler(event: str) -> None:
        raise RuntimeError("Something went wrong")

    def good_handler(event: str) -> None:
        events.append(event)

    bus.subscribe("gesture_triggered", bad_handler)
    bus.subscribe("gesture_triggered", good_handler)

    bus.publish("gesture_triggered", "safe")

    wait_for(lambda: len(events) == 1)

    assert events == ["safe"]


def test_handler_consecutive_failures_unsubscribes() -> None:
    bus = EventBus()
    events = []
    call_count = 0

    def failing_handler(event: str) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Failing on purpose")

    def good_handler(event: str) -> None:
        events.append(event)

    bus.subscribe("gesture_triggered", failing_handler)
    bus.subscribe("gesture_triggered", good_handler)

    # Trigger 3 failures
    for i in range(3):
        bus.publish("gesture_triggered", f"event_{i}")
        wait_for(lambda idx=i: len(events) == idx + 1)

    assert call_count == 3
    assert events == ["event_0", "event_1", "event_2"]

    # Publisher should have unsubscribed the bad handler
    # So publishing again should NOT invoke failing_handler
    bus.publish("gesture_triggered", "event_3")

    wait_for(lambda: len(events) == 4)

    assert call_count == 3  # remains 3
    assert events == ["event_0", "event_1", "event_2", "event_3"]
