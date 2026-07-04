import pytest
import time
import threading
from gesture_controller.core.event_bus import EventBus

def test_sync_publish() -> None:
    # sync event "gesture_triggered" runs in same thread
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
    
    assert events == ["click"]
    assert handler_thread_id == current_thread_id

def test_async_publish() -> None:
    # "test_event" is async and runs in the worker thread
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
    
    # Wait for the async worker queue to process the event
    time.sleep(0.05)
    
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
    bus.unsubscribe("gesture_triggered", handler)
    bus.publish("gesture_triggered", "second")
    
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
    
    # Should not raise exception
    bus.publish("gesture_triggered", "safe")
    
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
    
    # Trigger 5 failures
    for i in range(5):
        bus.publish("gesture_triggered", f"event_{i}")
        
    assert call_count == 5
    assert events == ["event_0", "event_1", "event_2", "event_3", "event_4"]
    
    # Publisher should have unsubscribed the bad handler
    # So publishing again should NOT invoke failing_handler
    bus.publish("gesture_triggered", "event_6")
    
    assert call_count == 5 # remains 5
    assert events == ["event_0", "event_1", "event_2", "event_3", "event_4", "event_6"]
