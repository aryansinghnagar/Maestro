import yaml
from pathlib import Path
from typing import Any
import structlog

from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.state_machine import GestureFSMManager
from gesture_controller.models.dtw_matcher import CustomGestureMatcher

logger = structlog.get_logger(__name__)


class GestureRecognizer:
    """Manages FSM state machines, DTW templates, and gesture event matching."""

    def __init__(
        self, config: ConfigManager, event_bus: EventBus, plugin_loader: Any = None
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._plugin_loader = plugin_loader
        self._custom_matchers: dict[int, CustomGestureMatcher] = {}
        self._fsm_manager: GestureFSMManager | None = None
        self._custom_matcher: CustomGestureMatcher | None = None

        self._init_fsm()
        self._init_custom_gesture_matcher()

        self._event_bus.subscribe("plugin_reloaded", self._on_plugin_reloaded)

    def _init_fsm(self, plugin_gestures: list[Any] | None = None) -> None:
        if plugin_gestures is None:
            plugin_gestures = self._plugin_loader.get_all_gestures() if self._plugin_loader else []

        gestures_yaml_path = Path(__file__).parent.parent / "data" / "predefined_gestures.yaml"
        gestures_config: dict[str, Any] = {}
        if gestures_yaml_path.exists():
            try:
                with open(gestures_yaml_path, "r") as f:
                    gestures_config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error("Failed loading predefined_gestures.yaml in recognizer", error=str(e))

        predefined_list = gestures_config.get("gestures", [])
        combined_gestures = predefined_list + plugin_gestures
        gestures_config["gestures"] = combined_gestures

        merged_config = self._config._config.copy()
        merged_config.update(gestures_config)

        if self._fsm_manager is None:
            self._fsm_manager = GestureFSMManager(merged_config, self._event_bus)
        else:
            self._fsm_manager.reload_gestures(merged_config)

    def _init_custom_gesture_matcher(self) -> None:
        self._custom_matcher = CustomGestureMatcher(self._config._config)
        original_load = self._custom_matcher.load_templates

        def wrapped_load(*args: Any, **kwargs: Any) -> Any:
            res = original_load(*args, **kwargs)
            self._custom_matchers.clear()
            return res

        self._custom_matcher.load_templates = wrapped_load  # type: ignore[method-assign]

    def _on_plugin_reloaded(self, plugin_name: str) -> None:
        logger.info("Handling plugin reload in recognizer", plugin=plugin_name)
        plugin_gestures = self._plugin_loader.get_all_gestures() if self._plugin_loader else []
        self._init_fsm(plugin_gestures)
        self._custom_matchers.clear()

    def evaluate(
        self, track_id: int, features: Any, hand: Any, timestamp: float, correlation_id: str
    ) -> Any:
        assert self._fsm_manager is not None
        matcher = self._custom_matchers.get(track_id)
        if matcher is None:
            matcher = CustomGestureMatcher(self._config._config)
            self._custom_matchers[track_id] = matcher

        matcher.update_buffer(hand)

        event = self._fsm_manager.evaluate(features, correlation_id, track_id=track_id)
        if not event:
            event = matcher.match(timestamp, correlation_id)

        return event

    def remove_hand(self, track_id: int) -> None:
        self._custom_matchers.pop(track_id, None)
        if self._fsm_manager:
            self._fsm_manager.remove_hand(track_id)

    def reset(self) -> None:
        if self._fsm_manager:
            self._fsm_manager.reset_all()
        for m in self._custom_matchers.values():
            m.reset()
        self._custom_matchers.clear()

    def get_fsm_states(self) -> dict[str, tuple[str, float]]:
        if self._fsm_manager:
            return self._fsm_manager.get_states()
        return {}
