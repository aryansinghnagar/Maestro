import pytest
from gesture_controller.core.event_bus import EventBus

def test_subscribe_and_publish() -> None:
    bus = EventBus()
    events: list[str] = []
    
    def handler(event: str) -> None:
        events.append(event)
        
    bus.subscribe("test_event", handler)
    bus.publish("test_event", "hello")
    
    assert events == ["hello"]

def test_unsubscribe() -> None:
    bus = EventBus()
    events: list[str] = []
    
    def handler(event: str) -> None:
        events.append(event)
        
    bus.subscribe("test_event", handler)
    bus.publish("test_event", "first")
    bus.unsubscribe("test_event", handler)
    bus.publish("test_event", "second")
    
    assert events == ["first"]

def test_multiple_subscribers() -> None:
    bus = EventBus()
    results: dict[str, int] = {"h1": 0, "h2": 0}
    
    def h1(event: int) -> None:
        results["h1"] += event
        
    def h2(event: int) -> None:
        results["h2"] += event * 2
        
    bus.subscribe("calc", h1)
    bus.subscribe("calc", h2)
    bus.publish("calc", 5)
    
    assert results["h1"] == 5
    assert results["h2"] == 10

def test_handler_exception_does_not_crash_publisher() -> None:
    bus = EventBus()
    events: list[str] = []
    
    def bad_handler(event: str) -> None:
        raise RuntimeError("Something went wrong")
        
    def good_handler(event: str) -> None:
        events.append(event)
        
    bus.subscribe("danger", bad_handler)
    bus.subscribe("danger", good_handler)
    
    # Should not raise exception
    bus.publish("danger", "safe")
    
    assert events == ["safe"]
