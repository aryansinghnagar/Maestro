"""Crash Reporter — Sprint 14.

Installs a global ``sys.excepthook`` and ``threading.excepthook`` that:
1. Write a structured JSON crash report to ``<user_data>/crash_reports/``.
2. Optionally show a PyQt6 crash dialog (when a QApplication exists).
3. Emit an event-bus event so other subsystems can react (e.g. flush buffers).

Usage::

    from gesture_controller.core.crash_reporter import install_crash_handler
    install_crash_handler(event_bus=bus, user_dir=paths.user_data_dir())
"""

from __future__ import annotations

import json
import platform
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_CRASH_REPORT_VERSION = 1


# ── System info ───────────────────────────────────────────────────────────────

def gather_system_info() -> dict[str, Any]:
    """Collect safe, non-PII system metadata for crash reports and diagnostics.

    Returns a dict with platform, Python, screen, and package version info.
    """
    info: dict[str, Any] = {}

    # ── Platform ────────────────────────────────────────────────────────────
    info["platform"] = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version,
        "python_version_info": list(sys.version_info[:3]),
    }

    # ── Screen info (Qt, optional) ──────────────────────────────────────────
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screens = app.screens()
            info["screens"] = [
                {
                    "name": s.name(),
                    "size": [s.size().width(), s.size().height()],
                    "dpi": round(s.logicalDotsPerInch(), 1),
                    "device_pixel_ratio": s.devicePixelRatio(),
                }
                for s in screens
            ]
    except Exception:
        info["screens"] = []

    # ── Key package versions ────────────────────────────────────────────────
    packages: dict[str, str] = {}
    _pkg_names = [
        "PyQt6", "mediapipe", "numpy", "structlog",
        "jsonschema", "pyautogui", "opencv-python",
    ]
    for pkg in _pkg_names:
        try:
            import importlib.metadata
            packages[pkg] = importlib.metadata.version(pkg)
        except Exception:
            packages[pkg] = "unknown"
    info["packages"] = packages

    return info


# ── Crash report writer ───────────────────────────────────────────────────────

def write_crash_report(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: Any,
    crash_dir: Path,
    thread_name: str = "MainThread",
) -> Path:
    """Serialise the exception + system info to a JSON file.

    Returns the path of the written report.
    """
    crash_dir.mkdir(parents=True, exist_ok=True)

    report_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    filename = f"crash_{timestamp[:10]}_{report_id}.json"
    report_path = crash_dir / filename

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)

    report: dict[str, Any] = {
        "report_version": _CRASH_REPORT_VERSION,
        "report_id": report_id,
        "timestamp": timestamp,
        "thread": thread_name,
        "exception": {
            "type": f"{exc_type.__module__}.{exc_type.__qualname__}",
            "message": str(exc_value),
            "traceback": "".join(tb_lines),
        },
        "system": gather_system_info(),
    }

    try:
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        logger.info("Crash report written", path=str(report_path), report_id=report_id)
    except Exception as write_err:
        logger.error("Failed to write crash report", error=str(write_err))

    return report_path


# ── Qt crash dialog ───────────────────────────────────────────────────────────

