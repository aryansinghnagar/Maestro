"""Tier Classifier for Adaptive Performance System — Phase 2.

Evaluates a HardwareProfile and dynamic RuntimeConditions to determine the optimal Tier.
Pure function implementation ensuring 100% unit-testability without hardware dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from gesture_controller.core.capabilities import Tier
from gesture_controller.core.hardware_probe import HardwareProfile


@dataclass(frozen=True, slots=True)
class RuntimeConditions:
    """Live metric signals captured during app runtime."""

    cpu_usage_1min_avg: float  # 0-100%
    ram_usage_percent: float  # 0-100%
    battery_percent: float  # 0-100%
    is_charging: bool
    thermal_state: str  # "nominal", "fair", "serious", "critical"
    pipeline_p95_latency_ms: float  # rolling p95 latency
    pipeline_error_rate: float  # 0-1


def classify_tier(hw: HardwareProfile, rc: RuntimeConditions) -> Tier:
    """Classify the system into Tier.ULTRA (T0), HIGH (T1), STANDARD (T2), or MINIMAL (T3)."""
    # 1. Safety Hard Floor: Critical battery or thermal state -> MINIMAL (T3)
    if rc.battery_percent < 10.0 and not rc.is_charging:
        return Tier.MINIMAL
    if rc.thermal_state == "critical":
        return Tier.MINIMAL

    # 2. Hardware Hard Floor: <3GB RAM or 1 physical core -> MINIMAL (T3)
    if hw.total_ram_gb < 3.0 or hw.cpu_count_physical < 2:
        return Tier.MINIMAL

    # 3. Dynamic Latency Degradation: Latency overload -> Drop to STANDARD or MINIMAL
    if rc.pipeline_p95_latency_ms > 100.0:
        return Tier.MINIMAL
    if rc.pipeline_p95_latency_ms > 50.0:
        return Tier.STANDARD

    cpu_heavy = rc.cpu_usage_1min_avg > 85.0

    # 4. ULTRA (T0): 8+ physical cores, 16+ GB RAM, GPU acceleration, plugged in
    has_gpu_accel = hw.has_cuda or hw.has_coreml or hw.has_directml or hw.has_tensorrt
    if (
        hw.cpu_count_physical >= 8
        and hw.total_ram_gb >= 15.5
        and has_gpu_accel
        and (rc.is_charging or not hw.has_battery)
    ):
        if not cpu_heavy:
            return Tier.ULTRA

    # 5. HIGH (T1): 4+ physical cores, 8+ GB RAM, plugged in (if laptop)
    if (
        hw.cpu_count_physical >= 4
        and hw.total_ram_gb >= 7.5
        and (rc.is_charging or not hw.has_battery)
    ):
        if not cpu_heavy:
            return Tier.HIGH

    # 6. STANDARD (T2): 2+ physical cores, 4+ GB RAM
    if hw.cpu_count_physical >= 2 and hw.total_ram_gb >= 3.5:
        return Tier.STANDARD

    return Tier.MINIMAL
