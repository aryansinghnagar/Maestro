"""Tremor calibration wizard dialog."""

from __future__ import annotations

import time
import numpy as np
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QMessageBox


class TremorCalibrator(QDialog):
    """Calibrate tremor compensation by recording 10 seconds of hand data."""

    DURATION_SECONDS = (
        10  # 10s is much better for user experience while still sufficient for 30Hz camera
    )

    def __init__(self, config_manager, landmark_callback, parent=None) -> None:
        super().__init__(parent)
        self._config = config_manager
        self._landmark_callback = landmark_callback
        self._samples: list[tuple[float, float]] = []
        self._timer = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Tremor Calibration")
        self.setMinimumSize(400, 250)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.label = QLabel(
            "Hold your hand steady in front of the camera.\n"
            "This wizard will measure your natural tremor frequency and amplitude."
        )
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setAccessibleName("Tremor calibration instructions")
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, self.DURATION_SECONDS * 10)  # 100ms ticks
        self.progress.setValue(0)
        self.progress.setAccessibleName("Calibration progress bar")
        layout.addWidget(self.progress)

        self.start_button = QPushButton("Start Calibration")
        self.start_button.clicked.connect(self._start)
        self.start_button.setAccessibleName("Start Calibration Button")
        self.start_button.setAccessibleDescription(
            "Start recording hand positioning to analyze tremors."
        )
        layout.addWidget(self.start_button)

    def _start(self) -> None:
        self.start_button.setEnabled(False)
        self._samples.clear()
        self._start_time = time.monotonic()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(100)  # 10 FPS / 100ms interval

    def _update(self) -> None:
        elapsed = time.monotonic() - self._start_time
        if elapsed >= self.DURATION_SECONDS:
            self._timer.stop()
            self._finish()
            return

        self.progress.setValue(int(elapsed * 10))

        # Retrieve wrist coordinate (landmark index 0)
        hand = self._landmark_callback()
        if hand is not None and hasattr(hand, "landmarks"):
            try:
                # hand.landmarks is a (21, 3) numpy array or list
                wrist_x = hand.landmarks[0][0]
                self._samples.append((time.monotonic(), float(wrist_x)))
            except Exception:
                pass

    def _finish(self) -> None:
        if len(self._samples) < 15:
            self.label.setText(
                "No hand coordinates detected. Please hold your hand in front of the camera and try again."
            )
            self.start_button.setEnabled(True)
            self.start_button.setText("Retry")
            return

        times = np.array([t for t, _ in self._samples])
        xs = np.array([x for _, x in self._samples])
        dt = np.mean(np.diff(times))

        if dt <= 0:
            self.label.setText("Timing error. Please try again.")
            self.start_button.setEnabled(True)
            self.start_button.setText("Retry")
            return

        # Perform FFT to determine peak tremor frequency
        x_detrend = xs - np.mean(xs)
        fft = np.fft.rfft(x_detrend)
        freqs = np.fft.rfftfreq(len(xs), d=dt)
        magnitudes = np.abs(fft)

        # Look for peak in the 4-12 Hz tremor band
        tremor_mask = (freqs >= 4.0) & (freqs <= 12.0)
        if tremor_mask.any():
            peak_idx = magnitudes[tremor_mask].argmax()
            tremor_freq = float(freqs[tremor_mask][peak_idx])
            tremor_amplitude = float(magnitudes[tremor_mask][peak_idx])
        else:
            tremor_freq = 0.0
            tremor_amplitude = 0.0

        # Update the configuration based on findings
        if tremor_amplitude > 0.001:  # Significant tremor amplitude
            self._config.set("filtering.tremor.enabled", True)
            self._config.set("filtering.tremor.min_freq", float(max(1.0, tremor_freq - 2.0)))
            self._config.set("filtering.tremor.max_freq", float(tremor_freq + 2.0))
            self.label.setText(
                f"Calibration Complete!\n"
                f"Detected tremor frequency: {tremor_freq:.1f} Hz.\n"
                f"Tremor filter enabled with range {max(1.0, tremor_freq - 2.0):.1f} - {tremor_freq + 2.0:.1f} Hz."
            )
        else:
            self._config.set("filtering.tremor.enabled", False)
            self.label.setText(
                "Calibration Complete!\n"
                "No significant hand tremors detected. Tremor compensation remains disabled."
            )

        self.start_button.setEnabled(True)
        self.start_button.setText("Close")
        self.start_button.clicked.disconnect()
        self.start_button.clicked.connect(self.accept)
