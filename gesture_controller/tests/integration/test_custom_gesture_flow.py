import sys
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication

from gesture_controller.gui.gesture_recorder import GestureRecorder
from gesture_controller.models.dtw_matcher import CustomGestureMatcher
from gesture_controller.models.data_types import Hand, Landmark3D


def test_custom_gesture_flow_integration(qapp: QApplication, tmp_path: Path) -> None:
    # 1. Setup mock hand landmark source
    landmarks = tuple(Landmark3D(x=float(i)/21.0, y=0.0, z=0.0) for i in range(21))
    mock_hand = Hand(landmarks=landmarks, handedness="Right", confidence=1.0)
    mock_callback = MagicMock(return_value=mock_hand)
    
    # 2. Record Custom Gesture using Dialog routines
    recorder = GestureRecorder(landmark_callback=mock_callback)
    recorder._name_input.setText("CustomWave")
    recorder._action_input.setText("KeyPress:VolumeUp")
    
    # Simulate 3 successful recordings (each capturing 10 frames)
    for _ in range(3):
        recorder._on_record_clicked()
        # Fast-forward countdown
        recorder._countdown = 1
        recorder._countdown_tick()
        # Capture 10 frames
        for _ in range(10):
            recorder._capture_frame()
        recorder._stop_recording()
        
    assert len(recorder._recordings) == 3
    
    # 3. Save recorded template to temporary templates directory
    saved_template = None
    def on_complete(data: dict) -> None:
        nonlocal saved_template
        saved_template = data
        # Write to JSON
        dest = tmp_path / f"{data['name']}.json"
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
    recorder.recording_complete.connect(on_complete)
    with patch.object(recorder, "accept"):
        recorder._on_save()
        
    assert saved_template is not None
    assert (tmp_path / "CustomWave.json").exists()
    
    # 4. Load template using CustomGestureMatcher
    matcher = CustomGestureMatcher()
    matcher._template_dir = tmp_path
    matcher.load_templates(tmp_path)
    
    assert "CustomWave" in matcher._templates
    
    # 5. Push matching frames to rolling buffer and match
    # Since we recorded and averaged flat line sequences, the template is a flat line.
    # Feeding the exact same mock hand landmarks should produce a high-confidence match!
    for _ in range(60):
        matcher.update_buffer(mock_hand)
        
    event = matcher.match()
    assert event is not None
    assert event.gesture_name == "CustomWave"
    assert event.action == "KeyPress:VolumeUp"
    assert event.confidence > 0.8
