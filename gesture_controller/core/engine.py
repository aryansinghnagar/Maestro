import threading
import time
import platform
from pathlib import Path
from typing import Any
import structlog

from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.metrics import MetricsCollector
from gesture_controller.plugins.plugin_loader import PluginLoader
from gesture_controller.os_integration.action_dispatcher import ActionDispatcher
from gesture_controller.core.frame_pipeline import FramePipeline
from gesture_controller.core.inference_pipeline import InferencePipeline
from gesture_controller.core.gesture_recognizer import GestureRecognizer
from gesture_controller.core.signal_handler import SignalHandler
from gesture_controller.models.data_types import Hand

# Import these at module level to allow legacy unit tests to patch them
from multiprocessing import shared_memory
from gesture_controller.vision.camera_stream import create_camera_process
from gesture_controller.vision.landmark_extractor import LandmarkExtractor
from gesture_controller.models.dtw_matcher import CustomGestureMatcher
from gesture_controller.models.feature_engineering import compute_features

logger = structlog.get_logger(__name__)


class GestureEngine:
    """Master daemon coordinator (EngineCoordinator). Coordinates the gesture recognition pipeline."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config = ConfigManager(config_path)
        self._event_bus = EventBus()
        self._metrics = MetricsCollector()
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._frame_count = 0
        self._current_hands: list[Hand] = []
        self._fps = 0.0
        self._last_fps_time = time.monotonic()
        self._fps_frame_count = 0
        self._gesture_count = 0
        self._correlation_counter = 0

        # Sub-components
        self._plugin_loader = PluginLoader(self._event_bus)
        self._plugin_loader.discover_all()

        self._controller = self._create_os_controller()
        self._dispatcher = ActionDispatcher(self._controller, self._config, self._event_bus)

        self._frame_pipeline = FramePipeline(self._config, create_camera_process=create_camera_process)
        
        try:
            self._frame_pipeline.start()
            self._inference_pipeline = InferencePipeline(
                self._config,
                landmark_extractor_cls=LandmarkExtractor,
            )
            self._gesture_recognizer = GestureRecognizer(self._config, self._event_bus, self._plugin_loader)
            self._signal_handler = SignalHandler(self.shutdown)
        except Exception as e:
            logger.critical("Engine initialization failed, rolling back resources...", error=str(e))
            self._frame_pipeline.shutdown()
            raise

        self._event_bus.subscribe("engine_pause_requested", self.set_paused)

    @property
    def _shm_name(self) -> str:
        return self._frame_pipeline.shm_name

    @property
    def _camera_process(self) -> Any:
        return self._frame_pipeline._camera_process

    @property
    def _frame_ready_event(self) -> Any:
        return self._frame_pipeline._frame_ready_event

    @property
    def _extractor(self) -> Any:
        return self._inference_pipeline._extractor

    def _create_os_controller(self) -> Any:
        """Create OS Controller appropriate for the platform."""
        current_os = platform.system()
        try:
            from gesture_controller.os_integration import create_controller
            return create_controller()
        except Exception as e:
            logger.warning(
                "Failed to create platform controller, falling back to dummy controller",
                error=str(e),
                os=current_os,
            )
            from gesture_controller.os_integration.base_controller import BaseController

            class DummyController(BaseController):
                def is_supported(self) -> bool:
                    return False
                def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
                    pass
                def key_release(self, key: str) -> None:
                    pass
                def key_combo(self, keys: list[str]) -> None:
                    pass
                def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
                    pass
                def mouse_double_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
                    pass
                def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
                    pass
                def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
                    pass
                def get_foreground_app(self) -> str:
                    return ""
                def minimize_active_window(self) -> None:
                    pass
                def switch_window(self) -> None:
                    pass
                def show_desktop(self) -> None:
                    pass
                def media_play_pause(self) -> None:
                    pass
                def media_next(self) -> None:
                    pass
                def media_previous(self) -> None:
                    pass
                def media_volume_up(self) -> None:
                    pass
                def media_volume_down(self) -> None:
                    pass

            return DummyController()

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the gesture recognition loop."""
        self._paused = paused
        logger.info("GestureEngine pause state changed", paused=paused)

    def is_paused(self) -> bool:
        """Check if engine is currently paused."""
        return self._paused

    def start(self) -> None:
        """Start the engine main loop thread."""
        if self._running:
            return
        self._running = True
        self._plugin_loader.start_hot_reload()
        # Note: FramePipeline start is now handled in __init__ (matches original GestureEngine sequence)
        self._signal_handler.install()
        self._thread = threading.Thread(target=self._main_loop, daemon=True, name="engine_loop")
        self._thread.start()
        logger.info("GestureEngine main thread started")

    def _main_loop(self) -> None:
        """Internal main loop retrieving frames, running inference, and evaluating FSMs."""
        last_hand_time = time.monotonic()
        while self._running:
            try:
                if self._paused:
                    time.sleep(0.01)
                    continue

                # Block until camera process announces frame ready
                if not self._frame_pipeline.wait_for_frame(0.1):
                    continue

                loop_start = time.perf_counter()
                self._correlation_counter += 1
                correlation_id = self._correlation_counter

                # Rolling FPS calculation
                self._fps_frame_count += 1
                now = time.monotonic()
                if now - self._last_fps_time >= 1.0:
                    self._fps = self._fps_frame_count / (now - self._last_fps_time)
                    self._fps_frame_count = 0
                    self._last_fps_time = now
                    self._metrics.set_gauge("fps", self._fps)
                    self._metrics.emit()
                    logger.info(
                        "metric_fps",
                        fps=self._fps,
                        frame_count=self._frame_count,
                        correlation_id=correlation_id,
                    )

                timestamp = now
                raw_hands, smoothed_hands, features_list = self._inference_pipeline.process(
                    self._frame_pipeline.shm_name, timestamp, self._frame_count
                )

                if raw_hands:
                    # Publish raw landmarks
                    self._event_bus.publish("raw_landmarks", raw_hands)
                    last_hand_time = time.monotonic()

                    for track_id, features in features_list:
                        # Find the correct hand by matching track ID index
                        hand_idx = next(i for i, (tid, _) in enumerate(features_list) if tid == track_id)
                        hand = smoothed_hands[hand_idx]

                        event = self._gesture_recognizer.evaluate(
                            track_id, features, hand, timestamp, correlation_id
                        )

                        if event:
                            self._event_bus.publish("gesture_triggered", event)
                            self._gesture_count += 1
                            logger.info(
                                "Gesture Triggered",
                                gesture=event.gesture_name,
                                action=event.action,
                                correlation_id=correlation_id,
                            )

                    # Manage retired track IDs
                    active_ids = self._inference_pipeline._active_track_ids
                    recognizer_track_ids = set(self._gesture_recognizer._custom_matchers.keys())
                    retired_ids = recognizer_track_ids - active_ids
                    for retired_id in retired_ids:
                        self._gesture_recognizer.remove_hand(retired_id)

                    self._current_hands = smoothed_hands
                else:
                    self._current_hands = []
                    self._gesture_recognizer.reset()

                processing_time = time.perf_counter() - loop_start
                self._frame_pipeline.adapt_fps(processing_time)
                self._frame_pipeline.maybe_idle(last_hand_time)
                self._frame_count += 1
                self._metrics.observe(
                    "frame_processing_latency_seconds", processing_time
                )
            except Exception as e:
                logger.error("Error inside engine main loop", error=str(e))

    def shutdown(self) -> None:
        """Gracefully shuts down background engine thread, camera process and SharedMemory."""
        if not self._running:
            return
        logger.info("Shutting down GestureEngine...")
        self._running = False

        self._plugin_loader.stop_hot_reload()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._frame_pipeline.shutdown()
        self._inference_pipeline.close()
        self._signal_handler.uninstall()

    def get_current_hands(self) -> list[Hand]:
        """Return the latest detected and filtered Hand data."""
        return list(self._current_hands)

    def get_fsm_states(self) -> dict[str, tuple[str, float]]:
        """Return states of all FSMs."""
        return self._gesture_recognizer.get_fsm_states()

    def get_fps(self) -> float:
        """Return the current frame processing rate (FPS)."""
        return self._fps

    def get_gesture_count(self) -> int:
        """Return total number of gestures recognized since startup."""
        return self._gesture_count


# Alias for EngineCoordinator mapping
EngineCoordinator = GestureEngine
