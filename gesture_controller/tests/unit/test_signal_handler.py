import pytest
from unittest.mock import MagicMock
from gesture_controller.core.signal_handler import SignalHandler


def test_signal_handler() -> None:
    called = False

    def shutdown_cb() -> None:
        nonlocal called
        called = True

    handler = SignalHandler(shutdown_cb)
    handler.install()
    # It should not throw ValueError or crash even if not main thread (handled by try-except)
    handler.uninstall()