def _show_crash_dialog(report_path: Path, traceback_text: str) -> None:
    """Show a user-friendly crash dialog if a QApplication is running."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout
        from PyQt6.QtCore import Qt

        app = QApplication.instance()
        if app is None:
            return

        dialog = QDialog()
        dialog.setWindowTitle("Maestro — Unexpected Error")
        dialog.setMinimumSize(540, 360)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("⚠️ Maestro encountered an unexpected error")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "A crash report has been saved automatically.\n"
            f"Report: {report_path.name}\n\n"
            "You can include this file when reporting a bug."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Traceback
        tb_view = QTextEdit()
        tb_view.setReadOnly(True)
        tb_view.setPlainText(traceback_text)
        tb_view.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(tb_view)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton("Copy Report Path")
        copy_btn.setAccessibleName("Copy crash report path to clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(str(report_path)))
        btn_row.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setAccessibleName("Close crash dialog")
        close_btn.setDefault(True)
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)
        dialog.exec()
    except Exception:
        # Never let the crash dialog itself crash the process
        pass


# ── Hook installation ─────────────────────────────────────────────────────────

class CrashReporter:
    """Installs global exception hooks and manages crash report directories."""

    def __init__(
        self,
        crash_dir: Path,
        event_bus: Any = None,
        show_dialog: bool = True,
        max_reports: int = 50,
    ) -> None:
        self.crash_dir = crash_dir
        self._event_bus = event_bus
        self._show_dialog = show_dialog
        self._max_reports = max_reports
        self._installed = False

    def install(self) -> None:
        """Install sys.excepthook and threading.excepthook."""
        if self._installed:
            return

        _reporter = self  # capture for closures

        def _excepthook(
            exc_type: type[BaseException],
            exc_value: BaseException,
            exc_tb: Any,
        ) -> None:
            # Don't intercept KeyboardInterrupt
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_tb)
                return

            logger.critical(
                "Unhandled exception",
                exc_type=exc_type.__name__,
                exc_value=str(exc_value),
            )

            report_path = write_crash_report(
                exc_type, exc_value, exc_tb,
                crash_dir=_reporter.crash_dir,
                thread_name="MainThread",
            )
            _reporter._prune_old_reports()

            if _reporter._event_bus:
                try:
                    _reporter._event_bus.publish("crash_occurred", str(report_path))
                except Exception:
                    pass

            if _reporter._show_dialog:
                tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
                _show_crash_dialog(report_path, tb_text)

        def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
            if args.exc_type is None or issubclass(args.exc_type, SystemExit):
                return
            thread_name = args.thread.name if args.thread else "unknown"
            logger.critical(
                "Unhandled exception in thread",
                thread=thread_name,
                exc_type=args.exc_type.__name__ if args.exc_type else "?",
            )
            write_crash_report(
                args.exc_type,
                args.exc_value,
                args.exc_traceback,
                crash_dir=_reporter.crash_dir,
                thread_name=thread_name,
            )
            _reporter._prune_old_reports()

        sys.excepthook = _excepthook
        threading.excepthook = _threading_excepthook
        self._installed = True
        logger.info("Crash reporter installed", crash_dir=str(self.crash_dir))

    def uninstall(self) -> None:
        """Restore default exception hooks."""
        if not self._installed:
            return
        sys.excepthook = sys.__excepthook__
        threading.excepthook = threading.__excepthook__
        self._installed = False

    def list_reports(self) -> list[Path]:
        """Return crash report paths, newest-first."""
        if not self.crash_dir.exists():
            return []
        reports = sorted(
            self.crash_dir.glob("crash_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return reports

    def _prune_old_reports(self) -> None:
        """Delete oldest reports beyond the cap."""
        reports = self.list_reports()
        if len(reports) > self._max_reports:
            for old in reports[self._max_reports:]:
                try:
                    old.unlink()
                except OSError:
                    pass


# ── Convenience installer ─────────────────────────────────────────────────────

def install_crash_handler(
    event_bus: Any = None,
    user_dir: Path | None = None,
    show_dialog: bool = True,
    max_reports: int = 50,
) -> CrashReporter:
    """Create and install a :class:`CrashReporter`.

    Args:
        event_bus: Optional EventBus to publish ``crash_occurred`` events.
        user_dir: Root user-data directory. Defaults to ``user_data_dir()``.
        show_dialog: Whether to show a Qt dialog on crash (default ``True``).
        max_reports: Maximum number of crash report files to keep.

    Returns:
        The installed :class:`CrashReporter` instance.
    """
    if user_dir is None:
        from gesture_controller.core.paths import user_data_dir
        user_dir = user_data_dir()

    reporter = CrashReporter(
        crash_dir=user_dir / "crash_reports",
        event_bus=event_bus,
        show_dialog=show_dialog,
        max_reports=max_reports,
    )
    reporter.install()
    return reporter
