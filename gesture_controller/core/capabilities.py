"""Capability Registry for Adaptive Performance Tiers — Phase 2.

Defines:
- Tier enum (ULTRA T0, HIGH T1, STANDARD T2, MINIMAL T3)
- CapabilitySet frozen dataclass detailing active subsystem configurations
- TIER_PRESETS dictionary providing tier-specific defaults
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Tier(str, Enum):
    """Performance tier designations."""

    ULTRA = "T0"
    HIGH = "T1"
    STANDARD = "T2"
    MINIMAL = "T3"


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """Read-only capability values active for the current performance tier."""

    tier: Tier
    camera_fps_target: int
    camera_frame_width: int
    camera_frame_height: int
    inference_backend: str  # "auto", "cuda", "coreml", "directml", "tensorrt", "cpu"
    model_quantization: str  # "fp16", "fp32", "int8"
    model_input_size: tuple[int, int]  # (width, height)
    hud_enabled: bool
    hud_skeleton_render_fps: int  # 0 = off, 60, 30, 15
    hud_show_tracking_points: bool
    voice_listener_enabled: bool
    integration_server_enabled: bool
    plugin_loading_mode: str  # "all", "wasm_only", "none"
    custom_gesture_dtw: bool
    one_euro_filter: bool
    tremor_compensation: bool
    dwell_clicker: bool
    global_hotkeys: bool
    max_hands: int
    overlay_opacity: float
    diagnostics_export_interval_s: int  # 0 = manual only

    def to_dict(self) -> dict[str, Any]:
        """Return dict representation of capability set."""
        return {
            "tier": self.tier.value,
            "camera_fps_target": self.camera_fps_target,
            "camera_frame_width": self.camera_frame_width,
            "camera_frame_height": self.camera_frame_height,
            "inference_backend": self.inference_backend,
            "model_quantization": self.model_quantization,
            "model_input_size": list(self.model_input_size),
            "hud_enabled": self.hud_enabled,
            "hud_skeleton_render_fps": self.hud_skeleton_render_fps,
            "hud_show_tracking_points": self.hud_show_tracking_points,
            "voice_listener_enabled": self.voice_listener_enabled,
            "integration_server_enabled": self.integration_server_enabled,
            "plugin_loading_mode": self.plugin_loading_mode,
            "custom_gesture_dtw": self.custom_gesture_dtw,
            "one_euro_filter": self.one_euro_filter,
            "tremor_compensation": self.tremor_compensation,
            "dwell_clicker": self.dwell_clicker,
            "global_hotkeys": self.global_hotkeys,
            "max_hands": self.max_hands,
            "overlay_opacity": self.overlay_opacity,
            "diagnostics_export_interval_s": self.diagnostics_export_interval_s,
        }


TIER_PRESETS: dict[Tier, CapabilitySet] = {
    Tier.ULTRA: CapabilitySet(
        tier=Tier.ULTRA,
        camera_fps_target=60,
        camera_frame_width=1280,
        camera_frame_height=720,
        inference_backend="auto",
        model_quantization="fp16",
        model_input_size=(256, 256),
        hud_enabled=True,
        hud_skeleton_render_fps=60,
        hud_show_tracking_points=True,
        voice_listener_enabled=True,
        integration_server_enabled=True,
        plugin_loading_mode="all",
        custom_gesture_dtw=True,
        one_euro_filter=True,
        tremor_compensation=True,
        dwell_clicker=True,
        global_hotkeys=True,
        max_hands=2,
        overlay_opacity=0.3,
        diagnostics_export_interval_s=0,
    ),
    Tier.HIGH: CapabilitySet(
        tier=Tier.HIGH,
        camera_fps_target=30,
        camera_frame_width=640,
        camera_frame_height=480,
        inference_backend="auto",
        model_quantization="int8",
        model_input_size=(224, 224),
        hud_enabled=True,
        hud_skeleton_render_fps=30,
        hud_show_tracking_points=True,
        voice_listener_enabled=True,
        integration_server_enabled=True,
        plugin_loading_mode="all",
        custom_gesture_dtw=True,
        one_euro_filter=True,
        tremor_compensation=True,
        dwell_clicker=True,
        global_hotkeys=True,
        max_hands=2,
        overlay_opacity=0.3,
        diagnostics_export_interval_s=0,
    ),
    Tier.STANDARD: CapabilitySet(
        tier=Tier.STANDARD,
        camera_fps_target=20,
        camera_frame_width=480,
        camera_frame_height=360,
        inference_backend="cpu",
        model_quantization="int8",
        model_input_size=(192, 192),
        hud_enabled=True,
        hud_skeleton_render_fps=15,
        hud_show_tracking_points=True,
        voice_listener_enabled=False,
        integration_server_enabled=False,
        plugin_loading_mode="wasm_only",
        custom_gesture_dtw=True,
        one_euro_filter=True,
        tremor_compensation=False,
        dwell_clicker=True,
        global_hotkeys=True,
        max_hands=1,
        overlay_opacity=0.4,
        diagnostics_export_interval_s=0,
    ),
    Tier.MINIMAL: CapabilitySet(
        tier=Tier.MINIMAL,
        camera_fps_target=10,
        camera_frame_width=320,
        camera_frame_height=240,
        inference_backend="cpu",
        model_quantization="int8",
        model_input_size=(160, 160),
        hud_enabled=False,
        hud_skeleton_render_fps=0,
        hud_show_tracking_points=False,
        voice_listener_enabled=False,
        integration_server_enabled=False,
        plugin_loading_mode="none",
        custom_gesture_dtw=False,
        one_euro_filter=True,
        tremor_compensation=False,
        dwell_clicker=False,
        global_hotkeys=True,
        max_hands=1,
        overlay_opacity=0.0,
        diagnostics_export_interval_s=0,
    ),
}
