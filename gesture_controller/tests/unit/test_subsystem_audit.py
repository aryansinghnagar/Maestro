import threading
import time
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from gesture_controller.vision.backends.base_backend import BaseONNXBackend
from gesture_controller.vision.palm_detector import PalmDetector
from gesture_controller.vision.one_euro_filter import OneEuroFilter
from gesture_controller.vision.double_buffer import DoubleFrameBuffer, HEADER_SIZE
from gesture_controller.models.dtw_matcher import (
    fast_dtw_distance,
    normalize_sequence,
    DTW_BUFFER_FRAMES,
    DTW_FEATURE_DIMS,
)
from gesture_controller.core.voice_listener import VoiceCommandRegistry, VoiceCommandListener
from gesture_controller.models.data_types import Hand, Landmark3D
from gesture_controller.models.feature_engineering import compute_features
from gesture_controller.core.hardware_probe import probe_hardware


def test_base_backend_dynamic_resolution_scaling():
    """Verify BaseONNXBackend normalizes coordinates dynamically based on frame shape (MAE-REV-001)."""
    with (
        patch("gesture_controller.vision.backends.base_backend.PalmDetector"),
        patch("gesture_controller.vision.backends.base_backend.HandPoseEstimator"),
    ):
        backend = BaseONNXBackend(
            config={"engine": {"max_hands": 1}},
            providers=["CPUExecutionProvider"],
        )
        # Mock palm detector and hand pose estimator
        backend.palm_det.infer = MagicMock(return_value=np.array([[0, 0, 100, 100, 0.9]]))

        # 21 landmarks * 3 = 63 values in index 4:67
        mock_output = np.zeros(140)
        # Set wrist landmark (x=640, y=360, z=0)
        mock_output[4] = 640.0
        mock_output[5] = 360.0
        mock_output[6] = 0.0
        mock_output[130] = 0.8  # Right hand
        mock_output[131] = 0.95  # Score
        backend.hand_pose.infer = MagicMock(return_value=mock_output)

        # 1280x720 frame (h=720, w=1280)
        frame_720p = np.zeros((720, 1280, 3), dtype=np.uint8)
        hands = backend.detect_hands(frame_720p, timestamp_ms=1000)

        assert hands is not None
        assert len(hands) == 1
        wrist = hands[0].landmarks[0]
        # x = 640 / 1280 = 0.5, y = 360 / 720 = 0.5
        assert pytest.approx(wrist.x, rel=1e-3) == 0.5
        assert pytest.approx(wrist.y, rel=1e-3) == 0.5


def test_palm_detector_empty_frame_guard():
    """Verify PalmDetector.infer returns empty array when given None or empty frame (MAE-REV-002)."""
    with patch("onnxruntime.InferenceSession"):
        detector = PalmDetector("dummy.onnx", providers=["CPUExecutionProvider"])
        assert detector.infer(None).shape == (0, 19)
        assert detector.infer(np.empty((0, 0, 3), dtype=np.uint8)).shape == (0, 19)
        assert detector.infer(np.zeros((0, 480, 3), dtype=np.uint8)).shape == (0, 19)


def test_one_euro_filter_bounds_and_clock_rewind():
    """Verify OneEuroFilter bounds cutoff, clamps alpha, and handles clock rewinds safely (MAE-REV-003)."""
    filter_inst = OneEuroFilter()
    landmarks_init = np.ones((21, 3), dtype=np.float64) * 0.5

    # Initial frame
    filt_pos, vel, accel = filter_inst.filter(landmarks_init, timestamp=10.0)
    assert np.allclose(filt_pos, landmarks_init)

    # Subsequent frame with normal progress
    filt_pos, vel, accel = filter_inst.filter(landmarks_init + 0.1, timestamp=10.033)
    assert np.all(np.isfinite(filt_pos))
    assert np.all(np.isfinite(vel))
    assert np.all(np.isfinite(accel))

    # Clock rewind (timestamp < prev_timestamp)
    filt_pos, vel, accel = filter_inst.filter(landmarks_init + 0.2, timestamp=9.5)
    assert np.all(np.isfinite(filt_pos))
    assert np.all(np.isfinite(vel))
    assert np.all(np.isfinite(accel))

    # Test extreme negative cutoff
    alpha = OneEuroFilter._smoothing_factor(te=0.033, cutoff=-10.0)
    assert 0.0 <= alpha <= 1.0


