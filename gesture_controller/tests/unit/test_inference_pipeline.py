import pytest
from unittest.mock import MagicMock
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.inference_pipeline import InferencePipeline


def test_inference_pipeline() -> None:
    mock_extractor_cls = MagicMock()
    config = ConfigManager()

    pipeline = InferencePipeline(config, landmark_extractor_cls=mock_extractor_cls)
    assert pipeline._extractor is not None

    pipeline.close()
    pipeline._extractor.close.assert_called_once()
