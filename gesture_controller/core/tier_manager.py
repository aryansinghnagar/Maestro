"""Tier Manager for Adaptive Performance System — Phase 2.

Manages periodic hardware probing, classifier evaluation, debounced transitions,
and publishes `TierChanged` events on the EventBus.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import psutil
import structlog

from gesture_controller.core.capabilities import CapabilitySet, TIER_PRESETS, Tier
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.hardware_probe import HardwareProfile, probe_hardware
from gesture_controller.core.tier_classifier import RuntimeConditions, classify_tier

logger = structlog.get_logger(__name__)


class TierManager:
    """Orchestrates hardware classification and subsystem capability dispatch."""

    def __init__(self, config_manager: Any, event_bus: EventBus) -> None:
        self._config_manager = config_manager
        self._event_bus = event_bus
        self._lock = threading.RLock()

        self._hw_profile: HardwareProfile = probe_hardware()
        self._detected_tier: Tier = Tier.HIGH
        self._active_tier: Tier = Tier.HIGH
        self._capabilities: CapabilitySet = TIER_PRESETS[Tier.HIGH]

        self._manual_override: Optional[str] = None
        self._capability_overrides: dict[str, Any] = {}

        # Debounce state
        self._pending_tier: Optional[Tier] = None
        self._pending_since: float = 0.0
        self._downgrade_debounce_s: float = 30.0
        self._upgrade_debounce_s: float = 60.0

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._init_from_config()
        self.reevaluate(force_immediate=True)

    def _init_from_config(self) -> None:
        cfg = self._config_manager.get_config()
        perf_cfg = cfg.get("performance", {})
        override = perf_cfg.get("tier", "auto")
        if override != "auto" and override in Tier.__members__.values():
            self._manual_override = override

        self._capability_overrides = perf_cfg.get("override_capabilities", {})

    @property
    def hardware_profile(self) -> HardwareProfile:
        return self._hw_profile

    @property
    def detected_tier(self) -> Tier:
        return self._detected_tier

    @property
    def active_tier(self) -> Tier:
        return self._active_tier

    @property
    def capabilities(self) -> CapabilitySet:
        with self._lock:
            return self._capabilities

    def get_runtime_conditions(self) -> RuntimeConditions:
        """Sample current live system metrics."""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        bat_pct = 100.0
        charging = True
        try:
            if hasattr(psutil, "sensors_battery"):
                bat = psutil.sensors_battery()
                if bat is not None:
                    bat_pct = float(bat.percent)
                    charging = bool(bat.power_plugged)
        except Exception:
            pass

        return RuntimeConditions(
            cpu_usage_1min_avg=float(cpu),
            ram_usage_percent=float(mem),
            battery_percent=bat_pct,
            is_charging=charging,
            thermal_state="nominal",
            pipeline_p95_latency_ms=12.0,
            pipeline_error_rate=0.0,
        )

    def reevaluate(self, force_immediate: bool = False) -> Tier:
        """Evaluate classifier and update active capability set if changed."""
        with self._lock:
            rc = self.get_runtime_conditions()
            classified = classify_tier(self._hw_profile, rc)
            self._detected_tier = classified

            target_tier = Tier(self._manual_override) if self._manual_override else classified

            now = time.monotonic()
            tier_rank = {Tier.ULTRA: 4, Tier.HIGH: 3, Tier.STANDARD: 2, Tier.MINIMAL: 1}

            # Safety drops (battery < 10% or thermal critical) apply immediately
            is_safety_drop = rc.battery_percent < 10.0 or rc.thermal_state == "critical"

            if force_immediate or is_safety_drop or target_tier == self._active_tier:
                self._pending_tier = None
                if target_tier != self._active_tier or force_immediate:
                    self._apply_tier_change(target_tier)
                return self._active_tier

            # Debounce evaluation
            if self._pending_tier != target_tier:
                self._pending_tier = target_tier
                self._pending_since = now
            else:
                elapsed = now - self._pending_since
                is_downgrade = tier_rank[target_tier] < tier_rank[self._active_tier]
                required = self._downgrade_debounce_s if is_downgrade else self._upgrade_debounce_s

                if elapsed >= required:
                    self._apply_tier_change(target_tier)
                    self._pending_tier = None

            return self._active_tier

    def _apply_tier_change(self, new_tier: Tier) -> None:
        old_tier = self._active_tier
        self._active_tier = new_tier

        base_preset = TIER_PRESETS[new_tier]
        if self._capability_overrides:
            d = base_preset.to_dict()
            d.update(self._capability_overrides)
            # Reconstruct CapabilitySet with overrides
            d["tier"] = Tier(d["tier"])
            d["model_input_size"] = tuple(d["model_input_size"])
            self._capabilities = CapabilitySet(**d)
        else:
            self._capabilities = base_preset

        logger.info(
            "metric_tier_changed",
            old_tier=old_tier.value,
            new_tier=new_tier.value,
            detected_tier=self._detected_tier.value,
            manual_override=self._manual_override,
        )

        try:
            self._event_bus.publish(
                "tier_changed",
                {
                    "old_tier": old_tier.value,
                    "new_tier": new_tier.value,
                    "capabilities": self._capabilities.to_dict(),
                },
            )
        except Exception as e:
            logger.error("Failed publishing tier_changed event", error=str(e))

    def set_manual_override(self, override: Optional[str]) -> None:
        """Set or clear manual tier override."""
        with self._lock:
            self._manual_override = override
            self.reevaluate(force_immediate=True)

    def start_monitoring(self, interval_s: float = 30.0) -> None:
        """Start periodic background monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._monitor_loop, args=(interval_s,), daemon=True, name="TierMonitorThread"
            )
            self._thread.start()

    def stop_monitoring(self) -> None:
        """Stop background monitoring thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _monitor_loop(self, interval_s: float) -> None:
        while self._running:
            time.sleep(interval_s)
            if self._running:
                try:
                    self.reevaluate()
                except Exception as e:
                    logger.error("Error in tier monitor loop", error=str(e))
