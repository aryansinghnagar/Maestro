import re
import yaml
import structlog
from pathlib import Path
from typing import Any

from gesture_controller.models.data_types import GestureEvent
from gesture_controller.os_integration.base_controller import BaseController
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.event_bus import EventBus

logger = structlog.get_logger(__name__)

class ActionDispatcher:
    """Routes GestureEvent to the appropriate BaseController method."""

    def __init__(self, controller: BaseController, config: ConfigManager, event_bus: EventBus) -> None:
        self._controller = controller
        self._config = config
        self._profiles = self._load_profiles()
        
        event_bus.subscribe("gesture_triggered", self._on_gesture)
        logger.info("ActionDispatcher initialized")

    def _load_profiles(self) -> dict[str, dict[str, str]]:
        """Load profiles from predefined_gestures.yaml."""
        path = Path(__file__).parent.parent / "data" / "predefined_gestures.yaml"
        if not path.exists():
            logger.warning("predefined_gestures.yaml not found, no app profiles loaded")
            return {}
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return data.get("app_profiles", {})
        except Exception as e:
            logger.error("Failed to load profiles yaml", error=str(e))
            return {}

    def _on_gesture(self, event: GestureEvent) -> None:
        action_str = self._resolve_action(event)
        if not action_str:
            return
        
        self._execute(action_str)
        logger.info("Action executed", gesture=event.gesture_name, action=action_str, app=event.app_profile)

    def _resolve_action(self, event: GestureEvent) -> str:
        """Resolve gesture action to app-specific commands if enabled."""
        if not self._config.get("profiles", {}).get("auto_detect_app", True):
            return event.action

        foreground = self._controller.get_foreground_app()
        # Try matching active foreground process name
        if foreground and foreground in self._profiles:
            if event.gesture_name in self._profiles[foreground]:
                event.app_profile = foreground
                return self._profiles[foreground][event.gesture_name]

        # Fallback to default profiles
        if "_default" in self._profiles:
            if event.gesture_name in self._profiles["_default"]:
                event.app_profile = "_default"
                return self._profiles["_default"][event.gesture_name]

        return event.action

    def _execute(self, action_str: str) -> None:
        """Parse action string and execute corresponding OS stimulation."""
        parts = action_str.split(":", 1)
        if len(parts) != 2:
            logger.error("Invalid action string format", action=action_str)
            return

        action_type, action_value = parts[0], parts[1]

        if action_type == "OS":
            self._execute_os(action_value)
        elif action_type == "KeyPress":
            self._execute_keypress(action_value)
        elif action_type == "MouseClick":
            self._execute_mouse_click(action_value)
        elif action_type == "MouseScroll":
            self._execute_scroll(action_value)
        elif action_type == "Media":
            self._execute_media(action_value)
        else:
            logger.error("Unknown action type", type=action_type)

    def _execute_os(self, action: str) -> None:
        dispatch = {
            "MinimizeActiveWindow": self._controller.minimize_active_window,
            "SwitchWindow": self._controller.switch_window,
            "ShowDesktop": self._controller.show_desktop,
        }
        fn = dispatch.get(action)
        if fn:
            fn()
        else:
            logger.error("Unknown OS action", action=action)

    def _normalize_key(self, key: str) -> str:
        aliases = {
            "arrowleft": "left", "arrowright": "right",
            "arrowup": "up", "arrowdown": "down",
            "win": "super", "windows": "super", "meta": "super",
            "enter": "return", "esc": "escape",
            "pageup": "page_up", "pagedown": "page_down",
            "pgup": "page_up", "pgdn": "page_down",
        }
        k = key.strip().lower()
        return aliases.get(k, k)

    def _execute_keypress(self, keys_str: str) -> None:
        keys = [self._normalize_key(k) for k in keys_str.split("+")]
        self._controller.key_combo(keys)

    def _execute_mouse_click(self, button: str) -> None:
        self._controller.mouse_click(button=button.lower())

    def _execute_scroll(self, delta_str: str) -> None:
        try:
            delta = int(delta_str)
            self._controller.mouse_scroll(delta_y=delta)
        except ValueError:
            logger.error("Invalid scroll delta value", delta=delta_str)

    def _execute_media(self, action: str) -> None:
        dispatch = {
            "PlayPause": self._controller.media_play_pause,
            "Next": self._controller.media_next,
            "Previous": self._controller.media_previous,
            "VolumeUp": self._controller.media_volume_up,
            "VolumeDown": self._controller.media_volume_down,
        }
        fn = dispatch.get(action)
        if fn:
            fn()
        else:
            logger.error("Unknown Media action", action=action)
