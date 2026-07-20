"""Crash Report Viewer & Diagnostics Dialog — Sprint 18.

Provides a user interface for:
1. Viewing list of recorded crash reports from ``<user_data>/crash_reports/``.
2. Inspecting detailed stack traces, exception messages, and system metadata.
3. Exporting sanitized diagnostic ZIP archives (integrating ``compliance.export_data``).
4. Deleting crash reports or clearing history.
5. Scrubbing sensitive data toggle before copying or exporting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QClipboard
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QPushButton,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QWidget,
    QTabWidget,
)

from gesture_controller.core.crash_reporter import CrashReporter
from gesture_controller.core.compliance import export_data, redact_logs_text
from gesture_controller.core.paths import user_data_dir
import structlog

logger = structlog.get_logger(__name__)


class CrashReportViewerDialog(QDialog):
    """GUI dialog for managing crash reports and exporting diagnostic archives."""

    def __init__(self, parent: Optional[QWidget] = None, crash_dir: Optional[Path] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Maestro Crash Reports & Diagnostics"))
        self.resize(780, 520)

        self._crash_dir = crash_dir or (user_data_dir() / "crash_reports")
        self._reporter = CrashReporter(self._crash_dir)
        self._reports_data: dict[str, dict[str, Any]] = {}

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QLabel {
                color: #cdd6f4;
            }
            QListWidget {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #313244;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #11111b;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #181825;
                color: #a6e3a1;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton#secondary {
                background-color: #313244;
                color: #cdd6f4;
            }
            QPushButton#secondary:hover {
                background-color: #45475a;
            }
            QPushButton#danger {
                background-color: #f38ba8;
                color: #11111b;
            }
            QPushButton#danger:hover {
                background-color: #f5e0dc;
            }
            QCheckBox {
                color: #cdd6f4;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 6px;
            }
        """)

        self._init_ui()
        self.refresh_reports()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel(self.tr("📋 Crash Logs & System Diagnostics"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.scrub_cb = QCheckBox(self.tr("Redact sensitive app/path names"))
        self.scrub_cb.setChecked(True)
        self.scrub_cb.toggled.connect(self._on_scrub_toggled)
        header_layout.addWidget(self.scrub_cb)

        main_layout.addLayout(header_layout)

        # Splitter: Left = Crash List, Right = Details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Container
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_label = QLabel(self.tr("Recorded Crash Reports:"))
        left_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        left_layout.addWidget(left_label)

        self.report_list = QListWidget()
        self.report_list.setAccessibleName("Crash Report List")
        self.report_list.currentItemChanged.connect(self._on_report_selected)
        left_layout.addWidget(self.report_list)

        list_btn_row = QHBoxLayout()
        self.delete_btn = QPushButton(self.tr("Delete"))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setAccessibleName("Delete Selected Report Button")
        self.delete_btn.clicked.connect(self._delete_selected)
        list_btn_row.addWidget(self.delete_btn)

        self.clear_all_btn = QPushButton(self.tr("Clear All"))
        self.clear_all_btn.setObjectName("secondary")
        self.clear_all_btn.setAccessibleName("Clear All Reports Button")
        self.clear_all_btn.clicked.connect(self._clear_all)
        list_btn_row.addWidget(self.clear_all_btn)

        left_layout.addLayout(list_btn_row)
        splitter.addWidget(left_widget)

        # Right Container
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.tab_widget = QTabWidget()

        # Tab 1: Stack Trace
        self.tb_edit = QTextEdit()
        self.tb_edit.setReadOnly(True)
        self.tb_edit.setAccessibleName("Stack Trace Viewer")
        self.tab_widget.addTab(self.tb_edit, self.tr("Stack Trace"))

        # Tab 2: System Metadata
        self.sys_edit = QTextEdit()
        self.sys_edit.setReadOnly(True)
        self.sys_edit.setAccessibleName("System Info Viewer")
        self.tab_widget.addTab(self.sys_edit, self.tr("System Metadata"))

        right_layout.addWidget(self.tab_widget)

        copy_row = QHBoxLayout()
        self.copy_tb_btn = QPushButton(self.tr("Copy Stack Trace"))
        self.copy_tb_btn.setObjectName("secondary")
        self.copy_tb_btn.clicked.connect(self._copy_traceback)
        copy_row.addWidget(self.copy_tb_btn)

        self.copy_path_btn = QPushButton(self.tr("Copy Report Path"))
        self.copy_path_btn.setObjectName("secondary")
        self.copy_path_btn.clicked.connect(self._copy_report_path)
        copy_row.addWidget(self.copy_path_btn)

        right_layout.addLayout(copy_row)
        splitter.addWidget(right_widget)

        splitter.setSizes([260, 480])
        main_layout.addWidget(splitter)

        # Footer Actions
        footer_layout = QHBoxLayout()

        self.export_zip_btn = QPushButton(self.tr("Export Diagnostics Archive (.zip)"))
        self.export_zip_btn.setAccessibleName("Export Diagnostics Archive Button")
        self.export_zip_btn.clicked.connect(self.export_diagnostics)
        footer_layout.addWidget(self.export_zip_btn)

        footer_layout.addStretch()

        self.close_btn = QPushButton(self.tr("Close"))
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)

        main_layout.addLayout(footer_layout)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def refresh_reports(self) -> None:
        """Scan crash directory and populate the list widget."""
        self.report_list.clear()
        self._reports_data.clear()
        self.tb_edit.clear()
        self.sys_edit.clear()

        reports = self._reporter.list_reports()
        if not reports:
            item = QListWidgetItem(self.tr("No crash reports found"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.report_list.addItem(item)
            self.delete_btn.setEnabled(False)
            self.clear_all_btn.setEnabled(False)
            self.copy_tb_btn.setEnabled(False)
            self.copy_path_btn.setEnabled(False)
            return

        self.delete_btn.setEnabled(True)
        self.clear_all_btn.setEnabled(True)
        self.copy_tb_btn.setEnabled(True)
        self.copy_path_btn.setEnabled(True)

        for path in reports:
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
                ts = content.get("timestamp", "Unknown time")
                if "T" in ts:
                    ts_display = ts.split("T")[0] + " " + ts.split("T")[1][:8]
                else:
                    ts_display = ts
                exc_type = content.get("exception", {}).get("type", "Error").split(".")[-1]
                label = f"{ts_display} — {exc_type}"

                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self.report_list.addItem(item)
                self._reports_data[str(path)] = content
            except Exception as e:
                logger.error("Failed parsing crash report file", path=str(path), error=str(e))

        if self.report_list.count() > 0:
            self.report_list.setCurrentRow(0)

    def _on_report_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None = None) -> None:
        if not current:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        if not path_str or path_str not in self._reports_data:
            return

        report = self._reports_data[path_str]
        self._display_report(report)

    def _display_report(self, report: dict[str, Any]) -> None:
        exc_info = report.get("exception", {})
        tb_text = exc_info.get("traceback", "No traceback available.")
        msg = exc_info.get("message", "")
        exc_type = exc_info.get("type", "")

        full_tb = f"Exception: {exc_type}\nMessage: {msg}\n\n{tb_text}"
        if self.scrub_cb.isChecked():
            full_tb = redact_logs_text(full_tb)

        self.tb_edit.setPlainText(full_tb)

        sys_info = report.get("system", {})
        sys_pretty = json.dumps(sys_info, indent=2, default=str)
        self.sys_edit.setPlainText(sys_pretty)

    def _on_scrub_toggled(self, checked: bool) -> None:
        current_item = self.report_list.currentItem()
        if current_item:
            self._on_report_selected(current_item)

    def _delete_selected(self) -> None:
        current = self.report_list.currentItem()
        if not current:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        if path_str:
            try:
                Path(path_str).unlink(missing_ok=True)
                logger.info("Deleted crash report", path=path_str)
            except Exception as e:
                logger.error("Failed to delete crash report", error=str(e))
            self.refresh_reports()

    def _clear_all(self) -> None:
        reports = self._reporter.list_reports()
        if not reports:
            return
        reply = QMessageBox.question(
            self,
            self.tr("Clear All Crash Reports"),
            self.tr("Are you sure you want to delete all recorded crash reports?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for p in reports:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            self.refresh_reports()

    def _copy_traceback(self) -> None:
        text = self.tb_edit.toPlainText()
        if text:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.clipboard().setText(text)
                logger.info("Copied crash traceback to clipboard")

    def _copy_report_path(self) -> None:
        current = self.report_list.currentItem()
        if not current:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        if path_str:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.clipboard().setText(path_str)
                logger.info("Copied crash report path to clipboard")

    def export_diagnostics(self) -> None:
        """Prompt user for destination and export a sanitized diagnostic ZIP bundle."""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Diagnostics Archive"),
            "maestro_diagnostics.zip",
            "Zip Archives (*.zip)",
        )
        if not save_path:
            return

        target_zip = Path(save_path)
        try:
            export_data(target_zip)
            QMessageBox.information(
                self,
                self.tr("Export Successful"),
                self.tr(f"Diagnostics bundle successfully exported to:\n{target_zip}"),
            )
            logger.info("Exported diagnostics bundle", path=str(target_zip))
        except Exception as e:
            logger.error("Failed exporting diagnostics bundle", error=str(e))
            QMessageBox.critical(
                self,
                self.tr("Export Failed"),
                self.tr(f"Failed to create diagnostics archive:\n{e}"),
            )
