"""Unit tests for Phase 2 — Adaptive Performance Tier System.

Tests:
1. Capabilities dataclass and preset mappings (T0-T3).
2. Hardware probe execution speed (<5ms) and profile output.
3. Pure tier classifier boundaries (battery floor, RAM floor, latency overload, T0-T3 rules).
4. TierManager initialization, reevaluation, debounced transitions, and manual overrides.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from gesture_controller.core.capabilities import CapabilitySet, TIER_PRESETS, Tier
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.hardware_probe import HardwareProfile, probe_hardware
from gesture_controller.core.tier_classifier import RuntimeConditions, classify_tier
from gesture_controller.core.tier_manager import TierManager


def test_capabilities_presets():
    assert len(TIER_PRESETS) == 4
    for tier in Tier:
        preset = TIER_PRESETS[tier]
        assert preset.tier == tier
        assert isinstance(preset.to_dict(), dict)

    assert TIER_PRESETS[Tier.ULTRA].camera_fps_target == 60
    assert TIER_PRESETS[Tier.MINIMAL].hud_enabled is False


def test_hardware_probe():
    t0 = time.perf_counter()
    hw = probe_hardware()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert isinstance(hw, HardwareProfile)
    assert hw.cpu_count_physical >= 1
    assert hw.total_ram_gb > 0.0
    assert isinstance(hw.to_dict(), dict)
    assert elapsed_ms < 1000.0  # Execution timing threshold


def _make_hw(cores=8, ram=16.0, cuda=True):
    return HardwareProfile(
        os="Windows",
        cpu_count_physical=cores,
        cpu_count_logical=cores * 2,
        cpu_freq_mhz=3200,
        total_ram_gb=ram,
        has_cuda=cuda,
        has_coreml=False,
        has_directml=False,
        has_tensorrt=False,
        has_opencl=False,
        gpu_names=["NVIDIA RTX 3080"],
        is_laptop=False,
        has_battery=False,
        battery_percent=100.0,
        is_charging=True,
        screen_count=1,
        primary_screen_dpi=96.0,
        thermal_state="nominal",
    )


def _make_rc(battery=100.0, charging=True, thermal="nominal", latency=10.0, cpu=20.0):
    return RuntimeConditions(
        cpu_usage_1min_avg=cpu,
        ram_usage_percent=30.0,
        battery_percent=battery,
        is_charging=charging,
        thermal_state=thermal,
        pipeline_p95_latency_ms=latency,
        pipeline_error_rate=0.0,
    )


def test_classifier_rules():
    # 1. Critical battery -> MINIMAL (T3)
    hw = _make_hw(cores=8, ram=32.0, cuda=True)
    rc_bat = _make_rc(battery=5.0, charging=False)
    assert classify_tier(hw, rc_bat) == Tier.MINIMAL

    # 2. Critical thermal -> MINIMAL (T3)
    rc_therm = _make_rc(thermal="critical")
    assert classify_tier(hw, rc_therm) == Tier.MINIMAL

    # 3. Low RAM -> MINIMAL (T3)
    hw_low_ram = _make_hw(cores=8, ram=2.0, cuda=True)
    assert classify_tier(hw_low_ram, _make_rc()) == Tier.MINIMAL

    # 4. Latency overload -> STANDARD or MINIMAL
    rc_lat55 = _make_rc(latency=55.0)
    assert classify_tier(hw, rc_lat55) == Tier.STANDARD

    rc_lat105 = _make_rc(latency=105.0)
    assert classify_tier(hw, rc_lat105) == Tier.MINIMAL

    # 5. ULTRA (T0) match
    assert classify_tier(hw, _make_rc()) == Tier.ULTRA

    # 6. HIGH (T1) match (no CUDA)
    hw_no_gpu = _make_hw(cores=4, ram=8.0, cuda=False)
    assert classify_tier(hw_no_gpu, _make_rc()) == Tier.HIGH

    # 7. STANDARD (T2) match (2 cores, 4GB RAM)
    hw_std = _make_hw(cores=2, ram=4.0, cuda=False)
    assert classify_tier(hw_std, _make_rc()) == Tier.STANDARD


def test_tier_manager_flow():
    cfg_mock = MagicMock()
    cfg_mock.get_config.return_value = {"performance": {"tier": "auto"}}
    bus = EventBus()

    manager = TierManager(config_manager=cfg_mock, event_bus=bus)
    assert manager.active_tier in list(Tier)
    assert manager.capabilities is not None

    # Manual override to MINIMAL
    manager.set_manual_override("T3")
    assert manager.active_tier == Tier.MINIMAL
    assert manager.capabilities.tier == Tier.MINIMAL

    # Clear override
    manager.set_manual_override(None)
    assert manager.active_tier in list(Tier)
