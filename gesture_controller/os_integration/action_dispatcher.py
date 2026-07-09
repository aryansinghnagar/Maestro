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

    def __init__(
        self, controller: BaseController, config: ConfigManager, event_bus: EventBus
    ) -> None:
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
            from typing import cast

            with open(path, "r") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return {}
            return cast(dict[str, dict[str, str]], data.get("app_profiles", {}))
        except Exception as e:
            logger.error("Failed to load profiles yaml", error=str(e))
            return {}

    def _on_gesture(self, event: GestureEvent) -> None:
        import time

        correlation_id = event.metadata.get("correlation_id", "")
        action_str = self._resolve_action(event)
        if not action_str:
            return

        # Set active gesture context on controller if supported (e.g. BrokerClientController)
        if hasattr(self._controller, "set_active_gesture"):
            self._controller.set_active_gesture(event.gesture_name)

        start_time = time.perf_counter()
        try:
            self._execute(action_str)
        finally:
            if hasattr(self._controller, "set_active_gesture"):
                self._controller.set_active_gesture(None)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        app_class = self._classify_app(event.app_profile or "")
        logger.info(
            "metric_dispatcher_latency_ms",
            gesture=event.gesture_name,
            action=action_str,
            app_class=app_class,
            latency_ms=latency_ms,
            correlation_id=correlation_id,
        )
        logger.info(
            "Action executed",
            gesture=event.gesture_name,
            action=action_str,
            app_class=app_class,
            correlation_id=correlation_id,
        )

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
            "arrowleft": "left",
            "arrowright": "right",
            "arrowup": "up",
            "arrowdown": "down",
            "win": "super",
            "windows": "super",
            "meta": "super",
            "enter": "return",
            "esc": "escape",
            "pageup": "page_up",
            "pagedown": "page_down",
            "pgup": "page_up",
            "pgdn": "page_down",
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

    def _classify_app(self, app_name: str) -> str:
        """Classify a raw app name into coarse categories for privacy protection."""
        if not app_name:
            return "unknown"
        app_lower = app_name.lower()
        if any(b in app_lower for b in ["chrome", "firefox", "safari", "edge", "opera", "browser"]):
            return "browser"
        if any(e in app_lower for e in ["code", "sublime", "notepad", "vim", "emacs", "editor"]):
            return "editor"
        if any(m in app_lower for m in ["vlc", "spotify", "itunes", "media", "player", "mpv"]):
            return "media"
        if any(
            c in app_lower
            for c in ["slack", "discord", "teams", "zoom", "skype", "whatsapp", "telegram"]
        ):
            return "communication"
        if any(g in app_lower for g in ["steam", "game", "minecraft"]):
            return "game"
        if any(
            s in app_lower
            for s in ["explorer", "finder", "system", "terminal", "bash", "cmd", "powershell"]
        ):
            return "system"
        return "unknown"
