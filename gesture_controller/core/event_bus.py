import queue
import threading
from typing import Any, Callable
import structlog

logger = structlog.get_logger(__name__)


class EventBus:
    """In-process publish/subscribe EventBus.
    Supports synchronous dispatch for latency-critical events (like gesture simulation)
    and asynchronous worker queue dispatch for telemetry or UI events."""

    SYNC_EVENTS: set[str] = set()

    def __init__(self, max_queue_size: int = 5000) -> None:
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}
        self._failures: dict[tuple[str, Callable[[Any], None]], int] = {}
        self._lock = threading.Lock()

        # Async Queue & Worker Thread (S3-9)
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=max_queue_size)
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="eventbus_async_worker"
        )
        self._worker_thread.start()

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Register a handler for an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
            self._failures[(event_type, handler)] = 0

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Unregister a handler for an event type."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    h for h in self._subscribers[event_type] if h != handler
                ]
            self._failures.pop((event_type, handler), None)

    def publish(self, event_type: str, event: Any) -> None:
        """Publish an event to all registered subscribers."""
        if event_type in self.SYNC_EVENTS:
            # Sync dispatch
            self._dispatch(event_type, event)
        else:
            # Async dispatch via worker queue
            try:
                self._queue.put_nowait((event_type, event))
            except queue.Full:
                logger.warning("EventBus async queue full, dropping event", event_type=event_type)

    def _dispatch(self, event_type: str, event: Any) -> None:
        """Perform actual event distribution."""
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        to_remove = []
        for handler in handlers:
            try:
                handler(event)
                # Successful execution, reset failure count (S3-2)
                with self._lock:
                    key = (event_type, handler)
                    if key in self._failures:
                        self._failures[key] = 0
            except Exception as e:
                logger.exception("Event handler failed", event_type=event_type, error=str(e))

                # Increment failure count and unsubscribe if threshold met (S3-2)
                with self._lock:
                    key = (event_type, handler)
                    if key in self._failures:
                        self._failures[key] += 1
                        fails = self._failures[key]
                        if fails >= 3:
                            logger.critical(
                                "Event handler exceeded consecutive failures threshold. Auto-unsubscribing.",
                                event_type=event_type,
                                handler=getattr(handler, "__name__", str(handler)),
                            )
                            to_remove.append(handler)

        for handler in to_remove:
            self.unsubscribe(event_type, handler)

    def _worker_loop(self) -> None:
        """Daemon worker executing async handler dispatches."""
        while True:
            try:
                event_type, event = self._queue.get()
                self._dispatch(event_type, event)
                self._queue.task_done()
            except Exception as e:
                logger.error("Error in EventBus async dispatcher worker loop", error=str(e))
