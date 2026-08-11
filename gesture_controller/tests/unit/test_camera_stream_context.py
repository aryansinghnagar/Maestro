import pytest
from unittest.mock import MagicMock, patch
from gesture_controller.vision.camera_stream import VideoCaptureContext


def test_video_capture_context_success() -> None:
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch("cv2.VideoCapture", return_value=mock_cap) as mock_vc:
        with VideoCaptureContext(device_id=0) as cap:
            assert cap == mock_cap
            assert cap.isOpened() is True
        mock_cap.release.assert_called_once()


def test_video_capture_context_exception_cleanup() -> None:
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch("cv2.VideoCapture", return_value=mock_cap):
        try:
            with VideoCaptureContext(device_id=0):
                raise RuntimeError("Simulated camera frame error")
        except RuntimeError:
            pass
        mock_cap.release.assert_called_once()


def test_video_capture_context_manual_release() -> None:
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch("cv2.VideoCapture", return_value=mock_cap):
        ctx = VideoCaptureContext(device_id=0)
        cap = ctx.__enter__()
        assert cap == mock_cap
        ctx.release()
        mock_cap.release.assert_called_once()
        assert ctx.cap is None
