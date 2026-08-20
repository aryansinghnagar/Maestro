import ast
import json
import os
import platform
import threading
import time
import yaml
import jsonschema
import structlog
from pathlib import Path
from typing import Any, Callable, Optional

from gesture_controller.core.paths import user_config_dir
from gesture_controller.core.expression_evaluator import SafeExpressionEvaluator

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "data" / "default_config.yaml"

# Performance optimization (P6): how long to wait after the last filesystem
# event before re-loading the config. Editors that save via atomic-rename
# (vim, gedit, VS Code) can fire 2-3 events in quick succession during a
# single user save; debouncing collapses them into one reload.
_CONFIG_RELOAD_DEBOUNCE_SECONDS = 0.5


class ConfigManager:
    """Manages system configuration loading, schema validation, and merging user overrides.

    Performance optimization (P6): optional file-watch support allows
    subsystems to subscribe to live config changes via the EventBus.
    A ``config_reloaded`` event is emitted whenever the user-config file
    changes on disk (subject to a 0.5s debounce so multi-event atomic
    saves don't trigger redundant reloads).
    """

    def __init__(
        self,
        config_path: Path | None = None,
        event_bus: Optional[Any] = None,
        enable_watch: bool = False,
    ) -> None:
        self._config: dict[str, Any] = {}
        self._schema: dict[str, Any] = {}
        self._event_bus = event_bus
        self._load_schema()
        self._load_config(config_path)

        # P6: optional file-watch state. Lazily created in start_watching().
        self._watch_observer: Optional[Any] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop = threading.Event()
        self._last_change_at: float = 0.0
        self._watch_lock = threading.Lock()
        self._watched_paths: list[Path] = []
        if enable_watch:
            self.start_watching(config_path)

    def _load_schema(self) -> None:
        schema_path = Path(__file__).parent.parent / "data" / "config_schema.json"
        if schema_path.exists():
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    self._schema = json.load(f)
            except Exception as e:
                logger.error("Failed to load config JSON schema", error=str(e))

    def _load_config(self, config_path: Path | None = None) -> None:
        paths: list[Path] = []
        if config_path:
            paths.append(config_path)

        # Add system defaults path
        paths.append(DEFAULT_CONFIG_PATH)

        # Add user overrides path
        user_dir = user_config_dir()
        if user_dir:
            paths.append(user_dir / "config.yaml")

        # Load and merge configurations (later paths override earlier ones)
        # Note: We merge default first, then user, so user overrides defaults.
        # But paths list is [custom_arg, default, user]. We want: default first, then custom_arg / user.
        # Let's order them properly: defaults first, then user, then custom arg if provided.
        ordered_paths: list[Path] = []
        if DEFAULT_CONFIG_PATH.exists():
            ordered_paths.append(DEFAULT_CONFIG_PATH)

        if user_dir:
            user_path = user_dir / "config.yaml"
            if user_path.exists():
                try:
                    with open(user_path, "r", encoding="utf-8") as f:
                        user_data = yaml.safe_load(f) or {}

                    from gesture_controller.core.config_migrator import migrate_config

                    migrated_data = migrate_config(user_data)

                    if migrated_data != user_data:
                        with open(user_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(migrated_data, f)
                        logger.info("Migrated user config file on disk", path=str(user_path))
                except Exception as e:
                    logger.warning(
                        "Failed to migrate user config file on disk",
                        path=str(user_path),
                        error=str(e),
                    )
                ordered_paths.append(user_path)

        if config_path and config_path.exists() and config_path not in ordered_paths:
            ordered_paths.append(config_path)

        for p in ordered_paths:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._deep_merge(self._config, data)
            except Exception as e:
                logger.warning("Failed to load config file", path=str(p), error=str(e))

        # Validate against schema if available
        if self._schema:
            try:
                jsonschema.validate(self._config, self._schema)
            except jsonschema.ValidationError as e:
                logger.error("Config validation failed against JSON schema", error=str(e.message))
                raise

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        """Deeply merges override dictionary into base dictionary."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation, e.g., 'camera.device_id'."""
        keys = key.split(".")
        val: Any = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation."""
        keys = key.split(".")
        d = self._config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    # --- Public accessor for the merged config dict --------------------------
    #
    # Audit fix MAE-ARCH-001: previously, modules that needed the *entire*
    # merged config dict (rather than a single dotted key) reached across
    # encapsulation to read ``config_manager._config`` directly. That
    # tight coupling made it impossible to later swap the storage format
    # (e.g., for hot-reload, versioned snapshots, or a typed dataclass)
    # without touching every consumer.
    #
    # ``as_dict()`` returns the same dict object that ``get()`` reads from.
    # Consumers receive a *live* reference (not a copy) for backward
    # compatibility with code that mutated the dict in place. A future
    # hardening pass should switch callers to ``get()`` + ``set()`` and
    # then return an immutable view from this method.

    def as_dict(self) -> dict[str, Any]:
        """Return the live, merged configuration dict.

        Audit fix MAE-ARCH-001: public accessor replacing cross-module
        access to the private ``_config`` attribute.
        """
        return self._config

    # --- P6: Config Hot-Reload ------------------------------------------------
    #
    # The hot-reload subsystem uses the ``watchdog`` library (already a
    # project dependency) to observe the user-config directory for file
    # modifications. When a change is detected, a debounce thread waits
    # ``_CONFIG_RELOAD_DEBOUNCE_SECONDS`` for further events (collapsing
    # multi-event atomic saves), then re-runs ``_load_config`` and emits
    # a ``config_reloaded`` event on the EventBus so subsystems (engine,
    # frame_pipeline, gesture_recognizer, etc.) can reload their derived
    # state without restarting the application.

    def start_watching(self, config_path: Path | None = None) -> None:
        """Begin watching the user-config file for on-disk changes.

        No-op if a watcher is already running. Safe to call multiple times.
        Requires ``watchdog`` to be importable; logs and returns silently
        if it is not (e.g., on a read-only filesystem).
        """
        if self._watch_observer is not None or self._watch_thread is not None:
            return  # already watching

        try:
            from watchdog.observers import Observer  # type: ignore[import-untyped]
            from watchdog.events import FileSystemEventHandler  # type: ignore[import-untyped]
        except ImportError as e:
            logger.warning(
                "Config hot-reload disabled: watchdog not importable",
                error=str(e),
            )
            return

        # Build the set of paths to watch. We always watch the user-config
        # directory; if a custom config_path is set we watch its parent too.
        watch_dirs: set[Path] = set()
        user_dir = user_config_dir()
        if user_dir and user_dir.exists():
            watch_dirs.add(user_dir)
        if config_path and config_path.exists():
            watch_dirs.add(config_path.parent)
        self._watched_paths = sorted(watch_dirs)
        if not self._watched_paths:
            logger.info("Config hot-reload: no watchable directories; skipping")
            return

        manager = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):  # type: ignore[override]
                if event.is_directory:
                    return
                manager._on_config_file_changed(Path(event.src_path))

            def on_created(self, event):  # type: ignore[override]
                if event.is_directory:
                    return
                manager._on_config_file_changed(Path(event.src_path))

        observer = Observer()
        for d in self._watched_paths:
            observer.schedule(_Handler(), str(d), recursive=False)
        observer.start()
        self._watch_observer = observer

        # Debounce thread: waits for quiet period, then reloads.
        self._watch_stop.clear()
        self._watch_thread = threading.Thread(
            target=self._debounce_loop, name="config_hot_reload", daemon=True
        )
        self._watch_thread.start()
        logger.info(
            "Config hot-reload watching directories",
            paths=[str(p) for p in self._watched_paths],
            debounce_seconds=_CONFIG_RELOAD_DEBOUNCE_SECONDS,
        )

    def _on_config_file_changed(self, path: Path) -> None:
        """Called by watchdog when a file in a watched directory changes."""
        # Only react to yaml files (ignore .swp, .tmp, editor backups, etc.)
        # and only if the path looks like our user-config file.
        if path.suffix.lower() not in (".yaml", ".yml"):
            return
        # Trigger the debounce regardless of which file changed — the
        # schema file, default config, or user config all warrant a reload.
        self._last_change_at = time.monotonic()

    def _debounce_loop(self) -> None:
        """Debounce thread: wait for filesystem events to settle, then reload.

        Watches ``self._last_change_at``; if no new events arrive for
        ``_CONFIG_RELOAD_DEBOUNCE_SECONDS``, performs the reload and emits
        the ``config_reloaded`` signal. Exits when ``stop_watching`` is
        called.
        """
        while not self._watch_stop.is_set():
            time.sleep(0.1)
            with self._watch_lock:
                last = self._last_change_at
            if last == 0.0:
                continue
            if (time.monotonic() - last) < _CONFIG_RELOAD_DEBOUNCE_SECONDS:
                continue
            # Quiet period elapsed; perform the reload exactly once.
            with self._watch_lock:
                if self._last_change_at == 0.0:
                    continue
                self._last_change_at = 0.0
            try:
                self._reload_and_emit()
            except Exception as e:
                logger.error("Config hot-reload failed", error=str(e))

    def _reload_and_emit(self) -> None:
        """Re-run ``_load_config`` and emit the ``config_reloaded`` signal."""
        # Preserve the original dict identity so any consumer holding a
        # reference via ``as_dict()`` sees the update (the in-place merge
        # in ``_load_config`` mutates ``self._config``).
        # Clear the existing merged state and re-merge from defaults+user.
        self._config.clear()
        # Re-run the schema load too in case the schema file itself changed.
        self._load_schema()
        self._load_config(None)
        logger.info("Config hot-reload complete")
        if self._event_bus is not None:
            try:
                self._event_bus.publish("config_reloaded", self._config)
            except Exception as e:
                logger.error("Failed to emit config_reloaded event", error=str(e))

    def stop_watching(self) -> None:
        """Stop the file-watch thread and release watchdog resources."""
        self._watch_stop.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=2.0)
            self._watch_thread = None
        if self._watch_observer is not None:
            try:
                self._watch_observer.stop()
                self._watch_observer.join(timeout=2.0)
            except Exception as e:
                logger.debug("Error stopping config watcher", error=str(e))
            self._watch_observer = None
        self._watched_paths = []
