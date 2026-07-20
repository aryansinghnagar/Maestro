import pytest
from unittest.mock import MagicMock, patch
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.frame_pipeline import FramePipeline


def test_frame_pipeline_lifecycle() -> None:
    mock_process = MagicMock()
    mock_shm = MagicMock()
    mock_shm.name = "mock_shm"
    mock_shm.buf = bytearray(1843208)

    config = ConfigManager()

    with (
        patch("multiprocessing.shared_memory.SharedMemory", return_value=mock_shm),
        patch("gesture_controller.core.frame_pipeline.mp.Process", return_value=mock_process),
    ):
        pipeline = FramePipeline(config)
        assert pipeline.shm_name is not None

        pipeline.start()
        assert pipeline._camera_process is not None

        pipeline.shutdown()
        assert pipeline._camera_process is None
        assert pipeline._db_buffer is None
