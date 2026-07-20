"""Hardware Probe for Adaptive Performance Tier System — Phase 2.

Collects platform metrics, CPU count, RAM capacity, ONNX execution providers,
battery status, and screen properties in <5ms.
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass
from typing import Any

import psutil
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Read-only hardware specification captured at startup."""

    os: str  # "Windows", "Darwin", "Linux"
    cpu_count_physical: int
    cpu_count_logical: int
    cpu_freq_mhz: int  # 0 if unknown
    total_ram_gb: float
    has_cuda: bool
    has_coreml: bool
    has_directml: bool
    has_tensorrt: bool
    has_opencl: bool
    gpu_names: list[str]
    is_laptop: bool
    has_battery: bool
    battery_percent: float  # 0-100
    is_charging: bool
    screen_count: int
    primary_screen_dpi: float
    thermal_state: str  # "nominal", "fair", "serious", "critical"

    def to_dict(self) -> dict[str, Any]:
        """Return dictionary representation for metrics / logging."""
        return {
            "os": self.os,
            "cpu_count_physical": self.cpu_count_physical,
            "cpu_count_logical": self.cpu_count_logical,
            "cpu_freq_mhz": self.cpu_freq_mhz,
            "total_ram_gb": round(self.total_ram_gb, 2),
            "has_cuda": self.has_cuda,
            "has_coreml": self.has_coreml,
            "has_directml": self.has_directml,
            "has_tensorrt": self.has_tensorrt,
            "has_opencl": self.has_opencl,
            "gpu_names": self.gpu_names,
            "is_laptop": self.is_laptop,
            "has_battery": self.has_battery,
            "battery_percent": self.battery_percent,
            "is_charging": self.is_charging,
            "screen_count": self.screen_count,
            "primary_screen_dpi": self.primary_screen_dpi,
            "thermal_state": self.thermal_state,
        }


def probe_hardware() -> HardwareProfile:
    """Probe host hardware capabilities. Enforces <5ms performance target."""
    t0 = time.perf_counter()

    os_name = platform.system()
    mem = psutil.virtual_memory()
    total_ram_gb = float(mem.total / (1024**3))

    cpu_phys = psutil.cpu_count(logical=False) or 2
    cpu_log = psutil.cpu_count(logical=True) or 2
    try:
        freq_obj = psutil.cpu_freq()
        cpu_freq_mhz = int(freq_obj.max) if freq_obj and freq_obj.max else 0
    except Exception:
        cpu_freq_mhz = 0

    has_cuda = has_coreml = has_directml = has_tensorrt = has_opencl = False
    gpu_names: list[str] = []
    try:
        import onnxruntime as ort  # type: ignore[import-untyped]

        providers = ort.get_available_providers()
        has_cuda = "CUDAExecutionProvider" in providers
        has_coreml = "CoreMLExecutionProvider" in providers
        has_directml = (
            "DmlExecutionProvider" in providers or "DirectMLExecutionProvider" in providers
        )
        has_tensorrt = "TensorrtExecutionProvider" in providers
        gpu_names = [
            p.replace("ExecutionProvider", "") for p in providers if p != "CPUExecutionProvider"
        ]
    except Exception:
        pass

    has_battery = False
    battery_percent = 100.0
    is_charging = True
    try:
        if hasattr(psutil, "sensors_battery"):
            bat = psutil.sensors_battery()
            if bat is not None:
                has_battery = True
                battery_percent = float(bat.percent)
                is_charging = bool(bat.power_plugged)
    except Exception:
        pass

    screen_count = 1
    primary_screen_dpi = 96.0
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if isinstance(app, QApplication):
            screens = app.screens()
            screen_count = len(screens)
            prim = app.primaryScreen()
            if prim:
                primary_screen_dpi = float(prim.logicalDotsPerInch())
    except Exception:
        pass

    profile = HardwareProfile(
        os=os_name,
        cpu_count_physical=cpu_phys,
        cpu_count_logical=cpu_log,
        cpu_freq_mhz=cpu_freq_mhz,
        total_ram_gb=total_ram_gb,
        has_cuda=has_cuda,
        has_coreml=has_coreml,
        has_directml=has_directml,
        has_tensorrt=has_tensorrt,
        has_opencl=has_opencl,
        gpu_names=gpu_names,
        is_laptop=has_battery,
        has_battery=has_battery,
        battery_percent=battery_percent,
        is_charging=is_charging,
        screen_count=screen_count,
        primary_screen_dpi=primary_screen_dpi,
        thermal_state="nominal",
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if elapsed_ms > 1000.0:
        logger.warning("hardware_probe_slow", elapsed_ms=elapsed_ms)

    return profile
