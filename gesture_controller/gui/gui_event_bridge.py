"""Marshals engine-thread EventBus events to the GUI thread via Qt signals.

HARD RULE: no QWidget/QObject subclass may call event_bus.subscribe directly.
All engine-thread → GUI-thread communication goes through this bridge.
"""
from PyQt6.QtCore import QObject, pyqtSignal

class GuiEventBridge(QObject):
    gesture_triggered = pyqtSignal(str, str)   # gesture_name, action
    camera_disconnected = pyqtSignal()
    camera_recovered = pyqtSignal()
    plugin_reloaded = pyqtSignal(str)          # plugin_name

    def __init__(self, event_bus, parent=None) -> None:
        super().__init__(parent)
        event_bus.subscribe("gesture_triggered", self._on_gesture)
        event_bus.subscribe("camera_disconnected", self._on_cam_disc)
        event_bus.subscribe("camera_recovered", self._on_cam_rec)
        event_bus.subscribe("plugin_reloaded", self._on_plugin_reload)

    # These run on the ENGINE thread — emit signals (thread-safe)
    def _on_gesture(self, event) -> None:
        if hasattr(event, "gesture_name") and hasattr(event, "action"):
            self.gesture_triggered.emit(event.gesture_name, event.action)

    def _on_cam_disc(self, _event) -> None:
        self.camera_disconnected.emit()

    def _on_cam_rec(self, _event) -> None:
        self.camera_recovered.emit()

    def _on_plugin_reload(self, event) -> None:
        if isinstance(event, str):
            name = event
        else:
            name = getattr(event, "plugin_name", "")
        self.plugin_reloaded.emit(name)
