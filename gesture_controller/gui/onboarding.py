import sys
import os
import platform
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QWidget,
    QProgressBar,
    QApplication,
)
from PyQt6.QtGui import QFont, QColor, QPalette

import structlog

logger = structlog.get_logger(__name__)


# Config Directory Marker
def get_onboarded_marker_path() -> Path:
    if platform.system() == "Windows":
        base_dir = Path(os.environ.get("APPDATA", "")) / "gesture_controller"
    elif platform.system() == "Darwin":
        base_dir = Path.home() / "Library" / "Application Support" / "gesture_controller"
    else:
        base_dir = Path.home() / ".config" / "gesture_controller"
    return base_dir / ".onboarded"


class OnboardingWizard(QDialog):
    """First-run onboarding wizard to check and configure system permissions."""

    finished_successfully = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Maestro Onboarding & Permissions")
        self.setFixedSize(550, 420)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
        )

        # Enable dark theme aesthetics
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QLabel {
                color: #cdd6f4;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #7f849c;
            }
            QPushButton#secondary {
                background-color: #313244;
                color: #cdd6f4;
            }
            QPushButton#secondary:hover {
                background-color: #45475a;
            }
        """)

        self.init_ui()
        self.check_permissions()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header title
        self.title_label = QLabel(self.tr("Welcome to Maestro"))
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Main instruction/status description
        self.desc_label = QLabel(
            self.tr(
                "To get started, we need to verify a few system permissions to ensure gesture detection and OS controls work properly on your machine."
            )
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setFont(QFont("Segoe UI", 11))
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)

        # Status layout
        self.status_widget = QWidget()
        status_layout = QVBoxLayout(self.status_widget)
        status_layout.setSpacing(12)

        # Row 1: Camera
        self.cam_row = QWidget()
        cam_layout = QHBoxLayout(self.cam_row)
        cam_layout.setContentsMargins(0, 0, 0, 0)
        self.cam_title = QLabel(self.tr("📷 Camera Access:"))
        self.cam_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.cam_status = QLabel(self.tr("Checking..."))
        self.cam_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        cam_layout.addWidget(self.cam_title)
        cam_layout.addWidget(self.cam_status)
        status_layout.addWidget(self.cam_row)

        # Row 2: OS Interaction (Accessibility/UIPI/udev)
        self.os_row = QWidget()
        os_layout = QHBoxLayout(self.os_row)
        os_layout.setContentsMargins(0, 0, 0, 0)
        self.os_title = QLabel(self.tr("⚙️ OS Input Control:"))
        self.os_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.os_status = QLabel(self.tr("Checking..."))
        self.os_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        os_layout.addWidget(self.os_title)
        os_layout.addWidget(self.os_status)
        status_layout.addWidget(self.os_row)

        layout.addWidget(self.status_widget)

        # Footer buttons
        btn_layout = QHBoxLayout()
        self.help_btn = QPushButton(self.tr("Grant Permission"))
        self.help_btn.setObjectName("secondary")
        self.help_btn.setAccessibleName("Grant System Permission Button")
        self.help_btn.clicked.connect(self.request_system_permissions)
        btn_layout.addWidget(self.help_btn)

        btn_layout.addStretch()

        self.check_btn = QPushButton(self.tr("Re-check"))
        self.check_btn.setObjectName("secondary")
        self.check_btn.setAccessibleName("Re-check System Permissions Button")
        self.check_btn.clicked.connect(self.check_permissions)
        btn_layout.addWidget(self.check_btn)

        self.next_btn = QPushButton(self.tr("Continue"))
        self.next_btn.setAccessibleName("Continue to Application Button")
        self.next_btn.clicked.connect(self.complete_onboarding)
        btn_layout.addWidget(self.next_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def check_permissions(self) -> None:
        """Evaluate system permissions dynamically based on operating system."""
        os_type = platform.system()

        self.camera_ok = False
        self.os_control_ok = False

        # Camera check (generic fallback uses OpenCV import attempt)
        try:
            import cv2

            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                self.camera_ok = True
                cap.release()
        except Exception:
            self.camera_ok = False

        if os_type == "Windows":
            # Windows camera is generally open, input control check:
            # Check if running as admin (recommended for UIPI control of Admin apps)
            import ctypes

            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                self.os_control_ok = True  # Always allowed to simulate, but notify user
            except Exception:
                is_admin = False
                self.os_control_ok = True

            self.cam_status.setText("✅ Access Granted")
            self.cam_status.setStyleSheet("color: #a6e3a1;")

            if is_admin:
                self.os_status.setText("✅ Running as Administrator")
                self.os_status.setStyleSheet("color: #a6e3a1;")
            else:
                self.os_status.setText("⚠️ Standard User (UIPI Enabled)")
                self.os_status.setStyleSheet("color: #f9e2af;")

        elif os_type == "Darwin":
            # macOS check permissions
            # Camera access
            try:
                from AVFoundation import AVCaptureDevice

                # AVAuthorizationStatusAuthorized = 3
                status = AVCaptureDevice.authorizationStatusForMediaType_("vide")
                self.camera_ok = status == 3
            except Exception:
                self.camera_ok = False

            # Accessibility process trust
            try:
                from ApplicationServices import AXIsProcessTrusted

                self.os_control_ok = AXIsProcessTrusted()
            except Exception:
                self.os_control_ok = False

            if self.camera_ok:
                self.cam_status.setText("✅ Access Granted")
                self.cam_status.setStyleSheet("color: #a6e3a1;")
            else:
                self.cam_status.setText("❌ Permission Missing")
                self.cam_status.setStyleSheet("color: #f38ba8;")

            if self.os_control_ok:
                self.os_status.setText("✅ Process Trusted")
                self.os_status.setStyleSheet("color: #a6e3a1;")
            else:
                self.os_status.setText("❌ Accessibility Blocked")
                self.os_status.setStyleSheet("color: #f38ba8;")

        else:
            # Linux checks
            # Group uinput check
            uinput_writable = os.access("/dev/uinput", os.W_OK)
            self.os_control_ok = uinput_writable

            if self.camera_ok:
                self.cam_status.setText("✅ Access Granted")
                self.cam_status.setStyleSheet("color: #a6e3a1;")
            else:
                self.cam_status.setText("❌ Video0 Inaccessible")
                self.cam_status.setStyleSheet("color: #f38ba8;")

            if uinput_writable:
                self.os_status.setText("✅ /dev/uinput Writable")
                self.os_status.setStyleSheet("color: #a6e3a1;")
            else:
                self.os_status.setText("❌ /dev/uinput Permission Denied")
                self.os_status.setStyleSheet("color: #f38ba8;")

        # Enable/Disable continue button
        # On Windows/Linux we can continue anyway, on macOS Accessibility is a blocker
        if os_type == "Darwin" and not self.os_control_ok:
            self.next_btn.setEnabled(False)
            self.next_btn.setToolTip(
                "Please grant Accessibility permission in System Settings to continue."
            )
        else:
            self.next_btn.setEnabled(True)
            self.next_btn.setToolTip("")

    def request_system_permissions(self) -> None:
        """Launch system preference panels or print manual installer setup instructions."""
        os_type = platform.system()

        if os_type == "Darwin":
            # Launch macOS System Preferences
            if not self.os_control_ok:
                os.system(
                    'open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"'
                )
            if not self.camera_ok:
                os.system(
                    'open "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"'
                )
        elif os_type == "Linux":
            # Linux: instruct user to run the udev installer script
            logger.info(
                "Linux: Execute 'sudo ./packaging/linux/install.sh' to establish permissions."
            )
            self.os_status.setText("ℹ️ Run packaging/linux/install.sh")
            self.os_status.setStyleSheet("color: #89b4fa;")
        else:
            # Windows: running as admin instruction
            logger.info(
                "Windows: If unable to control elevated applications, restart Maestro as Administrator."
            )
            self.os_status.setText("ℹ️ Restart as Administrator if needed")
            self.os_status.setStyleSheet("color: #89b4fa;")

    def complete_onboarding(self) -> None:
        """Write the onboarding confirmation marker file and exit dialog."""
        marker = get_onboarded_marker_path()
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
            logger.info("Onboarding wizard finished and marker file written", path=str(marker))
        except Exception as e:
            logger.error("Failed to write onboarding marker file", error=str(e))

        self.finished_successfully.emit()
        self.accept()


def is_onboarded() -> bool:
    """Return True if onboarding was completed previously."""
    return get_onboarded_marker_path().exists()
