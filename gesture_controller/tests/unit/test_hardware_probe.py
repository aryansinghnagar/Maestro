"""Unit tests for Hardware Probe module (gesture_controller/core/hardware_probe.py)."""

from unittest.mock import MagicMock, patch
import pytest

from gesture_controller.core.hardware_probe import HardwareProfile, probe_hardware


def test_hardware_profile_to_dict() -> None:
    profile = HardwareProfile(
        os="Windows",
        cpu_count_physical=4,
        cpu_count_logical=8,
        cpu_freq_mhz=3200,
        total_ram_gb=15.999,
        has_cuda=True,
        has_coreml=False,
        has_directml=True,
        has_tensorrt=False,
        has_opencl=False,
        gpu_names=["CUDA", "DirectML"],
        is_laptop=True,
        has_battery=True,
        battery_percent=85.5,
        is_charging=True,
        screen_count=2,
        primary_screen_dpi=96.0,
        thermal_state="nominal",
    )
    d = profile.to_dict()
    assert d["os"] == "Windows"
    assert d["cpu_count_physical"] == 4
    assert d["cpu_count_logical"] == 8
    assert d["total_ram_gb"] == 16.0
    assert d["has_cuda"] is True
    assert d["gpu_names"] == ["CUDA", "DirectML"]
    assert d["is_laptop"] is True
    assert d["battery_percent"] == 85.5


def test_probe_hardware_execution() -> None:
    profile = probe_hardware()
    assert isinstance(profile, HardwareProfile)
    assert profile.cpu_count_physical > 0
    assert profile.cpu_count_logical >= profile.cpu_count_physical
    assert profile.total_ram_gb > 0.0
    assert profile.os in ["Windows", "Darwin", "Linux"]


def test_probe_hardware_cpu_freq_exception() -> None:
    with patch("psutil.cpu_freq", side_effect=RuntimeError("psutil error")):
        profile = probe_hardware()
        assert profile.cpu_freq_mhz == 0


def test_probe_hardware_battery_detection() -> None:
    mock_battery = MagicMock(percent=75.0, power_plugged=False)
    with patch("psutil.sensors_battery", return_value=mock_battery):
        profile = probe_hardware()
        assert profile.has_battery is True
        assert profile.battery_percent == 75.0
        assert profile.is_charging is False


def test_probe_hardware_onnx_import_error() -> None:
    with patch.dict("sys.modules", {"onnxruntime": None}):
        profile = probe_hardware()
        assert isinstance(profile, HardwareProfile)
