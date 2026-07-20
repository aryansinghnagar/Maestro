"""Unit tests for Sprint 14 — Crash Reporting & Diagnostics.

Covers:
- gather_system_info: keys present, types correct
- write_crash_report: file created, JSON valid, traceback captured
- CrashReporter: install/uninstall hooks, list_reports, prune_old_reports
- crash hook invocation with non-KeyboardInterrupt
- KeyboardInterrupt passthrough (not caught)
- threading.excepthook wiring
- event_bus publish on crash
- compliance.export_data includes system_info.json and crash_reports/
"""

from __future__ import annotations

import json
import sys
import threading
import types
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# gather_system_info
# ---------------------------------------------------------------------------


class TestGatherSystemInfo:
    def test_returns_dict(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        info = gather_system_info()
        assert isinstance(info, dict)

    def test_has_platform_key(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        info = gather_system_info()
        assert "platform" in info

    def test_platform_has_system(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        plat = gather_system_info()["platform"]
        assert "system" in plat
        assert isinstance(plat["system"], str)

    def test_platform_has_python_version_info(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        plat = gather_system_info()["platform"]
        assert "python_version_info" in plat
        assert isinstance(plat["python_version_info"], list)
        assert len(plat["python_version_info"]) == 3

    def test_has_packages_key(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        info = gather_system_info()
        assert "packages" in info
        assert isinstance(info["packages"], dict)

    def test_packages_includes_pyqt6(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        pkgs = gather_system_info()["packages"]
        assert "PyQt6" in pkgs

    def test_result_is_json_serialisable(self) -> None:
        from gesture_controller.core.crash_reporter import gather_system_info

        info = gather_system_info()
        serialised = json.dumps(info, default=str)
        assert json.loads(serialised)


# ---------------------------------------------------------------------------
# write_crash_report
# ---------------------------------------------------------------------------


class TestWriteCrashReport:
    def _make_exc(self):
        try:
            raise ValueError("test crash")
        except ValueError:
            return sys.exc_info()

    def test_creates_file(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        exc_type, exc_value, exc_tb = self._make_exc()
        path = write_crash_report(exc_type, exc_value, exc_tb, crash_dir=tmp_path)
        assert path.exists()
        assert path.suffix == ".json"

    def test_report_is_valid_json(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        exc_type, exc_value, exc_tb = self._make_exc()
        path = write_crash_report(exc_type, exc_value, exc_tb, crash_dir=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_report_has_required_keys(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        exc_type, exc_value, exc_tb = self._make_exc()
        path = write_crash_report(exc_type, exc_value, exc_tb, crash_dir=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("report_version", "report_id", "timestamp", "thread", "exception", "system"):
            assert key in data, f"Missing key: {key}"

    def test_report_captures_exception_message(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        exc_type, exc_value, exc_tb = self._make_exc()
        path = write_crash_report(exc_type, exc_value, exc_tb, crash_dir=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "test crash" in data["exception"]["message"]

    def test_report_captures_traceback(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        exc_type, exc_value, exc_tb = self._make_exc()
        path = write_crash_report(exc_type, exc_value, exc_tb, crash_dir=tmp_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "ValueError" in data["exception"]["traceback"]

    def test_report_captures_thread_name(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        exc_type, exc_value, exc_tb = self._make_exc()
        path = write_crash_report(
            exc_type, exc_value, exc_tb, crash_dir=tmp_path, thread_name="WorkerThread"
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["thread"] == "WorkerThread"

    def test_creates_crash_dir_if_missing(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import write_crash_report

        crash_dir = tmp_path / "nested" / "crash_reports"
        exc_type, exc_value, exc_tb = self._make_exc()
        write_crash_report(exc_type, exc_value, exc_tb, crash_dir=crash_dir)
        assert crash_dir.exists()


# ---------------------------------------------------------------------------
# CrashReporter lifecycle
# ---------------------------------------------------------------------------


class TestCrashReporter:
    def test_install_replaces_excepthook(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        original = sys.excepthook
        reporter = CrashReporter(crash_dir=tmp_path / "cr", show_dialog=False)
        reporter.install()
        assert sys.excepthook is not original
        reporter.uninstall()
        assert sys.excepthook is original or sys.excepthook is sys.__excepthook__

    def test_install_idempotent(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        reporter = CrashReporter(crash_dir=tmp_path / "cr", show_dialog=False)
        reporter.install()
        hook1 = sys.excepthook
        reporter.install()  # second install should be no-op
        hook2 = sys.excepthook
        assert hook1 is hook2
        reporter.uninstall()

    def test_uninstall_before_install_is_safe(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        reporter = CrashReporter(crash_dir=tmp_path / "cr", show_dialog=False)
        reporter.uninstall()  # should not raise

    def test_list_reports_empty_before_crash(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        reporter = CrashReporter(crash_dir=tmp_path / "cr", show_dialog=False)
        assert reporter.list_reports() == []

    def test_list_reports_returns_newest_first(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter, write_crash_report
        import time

        crash_dir = tmp_path / "cr"
        reporter = CrashReporter(crash_dir=crash_dir, show_dialog=False)

        try:
            raise RuntimeError("first")
        except RuntimeError:
            et, ev, tb = sys.exc_info()
        p1 = write_crash_report(et, ev, tb, crash_dir=crash_dir)
        time.sleep(0.01)
        try:
            raise RuntimeError("second")
        except RuntimeError:
            et, ev, tb = sys.exc_info()
        p2 = write_crash_report(et, ev, tb, crash_dir=crash_dir)

        reports = reporter.list_reports()
        assert reports[0] == p2  # newest first

    def test_prune_old_reports(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter, write_crash_report

        crash_dir = tmp_path / "cr"
        reporter = CrashReporter(crash_dir=crash_dir, show_dialog=False, max_reports=3)

        try:
            raise RuntimeError("x")
        except RuntimeError:
            et, ev, tb = sys.exc_info()
        # Write 5 reports
        for _ in range(5):
            write_crash_report(et, ev, tb, crash_dir=crash_dir)
        reporter._prune_old_reports()
        assert len(reporter.list_reports()) <= 3

    def test_excepthook_writes_report_on_crash(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        crash_dir = tmp_path / "cr"
        reporter = CrashReporter(crash_dir=crash_dir, show_dialog=False)
        reporter.install()
        try:
            try:
                raise TypeError("boom")
            except TypeError:
                et, ev, tb = sys.exc_info()
            sys.excepthook(et, ev, tb)
        finally:
            reporter.uninstall()
        assert len(reporter.list_reports()) >= 1

    def test_excepthook_passes_through_keyboard_interrupt(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        crash_dir = tmp_path / "cr"
        reporter = CrashReporter(crash_dir=crash_dir, show_dialog=False)
        reporter.install()
        with patch.object(sys, "__excepthook__") as mock_default:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
            mock_default.assert_called_once()
        reporter.uninstall()
        assert reporter.list_reports() == []  # no crash written

    def test_event_bus_published_on_crash(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import CrashReporter

        mock_bus = MagicMock()
        crash_dir = tmp_path / "cr"
        reporter = CrashReporter(crash_dir=crash_dir, event_bus=mock_bus, show_dialog=False)
        reporter.install()
        try:
            raise ValueError("bus test")
        except ValueError:
            et, ev, tb = sys.exc_info()
        sys.excepthook(et, ev, tb)
        reporter.uninstall()
        mock_bus.publish.assert_called_once()
        args = mock_bus.publish.call_args[0]
        assert args[0] == "crash_occurred"


# ---------------------------------------------------------------------------
# install_crash_handler convenience function
# ---------------------------------------------------------------------------


class TestInstallCrashHandler:
    def test_returns_installed_reporter(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import install_crash_handler, CrashReporter

        reporter = install_crash_handler(user_dir=tmp_path, show_dialog=False)
        assert isinstance(reporter, CrashReporter)
        assert reporter._installed is True
        reporter.uninstall()

    def test_uses_user_data_dir_by_default(self, tmp_path) -> None:
        from gesture_controller.core.crash_reporter import install_crash_handler

        # user_data_dir is imported lazily inside install_crash_handler; patch at source
        with patch("gesture_controller.core.paths.user_data_dir", return_value=tmp_path):
            reporter = install_crash_handler(show_dialog=False)
        assert reporter.crash_dir == tmp_path / "crash_reports"
        reporter.uninstall()


# ---------------------------------------------------------------------------
# compliance.export_data includes Sprint 14 additions
# ---------------------------------------------------------------------------


class TestComplianceExportSprint14:
    def test_export_includes_system_info(self, tmp_path) -> None:
        from gesture_controller.core.compliance import export_data

        out_zip = tmp_path / "diag.zip"
        with patch(
            "gesture_controller.core.compliance.get_user_data_dirs", return_value=[tmp_path]
        ):
            export_data(out_zip)

        with zipfile.ZipFile(out_zip, "r") as zf:
            names = zf.namelist()
        assert "system_info.json" in names

    def test_system_info_is_valid_json(self, tmp_path) -> None:
        from gesture_controller.core.compliance import export_data

        out_zip = tmp_path / "diag.zip"
        with patch(
            "gesture_controller.core.compliance.get_user_data_dirs", return_value=[tmp_path]
        ):
            export_data(out_zip)

        with zipfile.ZipFile(out_zip, "r") as zf:
            data = json.loads(zf.read("system_info.json").decode("utf-8"))
        assert "platform" in data

    def test_export_includes_crash_reports_if_present(self, tmp_path) -> None:
        from gesture_controller.core.compliance import export_data
        from gesture_controller.core.crash_reporter import write_crash_report

        crash_dir = tmp_path / "crash_reports"
        try:
            raise RuntimeError("sample crash")
        except RuntimeError:
            et, ev, tb = sys.exc_info()
        write_crash_report(et, ev, tb, crash_dir=crash_dir)

        out_zip = tmp_path / "diag.zip"
        # compliance imports user_data_dir lazily inside export_data; patch at source module
        with patch(
            "gesture_controller.core.compliance.get_user_data_dirs", return_value=[tmp_path]
        ):
            with patch("gesture_controller.core.paths.user_data_dir", return_value=tmp_path):
                export_data(out_zip)

        with zipfile.ZipFile(out_zip, "r") as zf:
            names = zf.namelist()
        assert any("crash_reports/" in n for n in names)

    def test_export_caps_crash_reports_at_10(self, tmp_path) -> None:
        from gesture_controller.core.compliance import export_data
        from gesture_controller.core.crash_reporter import write_crash_report

        crash_dir = tmp_path / "crash_reports"
        try:
            raise RuntimeError("many crashes")
        except RuntimeError:
            et, ev, tb = sys.exc_info()
        for _ in range(15):
            write_crash_report(et, ev, tb, crash_dir=crash_dir)

        out_zip = tmp_path / "diag.zip"
        with patch(
            "gesture_controller.core.compliance.get_user_data_dirs", return_value=[tmp_path]
        ):
            with patch("gesture_controller.core.compliance.user_data_dir", return_value=tmp_path):
                export_data(out_zip)

        with zipfile.ZipFile(out_zip, "r") as zf:
            crash_entries = [n for n in zf.namelist() if n.startswith("crash_reports/")]
        assert len(crash_entries) <= 10
