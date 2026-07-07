from __future__ import annotations

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtCore import QObject, pyqtSignal, Qt, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
import structlog

logger = structlog.get_logger(__name__)


def create_tray_icon(paused: bool) -> QIcon:
    """Create a hand silhouette tray icon programmatically."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Active color: modern green; Paused color: modern red
    color = QColor("#ff4d4d") if paused else QColor("#00ff88")
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(Qt.GlobalColor.transparent))

    # Palm circle
    painter.drawEllipse(8, 12, 16, 16)
    # 4 fingers
    painter.drawRect(8, 4, 3, 10)  # Index
    painter.drawRect(12, 2, 3, 12)  # Middle
    painter.drawRect(16, 4, 3, 10)  # Ring
    painter.drawRect(20, 7, 3, 7)  # Pinky
    # Thumb
    painter.drawRect(3, 10, 6, 3)  # Thumb

    painter.end()
    return QIcon(pixmap)


class TrayController(QObject):
    """System Tray interface managing status tooltips, pause states, and balloon notifications."""

    pause_toggled = pyqtSignal(bool)  # True = paused
    settings_requested = pyqtSignal()
    export_diagnostics_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    message_clicked = pyqtSignal()

    def __init__(self, event_bus, parent=None) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._paused = False
        self._camera_active = True

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(create_tray_icon(self._paused))
        self._setup_menu()

        self._tray_icon.activated.connect(self._on_activated)
        self._tray_icon.messageClicked.connect(self.message_clicked.emit)

    def _setup_menu(self) -> None:
        self._menu = QMenu()

        # Camera status action (disabled, informational)
        self._status_action = self._menu.addAction("Camera: Connected")
        self._status_action.setEnabled(False)
        self._menu.addSeparator()

        # Pause/Resume toggle
        self._pause_action = self._menu.addAction("Pause Recognition")
        self._pause_action.triggered.connect(self.toggle_pause)

        # Settings
        settings_action = self._menu.addAction("Settings")
        settings_action.triggered.connect(self.settings_requested.emit)

        # Export Diagnostics
        export_action = self._menu.addAction("Export Diagnostics")
        export_action.triggered.connect(self.export_diagnostics_requested.emit)

        self._menu.addSeparator()

        # Quit
        quit_action = self._menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)

        self._tray_icon.setContextMenu(self._menu)

    def show(self) -> None:
        self._tray_icon.show()

    def hide(self) -> None:
        self._tray_icon.hide()

    def toggle_pause(self) -> None:
        """Toggle recognition pause state."""
        self._paused = not self._paused
        self._tray_icon.setIcon(create_tray_icon(self._paused))

        if self._paused:
            self._pause_action.setText("Resume Recognition")
        else:
            self._pause_action.setText("Pause Recognition")

        self.pause_toggled.emit(self._paused)
        logger.info("Recognition pause toggled via tray", paused=self._paused)

    def update_status(self, fps: float, gesture_count: int) -> None:
        """Update live status tooltip info."""
        state_str = "PAUSED" if self._paused else "ACTIVE"
        cam_str = "Connected" if self._camera_active else "Disconnected"
        tooltip = (
            f"Gesture Control ({state_str})\n"
            f"Camera: {cam_str}\n"
            f"FPS: {fps:.1f} | Gestures: {gesture_count}"
        )
        self._tray_icon.setToolTip(tooltip)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.settings_requested.emit()

    @pyqtSlot()
    def _on_camera_disconnected_gui(self) -> None:
        """Runs on GUI thread via GuiEventBridge signal."""
        self._camera_active = False
        self._status_action.setText("Camera: Disconnected")
        self._tray_icon.showMessage(
            "Camera Disconnected",
            "Gesture tracking is suspended until camera is reconnected.",
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )

    @pyqtSlot()
    def _on_camera_recovered_gui(self) -> None:
        """Runs on GUI thread via GuiEventBridge signal."""
        self._camera_active = True
        self._status_action.setText("Camera: Connected")
        self._tray_icon.showMessage(
            "Camera Connected",
            "Gesture tracking resumed.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def show_message(self, title: str, message: str) -> None:
        self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)