def test_double_buffer_variable_resolution():
    """Verify DoubleFrameBuffer works seamlessly with non-default resolutions (MAE-REV-004)."""
    w, h, c = 1280, 720, 3
    custom_frame_size = w * h * c
    custom_total_size = HEADER_SIZE + 2 * custom_frame_size

    shm_name = f"test_shm_var_res_{int(time.time() * 1000)}"
    db_writer = DoubleFrameBuffer(name=shm_name, create=True, size=custom_total_size)
    db_reader = DoubleFrameBuffer(name=shm_name, create=False, size=custom_total_size)

    try:
        assert db_writer.frame_size == custom_frame_size
        assert db_reader.frame_size == custom_frame_size

        frame_data = np.full((h, w, c), 123, dtype=np.uint8)
        db_writer.write(memoryview(frame_data).cast("B"))

        read_bytes = db_reader.read()
        assert read_bytes is not None
        assert len(read_bytes) == custom_frame_size

        read_arr = db_reader.read_array(shape=(h, w, c))
        assert read_arr is not None
        assert read_arr.shape == (h, w, c)
        assert read_arr[0, 0, 0] == 123
    finally:
        db_writer.close()
        db_reader.close()
        try:
            db_writer.shm.unlink()
        except Exception:
            pass


def test_dtw_matcher_boundary_guards():
    """Verify DTW matcher functions handle empty and single-frame inputs without crashing (MAE-REV-005)."""
    empty_arr = np.zeros((0, DTW_FEATURE_DIMS), dtype=np.float64)
    valid_arr = np.ones((10, DTW_FEATURE_DIMS), dtype=np.float64)

    # Empty inputs in fast_dtw_distance
    assert fast_dtw_distance(empty_arr, valid_arr) == 1e9
    assert fast_dtw_distance(valid_arr, empty_arr) == 1e9
    assert fast_dtw_distance(empty_arr, empty_arr) == 1e9

    # normalize_sequence on empty list
    norm_empty = normalize_sequence([])
    assert norm_empty.shape == (DTW_BUFFER_FRAMES, DTW_FEATURE_DIMS)
    assert np.all(norm_empty == 0.0)

    # normalize_sequence on single frame
    single_frame = [np.ones((DTW_FEATURE_DIMS,), dtype=np.float64)]
    norm_single = normalize_sequence(single_frame)
    assert norm_single.shape == (DTW_BUFFER_FRAMES, DTW_FEATURE_DIMS)
    assert np.all(norm_single == 1.0)


def test_voice_command_registry_concurrency():
    """Verify VoiceCommandRegistry thread safety across concurrent readers and writers (MAE-REV-006)."""
    registry = VoiceCommandRegistry()
    stop_event = threading.Event()

    def writer():
        for i in range(100):
            if stop_event.is_set():
                break
            registry.register(f"phrase_{i}", f"Gesture_{i}")
            if i % 2 == 0:
                registry.unregister(f"phrase_{i}")
            time.sleep(0.001)

    def reader():
        for _ in range(100):
            if stop_event.is_set():
                break
            _ = registry.resolve("phrase_10")
            _ = registry.all_phrases()
            _ = len(registry)
            time.sleep(0.001)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
    stop_event.set()


def test_feature_engineering_sanitization():
    """Verify feature engineering sanitizes non-finite velocity/acceleration inputs (MAE-REV-007)."""
    landmarks = tuple(Landmark3D(x=float(i) * 0.02, y=float(i) * 0.02, z=0.0) for i in range(21))
    hand = Hand(landmarks=landmarks, handedness="Right", confidence=0.9)

    # Nan/inf velocity and acceleration
    nan_vel = np.full((21, 3), np.nan)
    inf_acc = np.full((21, 3), np.inf)

    fv = compute_features(
        hand, velocity=nan_vel, acceleration=inf_acc, timestamp=1.0, frame_number=1
    )
    assert np.all(np.isfinite(fv.palm_velocity))
    assert np.all(np.isfinite(fv.palm_acceleration))
    assert np.isfinite(fv.palm_velocity_magnitude)


def test_hardware_probe_battery_none_charging():
    """Verify HardwareProbe treats power_plugged=None as True (MAE-REV-008)."""
    with patch("psutil.sensors_battery") as mock_bat:
        # Mock battery object where power_plugged is None (common in hypervisors)
        mock_obj = MagicMock()
        mock_obj.percent = 85.0
        mock_obj.power_plugged = None
        mock_bat.return_value = mock_obj

        profile = probe_hardware()
        assert profile.has_battery is True
        assert profile.battery_percent == 85.0
        assert profile.is_charging is True
