import time
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class OverlayHUD(QWidget):
    """Translucent, click-through overlay showing gesture tracking visualization."""

    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput  # Click-through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # Windows-specific: ensure click-through mouse events propagate
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._config = config
        self._hands: list = []  # List of Hand dataclasses
        self._active_gesture: str | None = None
        self._action_feedback: str | None = None
        self._action_feedback_time: float = 0
        self._fsm_progress: float = 0.0

        # Monitor changes tracking (S4-7)
        from PyQt6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app:
            app.screenAdded.connect(lambda _: self.reposition())
            app.screenRemoved.connect(lambda _: self.reposition())
            app.primaryScreenChanged.connect(lambda _: self.reposition())

        # Recalculate size to cover primary monitor
        self.reposition()

    def reposition(self) -> None:
        """Cover screen geometries based on monitor selection config (S4-7)."""
        from PyQt6.QtGui import QGuiApplication

        screen_cfg = self._config.get("hud", {}).get("multi_monitor_mode", "primary")
        primary = QGuiApplication.primaryScreen()
        if primary:
            if screen_cfg == "all":
                self.setGeometry(primary.virtualGeometry())
            elif screen_cfg == "select":
                screen_idx = self._config.get("hud", {}).get("target_screen_index", 0)
                screens = QGuiApplication.screens()
                if 0 <= screen_idx < len(screens):
                    self.setGeometry(screens[screen_idx].geometry())
                else:
                    self.setGeometry(primary.geometry())
            else:
                self.setGeometry(primary.geometry())

    def set_hand_data(self, hands: list, fsm_states: dict | None = None) -> None:
        """Called from engine thread to update landmarks and FSM tracking ring state."""
        self._hands = hands
        self._active_gesture = None
        self._fsm_progress = 0.0

        if fsm_states:
            for name, (state, progress) in fsm_states.items():
                if state not in ("Idle",):
                    self._active_gesture = name
                    self._fsm_progress = progress
                    break
        self.update()

    def show_action_feedback(self, gesture_name: str, action: str) -> None:
        """Flash action name on screen for visual confirmation."""
        self._action_feedback = f"{gesture_name} -> {action}"
        self._action_feedback_time = time.monotonic()

        duration = self._config.get("hud", {}).get("confirmation_duration_ms", 800)
        QTimer.singleShot(duration, self._clear_feedback)
        self.update()

    def _clear_feedback(self) -> None:
        self._action_feedback = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        hud_enabled = self._config.get("hud", {}).get("enabled", True)
        if not hud_enabled:
            return

        opacity = self._config.get("hud", {}).get("opacity", 0.8)
        painter.setOpacity(opacity)

        # Draw hand skeletons
        for hand in self._hands:
            self._draw_hand_skeleton(painter, hand.landmarks)

        # Draw action confirmation text
        if self._action_feedback:
            self._draw_action_text(painter, self._action_feedback)

        # Draw active gesture progress ring
        if self._active_gesture:
            self._draw_progress_ring(painter, self._active_gesture)

    def _draw_hand_skeleton(self, painter: QPainter, landmarks) -> None:
        """Draw bone lines and joint circles overlaying the hand."""
        if not self._config.get("hud", {}).get("show_tracking_points", True):
            return

        w, h = self.width(), self.height()
        painter.setPen(QPen(QColor(0, 255, 180, 220), 2))
        painter.setBrush(QBrush(QColor(0, 255, 180, 160)))

        from gesture_controller.models.hand_topology import CONNECTIONS

        # Convert normalized coordinates [0, 1] to pixel space
        points = []
        for lm in landmarks:
            px = int(lm.x * w)
            py = int(lm.y * h)
            points.append(QPointF(px, py))

        # Draw connections
        for start, end in CONNECTIONS:
            if start < len(points) and end < len(points):
                painter.drawLine(points[start], points[end])

        # Draw joints
        for pt in points:
            painter.drawEllipse(pt, 4, 4)

    def _draw_action_text(self, painter: QPainter, text: str) -> None:
        """Show dynamic text feedback at bottom center."""
        painter.setOpacity(0.95)
        painter.setPen(QColor("#00ff88"))
        font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font)

        w, h = self.width(), self.height()
        # Draw translucent capsule background
        bg_rect = QRectF(w / 2 - 250, h - 140, 500, 60)
        painter.setBrush(QBrush(QColor(15, 15, 15, 180)))
        painter.setPen(QPen(QColor(0, 255, 136, 120), 1.5))
        painter.drawRoundedRect(bg_rect, 10, 10)

        # Draw text inside capsule
        painter.setPen(QColor("#ffffff"))
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_progress_ring(self, painter: QPainter, gesture_name: str) -> None:
        """Draw a progress ring in the bottom-right corner."""
        if not self._config.get("hud", {}).get("show_progress_ring", True):
            return

        from gesture_controller.gui.theme import detect_reduced_motion

        reduced_motion = (
            self._config.get("a11y", {}).get("reduced_motion", False) or detect_reduced_motion()
        )

        w, h = self.width(), self.height()
        center_x = w - 100
        center_y = h - 100
        radius = 35

        # Background circular track
        painter.setPen(QPen(QColor(50, 50, 50, 180), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        # Foreground progress arc
        painter.setPen(QPen(QColor(0, 255, 136, 230), 5))
        rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        # Angle parameter is in 1/16th of a degree
        progress = (
            1.0 if self._fsm_progress >= 0.95 else 0.0 if reduced_motion else self._fsm_progress
        )
        angle_span = int(-360 * progress * 16)
        painter.drawArc(rect, 90 * 16, angle_span)

        # Active gesture label below ring
        painter.setPen(QColor(255, 255, 255, 200))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(center_x - 70, center_y + radius + 5, 140, 20),
            Qt.AlignmentFlag.AlignCenter,
            gesture_name,
        )
