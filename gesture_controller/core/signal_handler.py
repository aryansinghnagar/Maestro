import logging
import signal
import sys
from typing import Callable, Any
import structlog

logger = structlog.get_logger(__name__)


class SignalHandler:
    """Handles SIGINT and SIGTERM for graceful shutdown."""

    def __init__(self, shutdown_callback: Callable[[], None]) -> None:
        self._shutdown = shutdown_callback
        self._installed = False
        self._old_sigint: Any = None
        self._old_sigterm: Any = None

    def install(self) -> None:
        """Install signal handlers."""
        if self._installed:
            return
        try:
            self._old_sigint = signal.signal(signal.SIGINT, self._handle)
            self._old_sigterm = signal.signal(signal.SIGTERM, self._handle)
            self._installed = True
            logger.debug("Signal handlers installed")
        except ValueError:
            # signal only works in main thread
            pass

    def uninstall(self) -> None:
        """Uninstall signal handlers."""
        if not self._installed:
            return
        if self._old_sigint is not None:
            try:
                signal.signal(signal.SIGINT, self._old_sigint)
            except ValueError:
                pass
        if self._old_sigterm is not None:
            try:
                signal.signal(signal.SIGTERM, self._old_sigterm)
            except ValueError:
                pass
        self._installed = False
        logger.debug("Signal handlers uninstalled")

    def _handle(self, signum: int, frame: Any) -> None:
        """Handle signal by triggering shutdown callback and forwarding or exiting."""
        logger.info("Signal received, shutting down...", signal=signum)
        self._shutdown()

        # Restore old handler and forward signal, or exit
        old_handler = self._old_sigint if signum == signal.SIGINT else self._old_sigterm
        if old_handler and old_handler is not signal.SIG_DFL and old_handler is not signal.SIG_IGN:
            if callable(old_handler):
                old_handler(signum, frame)
        else:
            sys.exit(128 + signum)
