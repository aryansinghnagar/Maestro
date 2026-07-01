import sys
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMessageBox

from gesture_controller.gui.gesture_recorder import GestureRecorder
from gesture_controller.models.data_types import Hand, Landmark3D


def test_recorder_dialog_initialization(qapp: QApplication) -> None:
    recorder = GestureRecorder(landmark_callback=None)
    assert recorder.windowTitle() == "Record Custom Gesture"
    assert recorder._progress_label.text() == "Recordings: 0 / 3"
    assert recorder._threshold_slider.value() == 15

    # Clean up to prevent segfaults
    recorder.deleteLater()
    qapp.processEvents()

def test_recorder_save_warning_insufficient_recordings(qapp: QApplication) -> None:
    recorder = GestureRecorder(landmark_callback=None)
    
    # Attempt to save directly
    with patch.object(QMessageBox, "warning") as mock_warning:
        recorder._on_save()
        mock_warning.assert_called_once()
        assert "Need 3 recordings" in mock_warning.call_args[0][2]

    # Clean up to prevent segfaults
    recorder.deleteLater()
    qapp.processEvents()

def test_recorder_countdown_and_capture(qapp: QApplication) -> None:
    # Setup mock hand data for landmark callback
    mock_hand = Hand(
        landmarks=tuple(Landmark3D(x=float(i)/21.0, y=float(i)/21.0, z=0.0) for i in range(21)),
        handedness="Right",
        confidence=0.9
    )
    mock_callback = MagicMock(return_value=mock_hand)
    
    recorder = GestureRecorder(landmark_callback=mock_callback)
    
    # 1. Trigger countdown
    recorder._on_record_clicked()
    assert recorder._timer is not None
    assert recorder._timer.isActive()
    
    # 2. Complete countdown ticks manually
    recorder._countdown = 1
    recorder._countdown_tick()
    
    # Timer should stop and recording start timer should begin
    assert not recorder._timer.isActive()
    assert recorder._is_recording is True
    assert recorder._record_timer is not None
    assert recorder._record_timer.isActive()
    
    # 3. Capture frames
    for _ in range(10):
        recorder._capture_frame()
    assert mock_callback.called
    assert len(recorder._current_recording) == 10
    
    # 4. Stop recording
    recorder._stop_recording()
    assert recorder._is_recording is False
    assert recorder._record_timer is None
    assert len(recorder._recordings) == 1
    assert recorder._progress_label.text() == "Recordings: 1 / 3"

    # Clean up to prevent segfaults
    recorder.deleteLater()
    qapp.processEvents()

def test_recorder_save_valid_template(qapp: QApplication) -> None:
    recorder = GestureRecorder(landmark_callback=None)
    recorder._name_input.setText("Wave")
    recorder._action_input.setText("KeyPress:W")
    
    # Fabricate 3 mock recording examples (each containing 15 frames of flat shape data)
    mock_frame = np.zeros(63, dtype=np.float64)
    recorder._recordings = [
        [mock_frame] * 15,
        [mock_frame] * 15,
        [mock_frame] * 15
    ]
    
    # Setup listener for signal
    signal_data = []
    recorder.recording_complete.connect(lambda d: signal_data.append(d))
    
    # Trigger save
    with patch.object(recorder, "accept") as mock_accept:
        recorder._on_save()
        mock_accept.assert_called_once()
        
    assert len(signal_data) == 1
    data = signal_data[0]
    assert data["name"] == "Wave"
    assert data["action"] == "KeyPress:W"
    assert len(data["template"]) == 60  # Interpolated template frames
    assert "recorded_at" in data

    # Clean up to prevent segfaults
    recorder.deleteLater()
    qapp.processEvents()
