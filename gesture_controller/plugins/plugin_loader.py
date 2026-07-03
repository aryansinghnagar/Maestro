import importlib.util
import ast
import json
import os
import sys
import time
import platform
import structlog
import jsonschema
from pathlib import Path
from typing import Any, Callable

# Try importing watchdog (only used for hot reloading)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = None

logger = structlog.get_logger(__name__)

# Plugin discovery directories
PLUGIN_DIRS = [
    Path(__file__).parent / "builtin",          # Built-in plugins
    Path(__file__).parent.parent / "data" / "plugins",  # Bundled plugins
]

# User plugin directory (per-platform)
if platform.system() == "Windows":
    USER_PLUGIN_DIR = Path(os.environ.get("APPDATA", "")) / "gesture_controller" / "plugins"
elif platform.system() == "Darwin":
    USER_PLUGIN_DIR = Path.home() / "Library" / "Application Support" / "gesture_controller" / "plugins"
else:
    USER_PLUGIN_DIR = Path.home() / ".config" / "gesture_controller" / "plugins"

PLUGIN_DIRS.append(USER_PLUGIN_DIR)

class PluginLoadError(Exception):
    def __init__(self, plugin_path: str, reason: str) -> None:
        self.plugin_path = plugin_path
        self.reason = reason
        super().__init__(f"Failed to load plugin {plugin_path}: {reason}")

class Plugin:
    """Loaded plugin wrapper containing metadata, gestures, and action handlers."""
    def __init__(self, path: Path, module: Any, meta: dict, gestures: list[dict], actions: dict[str, Callable]) -> None:
        self.path = path
        self.module = module
        self.meta = meta
        self.gestures = gestures
        self.actions = actions
        self.loaded_at = time.monotonic()

