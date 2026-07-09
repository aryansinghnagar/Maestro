"""
PyQt6 QApplication init, wires GUI to engine.
Combined desktop app coordinator entry point.
"""

import sys
import signal
import structlog
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSlot

logger = structlog.get_logger(__name__)


def setup_logging(user_dir: Path) -> None:
    import logging
    import structlog
    from logging.handlers import RotatingFileHandler

    log_dir = user_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # Configure standard logging
    logging_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    logging_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(logging_handler)
    root_logger.addHandler(console_handler)

    # Configure structlog to use standard logging
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            (
                structlog.processors.JSONRenderer()
                if not sys.stderr.isatty()
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class GestureControllerApp:
    """Top-level application coordinator wiring Engine, Tray, Overlay, and Settings."""

    def __init__(self, config_path: str | None = None) -> None:
        # Enable high-DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        # Set up structured file logging
        from gesture_controller.core.config_manager import USER_CONFIG_DIRS
        import platform

        user_dir = USER_CONFIG_DIRS.get(platform.system(), Path.home())
        setup_logging(user_dir)

        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)  # Tray keeps app alive
        self._app.setApplicationName("Gesture Controller")

        # i18n setup: Load translation file based on system locale (S3-15)
        from PyQt6.QtCore import QTranslator, QLocale

        self._translator = QTranslator()
        translation_dir = Path(__file__).parent.parent / "data" / "translations"
        translation_dir.mkdir(parents=True, exist_ok=True)
        locale_name = QLocale.system().name()
        if self._translator.load(f"gesture_controller_{locale_name}", str(translation_dir)):
            self._app.installTranslator(self._translator)
            logger.info("Loaded translation file", locale=locale_name)

        # ── Initialize Engine ──────────────────────────────────────────────
        from gesture_controller.core.engine import GestureEngine

        path = Path(config_path) if config_path else None
        self._engine = GestureEngine(path)

        # Expose engine-internal objects for GUI wiring
        self._config = self._engine._config
        self._event_bus = self._engine._event_bus

        # ── Initialize GUI components ──────────────────────────────────────
        from gesture_controller.gui.tray_icon import TrayController
        from gesture_controller.gui.overlay import OverlayHUD
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.gui.gui_event_bridge import GuiEventBridge

        self._tray = TrayController(self._event_bus)
        self._overlay = OverlayHUD(self._config._config)

        # Provide a callback so GestureRecorder can pull live hand data
        def _get_current_hand():
            hands = self._engine.get_current_hands()
            return hands[0] if hands else None

        template_dir = (
            Path(self._engine._custom_matcher._template_dir)
            if hasattr(self._engine._custom_matcher, "_template_dir")
            else None
        )
        self._settings = SettingsWindow(
            self._config,
            landmark_callback=_get_current_hand,
            template_dir=template_dir,
            reload_callback=self._engine._custom_matcher.load_templates,
            parent=None,
        )

        # ── Signal wiring ──────────────────────────────────────────────────
        # Tray -> Engine pause
        self._tray.pause_toggled.connect(self._engine.set_paused)
        # Tray -> Settings window
        self._tray.settings_requested.connect(self._show_settings)
        # Tray -> Export Diagnostics
        self._tray.export_diagnostics_requested.connect(self._export_diagnostics)
        # Tray -> Quit
        self._tray.quit_requested.connect(self._shutdown)
        # Settings -> Config reload
        self._settings.config_changed.connect(self._on_config_changed)

        # Bridge engine-thread events to GUI thread via Qt signals
        self._bridge = GuiEventBridge(self._event_bus, parent=self._app)
        self._bridge.gesture_triggered.connect(self._on_gesture_triggered_gui)
        self._bridge.camera_disconnected.connect(self._tray._on_camera_disconnected_gui)
        self._bridge.camera_recovered.connect(self._tray._on_camera_recovered_gui)

        # ── Initialize Update Checker ──────────────────────────────────────
        from gesture_controller.core.updater import UpdateCheckerThread

        self._updater_thread = UpdateCheckerThread(current_version="0.1.0", parent=self._app)
        self._updater_thread.update_available.connect(self._on_update_available)
        self._updater_thread.start()

        # ── Initialize Integration API Server & Voice Command Listener ──────
        from gesture_controller.core.integration_server import IntegrationServer
        from gesture_controller.core.voice_listener import VoiceCommandListener

        self._integration_server = IntegrationServer(self._event_bus)
        try:
            self._integration_server.start()
        except Exception as e:
            logger.error("Failed to start Integration API Server", error=str(e))

        self._voice_listener = VoiceCommandListener(self._event_bus)
        self._voice_listener.start()

        self._tray.message_clicked.connect(self._on_tray_message_clicked)

        # ── Polling timer: Engine -> GUI bridge ────────────────────────────
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_engine)
        self._poll_timer.start(16)  # ~60 FPS GUI update rate

        # ── Status tooltip timer (lower frequency) ─────────────────────────
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_tray_status)
        self._status_timer.start(500)  # Every 500ms

        # ── Show GUI ───────────────────────────────────────────────────────
        self._tray.show()
        if self._config.get("hud.enabled", True):
            self._overlay.show()

        logger.info("Gesture Controller App started")

    # ── Polling callbacks ──────────────────────────────────────────────────

    def _poll_engine(self) -> None:
        """Bridge: push latest hand data from engine to the overlay."""
        hands = self._engine.get_current_hands()
        fsm_states = self._engine.get_fsm_states() if hands else None
        self._overlay.set_hand_data(hands, fsm_states)

    def _update_tray_status(self) -> None:
        """Update tray tooltip with live stats."""
        self._tray.update_status(self._engine.get_fps(), self._engine.get_gesture_count())

    def _on_gesture_triggered_gui(self, gesture_name: str, action: str) -> None:
        """Show action confirmation on HUD overlay. Runs on GUI thread."""
        self._overlay.show_action_feedback(gesture_name, action)

    def _on_config_changed(self, new_config: dict) -> None:
        """Propagate config changes to engine and overlay."""
        self._event_bus.publish("config_changed", new_config)
        # Refresh overlay config reference
        self._overlay._config = new_config
        # Toggle overlay visibility based on hud.enabled
        hud_enabled = new_config.get("hud", {}).get("enabled", True)
        if hud_enabled:
            self._overlay.show()
        else:
            self._overlay.hide()

    def _show_settings(self) -> None:
        """Show the settings dialog (non-modal)."""
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def _export_diagnostics(self) -> None:
        """Export system logs, user configurations, custom gesture templates, and plugins to a ZIP archive."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        from gesture_controller.core.compliance import export_data

        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Diagnostics Archive",
            "gesture_controller_diagnostics.zip",
            "Zip Archives (*.zip)",
        )
        if not save_path:
            return

        try:
            export_data(Path(save_path))
            QMessageBox.information(
                None, "Diagnostics Exported", f"Successfully exported diagnostics to:\n{save_path}"
            )
            logger.info("Diagnostics archive successfully exported", path=save_path)
        except Exception as e:
            logger.exception("Failed to export diagnostics", error=str(e))
            QMessageBox.critical(
                None, "Export Failed", f"Failed to export diagnostics archive:\n{str(e)}"
            )

    def _on_update_available(self, latest_version: str, download_url: str) -> None:
        """Show tray balloon notification when a newer version is available (S4-8)."""
        logger.info("Application update available", version=latest_version, url=download_url)
        self._download_url = download_url
        self._tray.show_message(
            "Update Available",
            f"A newer version (v{latest_version}) of Maestro is available. Click here to download.",
        )

    def _on_tray_message_clicked(self) -> None:
        """Open web browser to update release page when balloon message is clicked."""
        if hasattr(self, "_download_url") and self._download_url:
            import webbrowser

            webbrowser.open(self._download_url)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def _shutdown(self) -> None:
        """Gracefully shut down engine, API services, and Qt event loop."""
        logger.info("Shutting down Gesture Controller App")
        self._poll_timer.stop()
        self._status_timer.stop()

        # Stop API Services (Phases 15 & 17)
        if hasattr(self, "_integration_server"):
            self._integration_server.stop()
        if hasattr(self, "_voice_listener"):
            self._voice_listener.stop()

        # Stop and join update checker thread if running (S4-8)
        if hasattr(self, "_updater_thread"):
            self._updater_thread.quit()
            if not self._updater_thread.wait(1000):
                self._updater_thread.terminate()
                self._updater_thread.wait(500)

        self._engine.shutdown()
        self._overlay.hide()
        self._tray.hide()
        self._app.quit()

    def run(self) -> int:
        """Start the Qt event loop. Blocks until quit."""
        # First-run onboarding check
        from gesture_controller.gui.onboarding import is_onboarded, OnboardingWizard

        if not is_onboarded():
            wizard = OnboardingWizard()
            if not wizard.exec():
                return 0

        # Start engine processing thread
        self._engine.start()
        # Allow Ctrl+C in terminal to trigger shutdown
        signal.signal(signal.SIGINT, lambda *_: self._shutdown())
        return self._app.exec()


def main() -> None:
    """CLI entry point for the gesture controller desktop application."""
    import argparse

    parser = argparse.ArgumentParser(description="Gesture Controller Desktop App")
    parser.add_argument("--config", type=str, default=None, help="Path to custom config YAML")
    args = parser.parse_args()

    app = GestureControllerApp(config_path=args.config)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
