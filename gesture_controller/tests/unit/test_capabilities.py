"""Unit tests for Capabilities module (gesture_controller/core/capabilities.py)."""

import pytest
from gesture_controller.core.capabilities import Tier, CapabilitySet, TIER_PRESETS


def test_tier_enum_values() -> None:
    assert Tier.ULTRA.value == "T0"
    assert Tier.HIGH.value == "T1"
    assert Tier.STANDARD.value == "T2"
    assert Tier.MINIMAL.value == "T3"


def test_capability_set_to_dict() -> None:
    cap = TIER_PRESETS[Tier.ULTRA]
    d = cap.to_dict()
    assert d["tier"] == "T0"
    assert d["camera_fps_target"] == 60
    assert d["camera_frame_width"] == 1280
    assert d["camera_frame_height"] == 720
    assert d["model_input_size"] == [256, 256]
    assert d["hud_enabled"] is True
    assert d["voice_listener_enabled"] is True


def test_tier_presets_completeness() -> None:
    for tier in Tier:
        assert tier in TIER_PRESETS
        preset = TIER_PRESETS[tier]
        assert preset.tier == tier
        assert preset.camera_fps_target > 0
        assert len(preset.model_input_size) == 2