class PluginLoader:
    """Discovers, validates, and manages gesture/action plugins with hot-reloading capabilities."""

    def __init__(self, event_bus: Any, schema: dict | None = None) -> None:
        self._event_bus = event_bus
        self._plugins: dict[str, Plugin] = {}
        self._schema = schema or self._default_schema()
        self._observer: Any = None

    def _default_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["name", "version"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "version": {"type": "string"},
                "description": {"type": "string"},
                "author": {"type": "string"},
            },
        }

    def discover_all(self) -> list[Plugin]:
        """Scan all plugin directories and load valid plugins."""
        plugins = []
        seen_names = set()

        for plugin_dir in PLUGIN_DIRS:
            if not plugin_dir.exists():
                try:
                    plugin_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    continue

            for py_file in sorted(plugin_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                try:
                    plugin = self._load_plugin(py_file)
                    if plugin.meta["name"] in seen_names:
                        logger.warning("Duplicate plugin name, skipping", name=plugin.meta["name"], path=str(py_file))
                        continue
                    seen_names.add(plugin.meta["name"])
                    plugins.append(plugin)
                except PluginLoadError as e:
                    logger.warning("Plugin load failed", path=str(py_file), reason=e.reason)

        self._plugins = {p.meta["name"]: p for p in plugins}
        logger.info("Plugins loaded", count=len(plugins), names=[p.meta["name"] for p in plugins])
        return plugins

    def _extract_meta_without_exec(self, path: Path) -> dict | None:
        """Parse PLUGIN_META via AST without executing module code."""
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            raise PluginLoadError(str(path), f"Syntax error: {e}")
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "PLUGIN_META":
                        try:
                            return ast.literal_eval(node.value)
                        except (ValueError, SyntaxError) as e:
                            raise PluginLoadError(str(path), f"PLUGIN_META must be a literal dict: {e}")
        return None

    def _load_plugin(self, path: Path) -> Plugin:
        """Load and validate a single plugin file.

        SECURITY: Parse PLUGIN_META via AST BEFORE executing any module code.
        A malicious plugin cannot run module-level code unless its manifest
        passes schema validation first.
        """
        # 1. Validate manifest BEFORE executing any code
        meta = self._extract_meta_without_exec(path)
        if meta is None:
            raise PluginLoadError(str(path), "Missing PLUGIN_META")
        try:
            jsonschema.validate(meta, self._schema)
        except jsonschema.ValidationError as e:
            raise PluginLoadError(str(path), f"Invalid PLUGIN_META: {e.message}")

        # 2. Only execute after manifest is validated
        module_name = f"gesture_controller.plugins.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec is None or spec.loader is None:
            raise PluginLoadError(str(path), "Cannot create module spec")

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise PluginLoadError(str(path), f"Import error: {e}")
        sys.modules[module_name] = module

        # Re-read meta from the executed module (in case it was computed or customized)
        meta = getattr(module, "PLUGIN_META", meta)

        # 3. Validate GESTURE_DEFINITIONS if present
        gestures = getattr(module, "GESTURE_DEFINITIONS", [])
        if gestures:
            gesture_schema_path = Path(__file__).parent.parent / "data" / "gesture_schema.json"
            if gesture_schema_path.exists():
                try:
                    with open(gesture_schema_path, "r") as f:
                        g_schema = json.load(f)
                    for idx, gesture in enumerate(gestures):
                        jsonschema.validate(gesture, g_schema)
                except jsonschema.ValidationError as e:
                    # Clean up imported module from sys.modules on validation failure
                    sys.modules.pop(module_name, None)
                    raise PluginLoadError(str(path), f"Invalid GESTURE_DEFINITIONS at index {idx}: {e.message}")
                except Exception as e:
                    sys.modules.pop(module_name, None)
                    raise PluginLoadError(str(path), f"Failed to validate gestures: {e}")

        actions = getattr(module, "ACTION_HANDLERS", {})
        return Plugin(path=path, module=module, meta=meta, gestures=gestures, actions=actions)

    def start_hot_reload(self) -> None:
        """Watch plugin directories for changes and reload modified plugins."""
        if Observer is None or FileSystemEventHandler is None:
            logger.warning("watchdog module not loaded, hot reload disabled")
            return

        class PluginFileHandler(FileSystemEventHandler):
            def __init__(self, loader: "PluginLoader") -> None:
                self.loader = loader

            def on_modified(self, event: Any) -> None:
                src_path = Path(event.src_path)
                if src_path.suffix == ".py" and not src_path.name.startswith("_"):
                    logger.info("Plugin file modified, reloading", path=str(src_path))
                    try:
                        plugin = self.loader._load_plugin(src_path)
                        # Remove duplicate name if loaded from another location
                        for name, old_plugin in list(self.loader._plugins.items()):
                            if old_plugin.path.resolve() == src_path.resolve():
                                del self.loader._plugins[name]
                        self.loader._plugins[plugin.meta["name"]] = plugin
                        self.loader._event_bus.publish("plugin_reloaded", plugin.meta["name"])
                        logger.info("Plugin reloaded successfully", name=plugin.meta["name"])
                    except PluginLoadError as e:
                        logger.error("Hot reload failed", path=str(src_path), reason=e.reason)

        self._observer = Observer()
        handler = PluginFileHandler(self)
        for plugin_dir in PLUGIN_DIRS:
            if plugin_dir.exists():
                self._observer.schedule(handler, str(plugin_dir), recursive=False)
        self._observer.start()
        logger.info("Hot reload watcher started")

    def stop_hot_reload(self) -> None:
        """Stop filesystem observers."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None

    def get_all_gestures(self) -> list[dict]:
        """Collect gesture definitions from all loaded plugins."""
        gestures = []
        for plugin in self._plugins.values():
            gestures.extend(plugin.gestures)
        return gestures

    def get_action_handler(self, action_name: str) -> Any | None:
        """Find custom action handler across loaded plugins."""
        for plugin in self._plugins.values():
            if action_name in plugin.actions:
                return plugin.actions[action_name]
        return None
