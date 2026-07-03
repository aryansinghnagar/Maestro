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


class GestureControllerApp:
    """Top-level application coordinator wiring Engine, Tray, Overlay, and Settings."""

    def __init__(self, config_path: str | None = None) -> None:
        # Enable high-DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)  # Tray keeps app alive
        self._app.setApplicationName("Gesture Controller")

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

        template_dir = Path(self._engine._custom_matcher._template_dir) if hasattr(self._engine._custom_matcher, "_template_dir") else None
        self._settings = SettingsWindow(
            self._config,
            landmark_callback=_get_current_hand,
            template_dir=template_dir,
            reload_callback=self._engine._custom_matcher.load_templates,
            parent=None
        )

        # ── Signal wiring ──────────────────────────────────────────────────
        # Tray -> Engine pause
        self._tray.pause_toggled.connect(self._engine.set_paused)
        # Tray -> Settings window
        self._tray.settings_requested.connect(self._show_settings)
        # Tray -> Quit
        self._tray.quit_requested.connect(self._shutdown)
        # Settings -> Config reload
        self._settings.config_changed.connect(self._on_config_changed)
        
        # Bridge engine-thread events to GUI thread via Qt signals
        self._bridge = GuiEventBridge(self._event_bus, parent=self._app)
        self._bridge.gesture_triggered.connect(self._on_gesture_triggered_gui)
        self._bridge.camera_disconnected.connect(self._tray._on_camera_disconnected_gui)
        self._bridge.camera_recovered.connect(self._tray._on_camera_recovered_gui)

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
        self._tray.update_status(
            self._engine.get_fps(),
            self._engine.get_gesture_count()
        )

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

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def _shutdown(self) -> None:
        """Gracefully shut down engine and Qt event loop."""
        logger.info("Shutting down Gesture Controller App")
        self._poll_timer.stop()
        self._status_timer.stop()
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
