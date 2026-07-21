import signal
import sys
from unittest.mock import MagicMock, patch
import pytest
from gesture_controller.core.signal_handler import SignalHandler


def test_signal_handler_basic_flow() -> None:
    called = False

    def shutdown_cb() -> None:
        nonlocal called
        called = True

    handler = SignalHandler(shutdown_cb)
    handler.install()
    # Re-install should be idempotent
    handler.install()
    assert handler._installed is True

    handler.uninstall()
    # Re-uninstall should be idempotent
    handler.uninstall()
    assert handler._installed is False


def test_signal_handler_trigger_sys_exit() -> None:
    called = False

    def shutdown_cb() -> None:
        nonlocal called
        called = True

    handler = SignalHandler(shutdown_cb)
    handler._old_sigint = signal.SIG_DFL

    with pytest.raises(SystemExit) as exc_info:
        handler._handle(signal.SIGINT, None)

    assert called is True
    assert exc_info.value.code == 128 + signal.SIGINT


def test_signal_handler_forward_to_custom_handler() -> None:
    called = False
    forwarded = False

    def shutdown_cb() -> None:
        nonlocal called
        called = True

    def old_handler(signum: int, frame: object) -> None:
        nonlocal forwarded
        forwarded = True

    handler = SignalHandler(shutdown_cb)
    handler._old_sigint = old_handler

    handler._handle(signal.SIGINT, None)

    assert called is True
    assert forwarded is True


def test_signal_handler_install_thread_value_error() -> None:
    handler = SignalHandler(lambda: None)
    with patch("signal.signal", side_effect=ValueError("signal only works in main thread")):
        handler.install()
        assert handler._installed is False

        handler._installed = True
        handler._old_sigint = signal.SIG_DFL
        handler._old_sigterm = signal.SIG_DFL
        handler.uninstall()
        assert handler._installed is False
