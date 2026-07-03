import threading
import time
import platform
import numpy as np
import yaml
from pathlib import Path
from typing import Any
import structlog
from multiprocessing import shared_memory

from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.event_bus import EventBus
from gesture_controller.vision.camera_stream import start_camera_process
from gesture_controller.vision.landmark_extractor import LandmarkExtractor
from gesture_controller.vision.one_euro_filter import OneEuroFilter
from gesture_controller.models.feature_engineering import compute_features
from gesture_controller.models.data_types import Hand, Landmark3D, FeatureVector, GestureEvent
from gesture_controller.core.state_machine import GestureFSMManager
from gesture_controller.plugins.plugin_loader import PluginLoader
from gesture_controller.models.dtw_matcher import CustomGestureMatcher
from gesture_controller.os_integration.action_dispatcher import ActionDispatcher

logger = structlog.get_logger(__name__)

class GestureEngine:
    """Master daemon coordinator. Coordinates Process A and Process B pipeline flow."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config = ConfigManager(config_path)
        self._event_bus = EventBus()
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._frame_count = 0
        self._current_hands: list[Hand] = []
        self._fps = 0.0
        self._last_fps_time = time.monotonic()
        self._fps_frame_count = 0
        self._gesture_count = 0

        # Initialize PluginLoader
        self._plugin_loader = PluginLoader(self._event_bus)
        self._plugin_loader.discover_all()
        plugin_gestures = self._plugin_loader.get_all_gestures()

        # Initialize CustomGestureMatcher
        self._custom_matcher = CustomGestureMatcher(self._config._config)

        # Load predefined gestures YAML config
        gestures_yaml_path = Path(__file__).parent.parent / "data" / "predefined_gestures.yaml"
        gestures_config = {}
        if gestures_yaml_path.exists():
            try:
                with open(gestures_yaml_path, "r") as f:
                    gestures_config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error("Failed loading predefined_gestures.yaml in engine", error=str(e))

        # Merge predefined gestures with plugin gestures
        predefined_list = gestures_config.get("gestures", [])
        combined_gestures = predefined_list + plugin_gestures
        gestures_config["gestures"] = combined_gestures

        # Merge configs so FSMManager gets global engine defaults and gesture lists
        merged_config = self._config._config.copy()
        merged_config.update(gestures_config)

        # 1. Create SharedMemory segment for frame exchanging
        self._frame_size = 640 * 480 * 3
        self._frame_shm = shared_memory.SharedMemory(create=True, size=self._frame_size)
        self._shm_name = self._frame_shm.name
        logger.info("Shared memory buffer created", name=self._shm_name, size=self._frame_size)

        # 2. Spawn Camera Stream capture process (Process A)
        self._camera_process = start_camera_process(self._config._config, self._shm_name)
        logger.info("Camera Stream process spawned")

        # 3. Initialize Landmark Extractor (Process B)
        self._extractor = LandmarkExtractor(self._config._config)

        # 4. Initialize One-Euro Filters dict
        self._filters: dict[str, OneEuroFilter] = {}

        # 5. Initialize Gesture FSM Manager
        self._fsm_manager = GestureFSMManager(merged_config, self._event_bus)
        
        # Subscribe to plugin reloads to dynamically rebuild the FSM instances
        self._event_bus.subscribe("plugin_reloaded", self._on_plugin_reloaded)

        # 6. Instantiate Platform Controller
        self._controller = self._create_os_controller()

        # 7. Initialize Action Dispatcher (Subscribes to gesture_triggered on event_bus)
        self._dispatcher = ActionDispatcher(self._controller, self._config, self._event_bus)

        # Register signal handlers for graceful shutdown (SIGINT/SIGTERM)
        import signal
        try:
            self._old_sigint = signal.signal(signal.SIGINT, self._handle_signal)
            self._old_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            self._old_sigint = None
            self._old_sigterm = None

    def _handle_signal(self, signum: int, frame: Any) -> None:
        import sys
        import signal
        logger.info("Signal received, shutting down...", signal=signum)
        self.shutdown()
        
        # Restore old handler and forward signal, or exit
        old_handler = self._old_sigint if signum == signal.SIGINT else self._old_sigterm
        if old_handler and old_handler is not signal.SIG_DFL and old_handler is not signal.SIG_IGN:
            if callable(old_handler):
                old_handler(signum, frame)
        else:
            sys.exit(128 + signum)

    def _create_os_controller(self) -> Any:
        """Create OS Controller appropriate for the platform."""
        current_os = platform.system()
        try:
            from gesture_controller.os_integration import create_controller
            return create_controller()
        except Exception as e:
            logger.warning("Failed to create platform controller, falling back to dummy controller", error=str(e), os=current_os)
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


    def _on_plugin_reloaded(self, plugin_name: str) -> None:
        """Handle plugin reload event by re-fetching and reloading FSM templates."""
        logger.info("Handling plugin reload in engine", plugin=plugin_name)
        plugin_gestures = self._plugin_loader.get_all_gestures()
        gestures_yaml_path = Path(__file__).parent.parent / "data" / "predefined_gestures.yaml"
        gestures_config = {}
        if gestures_yaml_path.exists():
            try:
                with open(gestures_yaml_path, "r") as f:
                    gestures_config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error("Failed loading predefined_gestures.yaml during FSM reload", error=str(e))

        predefined_list = gestures_config.get("gestures", [])
        combined_gestures = predefined_list + plugin_gestures
        gestures_config["gestures"] = combined_gestures

        merged_config = self._config._config.copy()
        merged_config.update(gestures_config)
        self._fsm_manager.reload_gestures(merged_config)

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
        self._thread = threading.Thread(target=self._main_loop, daemon=True, name="engine_loop")
        self._thread.start()
        logger.info("GestureEngine main thread started")

    def _main_loop(self) -> None:
        """Internal main loop retrieving frames, running inference, and evaluating FSMs."""
        while self._running:
            try:
                if self._paused:
                    time.sleep(0.01)
                    continue
                
                # Rolling FPS calculation
                self._fps_frame_count += 1
                now = time.monotonic()
                if now - self._last_fps_time >= 1.0:
                    self._fps = self._fps_frame_count / (now - self._last_fps_time)
                    self._fps_frame_count = 0
                    self._last_fps_time = now

                timestamp = now
                hands = self._extractor.extract(self._shm_name, int(timestamp * 1000))
                
                if hands:
                    # Publish raw landmarks (useful for debug overlays/visualizers)
                    self._event_bus.publish("raw_landmarks", hands)
                    
                    smoothed_hands = []
                    for hand in hands:
                        # Convert hand landmarks to numpy coordinates
                        lm_array = np.array([[l.x, l.y, l.z] for l in hand.landmarks], dtype=np.float64)
                        
                        # Get or create One-Euro filter per hand/handedness
                        filt = self._filters.get(hand.handedness)
                        if filt is None:
                            filt = OneEuroFilter(self._config._config)
                            self._filters[hand.handedness] = filt

                        # Depth metric: Wrist to Index MCP length
                        mcp5 = lm_array[5]
                        wrist = lm_array[0]
                        depth_metric = float(np.linalg.norm(mcp5 - wrist))
                        
                        # 1. Apply One-Euro filter
                        filtered, velocity, acceleration = filt.filter(
                            lm_array, 
                            timestamp,
                            lighting_metric=None,
                            depth_metric=depth_metric
                        )
                        
                        # 2. Reconstruct Hand with filtered positions
                        smoothed_landmarks = tuple(
                            Landmark3D(x=f[0], y=f[1], z=f[2]) for f in filtered
                        )
                        smoothed_hand = Hand(
                            landmarks=smoothed_landmarks,
                            handedness=hand.handedness,
                            confidence=hand.confidence
                        )
                        smoothed_hands.append(smoothed_hand)
                        
                        # 3. Compute invariant features
                        features = compute_features(
                            smoothed_hand, 
                            velocity, 
                            acceleration, 
                            timestamp, 
                            self._frame_count
                        )
                        
                        # Update CustomGestureMatcher rolling buffer
                        self._custom_matcher.update_buffer(smoothed_hand)

                        # 4. Evaluate FSM transitions
                        event = self._fsm_manager.evaluate(features)
                        if not event:
                            event = self._custom_matcher.match(timestamp)

                        if event:
                            # Propagate trigger to subscribers (dispatcher is subscribed to this)
                            self._event_bus.publish("gesture_triggered", event)
                            self._gesture_count += 1
                            logger.info("Gesture Triggered", gesture=event.gesture_name, action=event.action)
                    self._current_hands = smoothed_hands
                else:
                    self._current_hands = []
                    # Reset filters, FSMs, and custom matcher immediately when hand is lost to prevent drift/lag
                    for f in self._filters.values():
                        f.reset()
                    self._fsm_manager.reset_all()
                    self._custom_matcher.reset()

                self._frame_count += 1
            except Exception as e:
                logger.error("Error inside engine main loop", error=str(e))
            # Sleep 1ms to allow CPU context switching, max ~1000 Hz polling rate
            time.sleep(0.001)

    def shutdown(self) -> None:
        """Gracefully shuts down background engine thread, camera process and SharedMemory."""
        logger.info("Shutting down GestureEngine...")
        self._running = False
        
        # Stop plugin hot reloading
        self._plugin_loader.stop_hot_reload()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        # Try to join camera stream process cleanly
        if self._camera_process.is_alive():
            self._camera_process.join(timeout=2.0)
            if self._camera_process.is_alive():
                logger.warning("Camera stream process did not stop cleanly, terminating...")
                self._camera_process.terminate()
                self._camera_process.join()

        # Close MediaPipe Hands
        self._extractor.close()

        # Tear down shared memory segment
        try:
            self._frame_shm.close()
            self._frame_shm.unlink()
            logger.info("Shared memory segment cleanly unlinked")
        except Exception as e:
            logger.error("Failed unlinking shared memory segment during shutdown", error=str(e))

    def get_current_hands(self) -> list[Hand]:
        """Return the latest detected and filtered Hand data."""
        return list(self._current_hands)

    def get_fsm_states(self) -> dict[str, tuple[str, float]]:
        """Return states of all FSMs."""
        return self._fsm_manager.get_states()

    def get_fps(self) -> float:
        """Return the current frame processing rate (FPS)."""
        return self._fps

    def get_gesture_count(self) -> int:
        """Return total number of gestures recognized since startup."""
        return self._gesture_count
