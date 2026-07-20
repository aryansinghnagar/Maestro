"""Unit tests for Sprint 18 — CrashReportViewerDialog.

Tests:
1. Dialog initialization and empty state rendering.
2. Loading single and multiple crash report JSON files.
3. Traceback & system info display in QTextEdits.
4. Scrub / redaction toggle behavior.
5. Deleting selected crash report.
6. Clearing all crash reports.
7. Diagnostics export ZIP trigger via mock.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gesture_controller.gui.crash_report_dialog import CrashReportViewerDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_crash_dir(tmp_path):
    crash_dir = tmp_path / "crash_reports"
    crash_dir.mkdir(parents=True, exist_ok=True)
    return crash_dir


def _create_sample_crash_json(
    crash_dir: Path, report_id: str, exc_msg: str = "Test failure"
) -> Path:
    data = {
        "report_version": 1,
        "report_id": report_id,
        "timestamp": "2026-07-20T12:00:00.000000+00:00",
        "thread": "MainThread",
        "exception": {
            "type": "builtins.ValueError",
            "message": exc_msg,
            "traceback": f"Traceback (most recent call last):\n  File 'chrome.exe', line 10\nValueError: {exc_msg}\n",
        },
        "system": {
            "platform": {"system": "Windows", "python": "3.11.0"},
            "packages": {"PyQt6": "6.5.0"},
        },
    }
    path = crash_dir / f"crash_2026-07-20_{report_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_dialog_empty_state(qapp, temp_crash_dir):
    dialog = CrashReportViewerDialog(crash_dir=temp_crash_dir)
    assert dialog.report_list.count() == 1
    assert "No crash reports found" in dialog.report_list.item(0).text()
    assert dialog.delete_btn.isEnabled() is False
    assert dialog.clear_all_btn.isEnabled() is False
    dialog.deleteLater()


def test_dialog_populates_reports(qapp, temp_crash_dir):
    p1 = _create_sample_crash_json(temp_crash_dir, "r101", "Invalid coordinate")
    p2 = _create_sample_crash_json(temp_crash_dir, "r102", "Division by zero")

    dialog = CrashReportViewerDialog(crash_dir=temp_crash_dir)
    assert dialog.report_list.count() == 2
    assert dialog.delete_btn.isEnabled() is True
    assert dialog.clear_all_btn.isEnabled() is True

    # First report should be selected by default
    assert "ValueError" in dialog.report_list.item(0).text()
    assert "ValueError" in dialog.tb_edit.toPlainText()
    assert "Windows" in dialog.sys_edit.toPlainText()
    dialog.deleteLater()


def test_dialog_redaction_toggle(qapp, temp_crash_dir):
    p1 = _create_sample_crash_json(temp_crash_dir, "r201", "Failure in chrome.exe")

    dialog = CrashReportViewerDialog(crash_dir=temp_crash_dir)
    # Scrub is checked by default
    text_redacted = dialog.tb_edit.toPlainText()
    assert "[REDACTED]" in text_redacted

    # Uncheck scrub
    dialog.scrub_cb.setChecked(False)
    text_unredacted = dialog.tb_edit.toPlainText()
    assert "chrome.exe" in text_unredacted
    dialog.deleteLater()


def test_dialog_delete_selected(qapp, temp_crash_dir):
    p1 = _create_sample_crash_json(temp_crash_dir, "d101", "Err 1")
    p2 = _create_sample_crash_json(temp_crash_dir, "d102", "Err 2")

    dialog = CrashReportViewerDialog(crash_dir=temp_crash_dir)
    assert dialog.report_list.count() == 2

    dialog._delete_selected()
    assert dialog.report_list.count() == 1
    assert not p1.exists() or not p2.exists()
    dialog.deleteLater()


def test_dialog_clear_all(qapp, temp_crash_dir):
    _create_sample_crash_json(temp_crash_dir, "c101", "Err 1")
    _create_sample_crash_json(temp_crash_dir, "c102", "Err 2")

    dialog = CrashReportViewerDialog(crash_dir=temp_crash_dir)
    assert dialog.report_list.count() == 2

    with patch(
        "PyQt6.QtWidgets.QMessageBox.question",
        return_value=pytest.importorskip("PyQt6.QtWidgets").QMessageBox.StandardButton.Yes,
    ):
        dialog._clear_all()

    assert dialog.report_list.count() == 1
    assert "No crash reports found" in dialog.report_list.item(0).text()
    dialog.deleteLater()


def test_dialog_export_diagnostics(qapp, temp_crash_dir, tmp_path):
    dialog = CrashReportViewerDialog(crash_dir=temp_crash_dir)
    out_zip = tmp_path / "output_test_diag.zip"

    with (
        patch(
            "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(str(out_zip), "Zip Archives (*.zip)"),
        ),
        patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        dialog.export_diagnostics()
        assert out_zip.exists()
        mock_info.assert_called_once()

    dialog.deleteLater()
