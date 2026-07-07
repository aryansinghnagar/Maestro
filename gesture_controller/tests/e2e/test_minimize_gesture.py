"""E2E test verifying the Minimize gesture end-to-end pipeline.
Feeds a simulated downward finger movement and checks OS action trigger.
"""

import sys
import time
import pytest
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.real_mediapipe]
from unittest.mock import MagicMock, patch
import numpy as np

from gesture_controller.core.engine import GestureEngine
from gesture_controller.models.data_types import Hand, Landmark3D, FeatureVector, GestureEvent
from gesture_controller.os_integration.base_controller import BaseController


class MockOSController(BaseController):
    """Mock OS controller to capture command executions without performing them."""

    def __init__(self) -> None:
        self.minimize_called = False

    def is_supported(self) -> bool:
        return True

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        pass

    def key_release(self, key: str) -> None:
        pass

    def key_combo(self, keys: list[str]) -> None:
        pass

    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        pass

    def mouse_double_click(
        self, button: str = "left", x: int | None = None, y: int | None = None
    ) -> None:
        pass

    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        pass

    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        pass

    def get_foreground_app(self) -> str:
        return "Not Chrome"

    def minimize_active_window(self) -> None:
        self.minimize_called = True

    def media_next(self) -> None:
        pass

    def media_play_pause(self) -> None:
        pass

    def media_previous(self) -> None:
        pass

    def media_volume_down(self) -> None:
        pass

    def media_volume_up(self) -> None:
        pass

    def show_desktop(self) -> None:
        pass

    def switch_window(self, direction: str = "next") -> None:
        pass


@pytest.mark.e2e
def test_minimize_gesture_e2e() -> None:
    """Simulate a sequence of FeatureVectors representing Minimize gesture sequence."""

    # We will mock compute_features to yield a sequence of FeatureVectors:
    # 0.00s: Index Extended (Idle -> PointingUp)
    # 0.06s: Index Extended (stays in PointingUp, duration = 60ms)
    # 0.12s: Index Extended (stays in PointingUp, duration = 120ms)
    # 0.18s: Index Extended (stays in PointingUp, duration = 180ms)
    # 0.24s: Index Extended (stays in PointingUp, duration = 240ms >= 200ms min_duration)
    # 0.30s: Index moving down fast (PointingUp -> RapidDownFlick)
    # 0.36s: Index tip has moved down significantly (RapidDownFlick -> Trigger)

    simulated_features = []

    def make_fv(t: float, index_ext: bool, vel_y: float, tip_y: float) -> FeatureVector:
        return FeatureVector(
            thumb_extended=False,
            index_extended=index_ext,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
            thumb_curl=0.0,
            index_curl=0.0,
            middle_curl=0.9,
            ring_curl=0.9,
            pinky_curl=0.9,
            hand_openness=0.2,
            pinch_distance=0.5,
            palm_normal=np.array([0.0, 0.0, 1.0]),
            palm_center=np.array([0.5, 0.5, 0.5]),
            index_tip=np.array([0.5, tip_y, 0.0]),  # Dynamic tip y position
            palm_velocity=np.array([0.0, 0.0, 0.0]),
            palm_velocity_magnitude=0.05,
            palm_acceleration=np.array([0.0, 0.0, 0.0]),
            index_tip_velocity=np.array([0.0, vel_y, 0.0]),
            handedness="Right",
            confidence=0.95,
            timestamp=t,
            frame_number=int(t * 10),
            index_tip_delta_y=0.0,
            palm_center_delta_x=0.0,
            palm_center_delta_y=0.0,
            palm_delta_y=0.0,
        )

    # Frame 0 to 4: Steady PointingUp (tip y = 0.3)
    for i in range(5):
        simulated_features.append(make_fv(0.06 * i, True, 0.0, 0.3))
    # Frame 5: Down flick velocity > 0.5, tip y = 0.4 (RapidDownFlick state entered here)
    simulated_features.append(make_fv(0.30, True, 0.6, 0.4))
    # Frame 6: Down flick tip y = 0.6 (this gives index_tip_delta_y = 0.6 - 0.4 = 0.2 > 0.15)
    simulated_features.append(make_fv(0.36, True, 0.0, 0.6))

    # 2. Mock camera process startup & landmark extraction inside engine
    with (
        patch("gesture_controller.core.engine.start_camera_process"),
        patch("gesture_controller.core.engine.shared_memory.SharedMemory") as MockSHM,
    ):

        shm_instance = MagicMock()
        shm_instance.name = "mock_shm"
        MockSHM.return_value = shm_instance

        # Instantiate the engine
        engine = GestureEngine()
        engine._frame_ready_event.wait = MagicMock(return_value=True)

        # Replace OS controller with our mock
        mock_controller = MockOSController()
        engine._controller = mock_controller
        engine._dispatcher._controller = mock_controller

        # Mock extractor to return a dummy hand to keep the engine loop going
        dummy_landmarks = tuple(Landmark3D(x=0.5, y=0.5, z=0.0) for _ in range(21))
        dummy_hand = Hand(landmarks=dummy_landmarks, handedness="Right", confidence=0.95)
        engine._extractor.extract = MagicMock(return_value=[dummy_hand])

        # Mock compute_features to yield our simulated feature sequence step by step
        feature_idx = 0

        def mock_compute_features(*args, **kwargs):
            nonlocal feature_idx
            if feature_idx < len(simulated_features):
                fv = simulated_features[feature_idx]
                feature_idx += 1
                return fv
            else:
                # Return standard idle feature vector after sequence completes
                return make_fv(0.36 + 0.06 * (feature_idx - 6), False, 0.0, 0.3)

        # Patch compute_features in the engine execution context
        with patch(
            "gesture_controller.core.engine.compute_features", side_effect=mock_compute_features
        ):
            # Start engine processing thread
            engine.start()

            # Wait up to 2 seconds for FSM evaluation to complete and trigger minimize
            start_time = time.time()
            while time.time() - start_time < 2.0:
                if mock_controller.minimize_called:
                    break
                time.sleep(0.05)

            # Clean up
            engine.shutdown()

        # Assert that the OS-level minimize command was successfully triggered
        assert mock_controller.minimize_called is True
