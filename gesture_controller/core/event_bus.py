import queue
import threading
from typing import Any, Callable
import structlog

logger = structlog.get_logger(__name__)

class EventBus:
    """In-process publish/subscribe.
    Subscribers are registered for specific event types and are called in the publishing thread.
    Keep handlers fast and non-blocking."""

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue_size)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Register a handler for an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Unregister a handler for an event type."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h != handler
                ]

    def publish(self, event_type: str, event: Any) -> None:
        """Publish an event to all registered subscribers."""
        with self._lock:
            # Copy list of handlers to prevent race conditions during iteration
            handlers = list(self._subscribers.get(event_type, []))
            
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler failed", event_type=event_type)
