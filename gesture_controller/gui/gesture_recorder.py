import json
from datetime import datetime, timezone
import numpy as np
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QMessageBox,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor

from gesture_controller.models.dtw_matcher import to_hand_frame, normalize_sequence
from gesture_controller.models.data_types import Landmark3D


class GestureCanvas(QWidget):
    """Custom canvas showing live hand skeleton feedback."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.landmarks = []
        self.setMinimumHeight(200)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 4px;")

    def update_hand(self, landmarks) -> None:
        self.landmarks = landmarks
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.landmarks:
            painter.setPen(QPen(QColor("#777"), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Hand Detected")
            return

        w, h = self.width(), self.height()
        xs = [l.x for l in self.landmarks]
        ys = [l.y for l in self.landmarks]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = max_x - min_x
        span_y = max_y - min_y
        scale = min((w - 40) / max(span_x, 1e-5), (h - 40) / max(span_y, 1e-5))

        offset_x = (w - span_x * scale) / 2.0 - min_x * scale
        offset_y = (h - span_y * scale) / 2.0 - min_y * scale

        points = []
        for l in self.landmarks:
            px = l.x * scale + offset_x
            py = l.y * scale + offset_y
            points.append(QPointF(px, py))

        # Draw skeleton connections
        painter.setPen(QPen(QColor("#00ffcc"), 2))
        from gesture_controller.models.hand_topology import CONNECTIONS as connections
        for start, end in connections:
            if start < len(points) and end < len(points):
                painter.drawLine(points[start], points[end])

        # Draw joints on top
        painter.setPen(QPen(QColor("#ffffff"), 6))
        for p in points:
            painter.drawPoint(p)


class GestureRecorder(QDialog):
    """Dialog for recording custom gestures."""

    recording_complete = pyqtSignal(dict)  # Emits template data

    def __init__(self, parent=None, landmark_callback=None) -> None:
        super().__init__(parent)
        self._landmark_callback = landmark_callback  # Called to get current Hand from engine
        self._recordings: list[list[np.ndarray]] = []
        self._is_recording = False
        self._current_recording: list[np.ndarray] = []
        self._required_examples = 3
        self._frames_per_example = 60
        self._fps = 30
        self._countdown = 0
        self._timer: QTimer | None = None
        self._record_timer: QTimer | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Record Custom Gesture")
        self.setMinimumSize(500, 450)
        layout = QVBoxLayout(self)

        # Name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Gesture Name:"))
        self._name_input = QLineEdit()
        name_layout.addWidget(self._name_input)
        layout.addLayout(name_layout)

        # Action input
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel("Action:"))
        self._action_input = QLineEdit()
        self._action_input.setPlaceholderText("e.g. KeyPress:Space")
        action_layout.addWidget(self._action_input)
        layout.addLayout(action_layout)

        # Recording progress
        self._progress_label = QLabel("Recordings: 0 / 3")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_label)

        # Visual feedback area
        self._canvas = GestureCanvas()
        layout.addWidget(self._canvas)

        # Record button
        self._record_btn = QPushButton("Start Recording (3s countdown)")
        self._record_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self._record_btn)

        # Threshold slider
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("DTW Threshold:"))
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(5, 50)
        self._threshold_slider.setValue(15)
        self._threshold_label = QLabel("0.15")
        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_label.setText(f"{v/100:.2f}")
        )
        thresh_layout.addWidget(self._threshold_slider)
        thresh_layout.addWidget(self._threshold_label)
        layout.addLayout(thresh_layout)

        # Save / Cancel
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Gesture")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_record_clicked(self) -> None:
        """Start a 3-second countdown, then record 2 seconds of landmarks."""
        self._record_btn.setEnabled(False)
        self._record_btn.setText("Get ready...")

        # Countdown timer
        self._countdown = 3
        self._timer = QTimer()
        self._timer.timeout.connect(self._countdown_tick)
        self._timer.start(1000)

    def _countdown_tick(self) -> None:
        self._countdown -= 1
        if self._countdown > 0:
            self._record_btn.setText(f"Recording in {self._countdown}...")
        else:
            self._timer.stop()
            self._start_recording()

    def _start_recording(self) -> None:
        self._is_recording = True
        self._current_recording = []
        self._record_btn.setText("Recording... (2 seconds)")
        self._record_timer = QTimer()
        self._record_timer.timeout.connect(self._capture_frame)
        self._record_timer.start(int(1000 / self._fps))

        # Auto-stop after 2 seconds
        QTimer.singleShot(2000, self._stop_recording)

    def _capture_frame(self) -> None:
        if not self._landmark_callback:
            return
        hand = self._landmark_callback()  # Get current Hand from engine
        if hand:
            landmarks = to_hand_frame(hand.landmarks, hand.handedness)
            flat = np.array(
                [l.x for l in landmarks] + [l.y for l in landmarks] + [l.z for l in landmarks],
                dtype=np.float64,
            )
            self._current_recording.append(flat)
            self._canvas.update_hand(landmarks)

    def _stop_recording(self) -> None:
        self._is_recording = False
        if self._record_timer:
            self._record_timer.stop()
            self._record_timer = None

        if len(self._current_recording) >= 10:  # Minimum viable recording
            self._recordings.append(self._current_recording)
            self._progress_label.setText(
                f"Recordings: {len(self._recordings)} / {self._required_examples}"
            )

        self._record_btn.setEnabled(len(self._recordings) < self._required_examples)
        if len(self._recordings) < self._required_examples:
            self._record_btn.setText(
                f"Record Another ({self._required_examples - len(self._recordings)} remaining)"
            )
        else:
            self._record_btn.setText("Recording Complete!")

    def _on_save(self) -> None:
        if len(self._recordings) < self._required_examples:
            QMessageBox.warning(
                self,
                "Not Enough Recordings",
                f"Need {self._required_examples} recordings, have {len(self._recordings)}",
            )
            return

        name = self._name_input.text().strip()
        action = self._action_input.text().strip()
        if not name or not action:
            QMessageBox.warning(self, "Missing Info", "Name and action are required")
            return

        # Normalize and average the recordings into a template of exactly 60 frames
        normalized = [normalize_sequence(rec, self._frames_per_example) for rec in self._recordings]
        template = np.mean(normalized, axis=0).tolist()

        threshold = self._threshold_slider.value() / 100.0

        template_data = {
            "version": "1.0",
            "name": name,
            "action": action,
            "hand": "Right",
            "threshold": threshold,
            "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "examples": [n.tolist() for n in normalized],
            "template": template,
        }

        self.recording_complete.emit(template_data)
        self.accept()
