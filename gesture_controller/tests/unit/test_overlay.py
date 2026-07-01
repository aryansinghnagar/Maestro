import sys
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gesture_controller.gui.overlay import OverlayHUD
from gesture_controller.models.data_types import Hand, Landmark3D


def test_overlay_hud_initialization(qapp: QApplication) -> None:
    config = {
        "hud": {
            "enabled": True,
            "opacity": 0.5,
            "show_tracking_points": True,
            "show_progress_ring": True,
            "confirmation_duration_ms": 500
        }
    }
    overlay = OverlayHUD(config)
    
    # Confirm correct translucent / frameless window flags
    flags = overlay.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.WindowTransparentForInput
    
    assert overlay._config == config
    assert overlay._action_feedback is None

    # Clean up to prevent segfaults
    overlay.deleteLater()
    qapp.processEvents()

def test_overlay_hud_feedback_timer(qapp: QApplication) -> None:
    config = {"hud": {"confirmation_duration_ms": 100}}
    overlay = OverlayHUD(config)
    
    # Flash feedback
    overlay.show_action_feedback("Wave", "KeyPress:Space")
    assert overlay._action_feedback == "Wave -> KeyPress:Space"
    
    # Let event loop process timer
    qapp.processEvents()
    import time
    time.sleep(0.15)
    qapp.processEvents()
    
    # Text should be cleared
    assert overlay._action_feedback is None

    # Clean up to prevent segfaults
    overlay.deleteLater()
    qapp.processEvents()

def test_overlay_hud_set_hand_data(qapp: QApplication) -> None:
    config = {"hud": {}}
    overlay = OverlayHUD(config)
    
    # Mock hand structure
    mock_hand = Hand(
        landmarks=tuple(Landmark3D(x=0.0, y=0.0, z=0.0) for _ in range(21)),
        handedness="Right",
        confidence=1.0
    )
    
    fsm_states = {"Swipe": ("SwipeRightPose", 0.75)}
    overlay.set_hand_data([mock_hand], fsm_states)
    
    assert len(overlay._hands) == 1
    assert overlay._active_gesture == "Swipe"
    assert overlay._fsm_progress == 0.75

    # Clean up to prevent segfaults
    overlay.deleteLater()
    qapp.processEvents()
