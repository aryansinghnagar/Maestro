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
from typing import Any
from collections.abc import Callable

# Try importing tomllib (Python 3.11+)
try:
    import tomllib
except ImportError:
    tomllib = None

# Try importing wasmtime
try:
    import wasmtime
except ImportError:
    wasmtime = None

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
    Path(__file__).parent / "builtin",  # Built-in plugins
    Path(__file__).parent.parent / "data" / "plugins",  # Bundled plugins
]

# User plugin directory (per-platform)
from gesture_controller.core.paths import user_plugin_dir
USER_PLUGIN_DIR = user_plugin_dir()

PLUGIN_DIRS.append(USER_PLUGIN_DIR)


class PluginLoadError(Exception):
    def __init__(self, plugin_path: str, reason: str) -> None:
        self.plugin_path = plugin_path
        self.reason = reason
        super().__init__(f"Failed to load plugin {plugin_path}: {reason}")


class Plugin:
    """Loaded plugin wrapper containing metadata, gestures, and action handlers."""

    def __init__(
        self,
        path: Path,
        module: Any,
        meta: dict,
        gestures: list[dict],
        actions: dict[str, Callable],
    ) -> None:
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
                "permissions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["os:input", "ui:hud", "camera:read", "config:read"],
                    },
                },
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
                        logger.warning(
                            "Duplicate plugin name, skipping",
                            name=plugin.meta["name"],
                            path=str(py_file),
                        )
                        continue
                    seen_names.add(plugin.meta["name"])
                    plugins.append(plugin)
                except PluginLoadError as e:
                    logger.warning("Plugin load failed", path=str(py_file), reason=e.reason)

            # Discover WASM plugins in subdirectories if tomllib and wasmtime are available
            if tomllib is not None and wasmtime is not None:
                for sub_dir in sorted(plugin_dir.iterdir()):
                    if sub_dir.is_dir() and (sub_dir / "maestro.toml").exists():
                        try:
                            plugin = self._load_wasm_plugin(sub_dir)
                            if plugin.meta["name"] in seen_names:
                                logger.warning(
                                    "Duplicate plugin name, skipping",
                                    name=plugin.meta["name"],
                                    path=str(sub_dir),
                                )
                                continue
                            seen_names.add(plugin.meta["name"])
                            plugins.append(plugin)
                        except PluginLoadError as e:
                            logger.warning(
                                "WASM plugin load failed", path=str(sub_dir), reason=e.reason
                            )

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
                            raise PluginLoadError(
                                str(path), f"PLUGIN_META must be a literal dict: {e}"
                            )
        return None

    def _scan_ast_for_unsafe_code(self, path: Path, permissions: list[str]) -> None:
        """Scan AST for unsafe imports or calls based on manifest permissions (S3-12)."""
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise PluginLoadError(str(path), f"Syntax error: {e}")

        # Block list of packages that require permissions
        blocked_packages = {
            "pyautogui",
            "ctypes",
            "evdev",
            "Quartz",
            "AppKit",
            "win32api",
            "win32con",
            "subprocess",
            "os",
            "sys",
            "socket",
            "pickle",
            "multiprocessing",
            "threading",
            "asyncio",
            "shutil",
            "pathlib",
            "tempfile",
            "glob",
            "urllib",
            "http",
            "ftplib",
            "smtplib",
            "telnetlib",
            "xmlrpc",
            "websocket",
            "requests",
            "httpx",
            "aiohttp",
            "builtins",
            "__builtin__",
        }

        # If "os:input" is granted, we allow input simulation libraries
        allowed_packages = {"typing", "structlog", "math", "numpy", "mediapipe"}
        if "os:input" in permissions:
            allowed_packages.update(
                {"pyautogui", "ctypes", "evdev", "Quartz", "AppKit", "win32api", "win32con"}
            )

        blocked_builtins = {
            "eval", "exec", "compile", "__import__", "globals", "locals",
            "vars", "dir", "getattr", "setattr", "delattr", "hasattr",
            "open", "input", "breakpoint", "exit", "quit", "__builtins__", "__builtin__"
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_mod = alias.name.split(".")[0]
                    if base_mod in blocked_packages and base_mod not in allowed_packages:
                        raise PluginLoadError(
                            str(path),
                            f"Unauthorized import of '{alias.name}'. Declared permissions do not allow it.",
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base_mod = node.module.split(".")[0]
                    if base_mod in blocked_packages and base_mod not in allowed_packages:
                        raise PluginLoadError(
                            str(path),
                            f"Unauthorized import from '{node.module}'. Declared permissions do not allow it.",
                        )
                for alias in node.names:
                    if alias.name in blocked_builtins:
                        raise PluginLoadError(
                            str(path),
                            f"Unauthorized import of blocked built-in '{alias.name}'.",
                        )

            # Block any reference to security-critical names
            if isinstance(node, ast.Name):
                if node.id in blocked_builtins:
                    raise PluginLoadError(
                        str(path),
                        f"Use of blocked security-critical identifier '{node.id}' is forbidden.",
                    )

            # Block any reference to security-critical attributes (e.g. __import__)
            if isinstance(node, ast.Attribute):
                if node.attr in {"__import__", "eval", "exec", "__builtins__", "__builtin__"}:
                    raise PluginLoadError(
                        str(path),
                        f"Access to blocked security-critical attribute '{node.attr}' is forbidden.",
                    )

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

        # 1.5 Scan AST for unsafe imports / calls (S3-12)
        self._scan_ast_for_unsafe_code(path, meta.get("permissions", []))

        # 1.7 Execute in RestrictedPython sandboxed execution environment
        module_name = f"gesture_controller.plugins.{path.stem}"
        try:
            from RestrictedPython import compile_restricted, safe_builtins
            from RestrictedPython.Eval import default_guarded_getattr
            from RestrictedPython.Guards import full_write_guard
            import types

            # Compile code under RestrictedPython rules
            source = path.read_text(encoding="utf-8")
            code = compile_restricted(source, filename=str(path), mode="exec")

            permissions = meta.get("permissions", [])

            ALLOWED_IMPORTS = {
                "time",
                "math",
                "json",
                "structlog",
                "numpy",
                "mediapipe",
                "typing",
            }

            PERMISSION_GATED_IMPORTS = {
                "pyautogui": "os:input",
                "ctypes": "os:input",
                "evdev": "os:input",
                "Quartz": "os:input",
                "AppKit": "os:input",
                "win32api": "os:input",
                "win32con": "os:input",
            }

            def guarded_import(
                name: str,
                globals: dict[str, Any] | None = None,
                locals: dict[str, Any] | None = None,
                fromlist: Any = (),
                level: int = 0,
            ) -> Any:
                base_mod = name.split(".")[0]
                if base_mod in ALLOWED_IMPORTS:
                    return __import__(name, globals, locals, fromlist, level)
                if base_mod in PERMISSION_GATED_IMPORTS:
                    required_permission = PERMISSION_GATED_IMPORTS[base_mod]
                    if required_permission in permissions:
                        return __import__(name, globals, locals, fromlist, level)
                    raise ImportError(
                        f"Unauthorized import of '{name}'. Declared permissions do not allow it."
                    )
                raise ImportError(
                    f"Import of module '{name}' is blocked by sandbox security policy."
                )

            # Create module namespace
            module = types.ModuleType(module_name)
            module.__file__ = str(path)

            builtins_dict = safe_builtins.copy()
            builtins_dict["__import__"] = guarded_import

            module_globals = module.__dict__
            module_globals.update(
                {
                    "__builtins__": builtins_dict,
                    "_getattr_": default_guarded_getattr,
                    "_write_": full_write_guard,
                    "_getiter_": lambda x: iter(x),
                    "_inplacevar_": lambda op, x, y: x,
                    "__name__": module_name,
                    "__file__": str(path),
                }
            )

            exec(code, module_globals)
            sys.modules[module_name] = module
        except Exception as e:
            raise PluginLoadError(str(path), f"RestrictedPython sandbox execution failed: {e}")

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
                    raise PluginLoadError(
                        str(path), f"Invalid GESTURE_DEFINITIONS at index {idx}: {e.message}"
                    )
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

    def _load_wasm_plugin(self, path: Path) -> Plugin:
        """Load and validate a directory-based WASM plugin with sandboxed wasmtime runtime."""
        if tomllib is None or wasmtime is None:
            raise PluginLoadError(str(path), "WASM runtime dependencies not installed")

        manifest_path = path / "maestro.toml"
        try:
            with open(manifest_path, "rb") as f:
                config = tomllib.load(f)
        except Exception as e:
            raise PluginLoadError(str(path), f"Failed to parse maestro.toml: {e}")

        # Construct meta and validate against schema
        try:
            meta = {
                "name": config["plugin"]["name"],
                "version": config["plugin"]["version"],
                "description": config["plugin"].get("description", ""),
                "author": config["plugin"].get("author", ""),
                "permissions": [k for k, v in config.get("capabilities", {}).items() if v],
            }
            jsonschema.validate(meta, self._schema)
        except KeyError as e:
            raise PluginLoadError(str(path), f"Missing key in maestro.toml: {e}")
        except jsonschema.ValidationError as e:
            raise PluginLoadError(str(path), f"Invalid metadata: {e.message}")

        wasm_path = path / "plugin.wasm"
        if not wasm_path.exists():
            wasm_path = path / "plugin.wat"
        if not wasm_path.exists():
            raise PluginLoadError(str(path), "Missing plugin.wasm or plugin.wat")

        # Compile WASM module
        try:
            engine = wasmtime.Engine()
            store = wasmtime.Store(engine)
            linker = wasmtime.Linker(engine)

            if wasm_path.suffix == ".wat":
                module = wasmtime.Module(engine, wasm_path.read_text(encoding="utf-8"))
            else:
                module = wasmtime.Module(engine, wasm_path.read_bytes())
        except Exception as e:
            raise PluginLoadError(str(wasm_path), f"WASM compilation failed: {e}")

        gestures: list[dict] = []

        # Helper to read strings from WASM memory
        def get_wasm_string(caller: Any, ptr: int, length: int) -> str:
            memory = caller.get("memory")
            if not memory:
                raise RuntimeError("WASM module does not export 'memory'")
            data = memory.read(caller, ptr, ptr + length)
            return data.decode("utf-8")

        # Define host imports
        def trigger_action(caller: Any, ptr: int, length: int) -> None:
            if "os:input" not in meta["permissions"]:
                raise PermissionError("Permission Denied: Plugin lacks 'os:input' capability")
            action = get_wasm_string(caller, ptr, length)
            logger.info("WASM plugin triggered action", plugin=meta["name"], action=action)
            self._event_bus.publish("action_triggered", action)

        def get_config(
            caller: Any, key_ptr: int, key_len: int, val_buf_ptr: int, val_buf_len: int
        ) -> int:
            if "config:read" not in meta["permissions"]:
                raise PermissionError("Permission Denied: Plugin lacks 'config:read' capability")
            key = get_wasm_string(caller, key_ptr, key_len)
            val = ""
            memory = caller.get("memory")
            if not memory:
                raise RuntimeError("WASM module does not export 'memory'")

            val_bytes = val.encode("utf-8")
            write_len = min(len(val_bytes), val_buf_len)
            memory.write(caller, val_bytes[:write_len], val_buf_ptr)
            return write_len

        def register_gesture(caller: Any, ptr: int, length: int) -> None:
            gesture_json = get_wasm_string(caller, ptr, length)
            try:
                gesture = json.loads(gesture_json)
                gesture_schema_path = (
                    Path(__file__).parent.parent / "data" / "gesture_schema.json"
                )
                if gesture_schema_path.exists():
                    with open(gesture_schema_path, "r") as f:
                        g_schema = json.load(f)
                    jsonschema.validate(gesture, g_schema)
                gestures.append(gesture)
            except Exception as e:
                logger.error("WASM plugin failed to register gesture", error=str(e))

        # Register functions in linker
        try:
            linker.define_func(
                "maestro",
                "trigger_action",
                wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []),
                trigger_action,
                access_caller=True,
            )
            linker.define_func(
                "maestro",
                "get_config",
                wasmtime.FuncType(
                    [
                        wasmtime.ValType.i32(),
                        wasmtime.ValType.i32(),
                        wasmtime.ValType.i32(),
                        wasmtime.ValType.i32(),
                    ],
                    [wasmtime.ValType.i32()],
                ),
                get_config,
                access_caller=True,
            )
            linker.define_func(
                "maestro",
                "register_gesture",
                wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []),
                register_gesture,
                access_caller=True,
            )
        except Exception as e:
            raise PluginLoadError(str(path), f"Failed to define host imports: {e}")

        # Instantiate module
        try:
            instance = linker.instantiate(store, module)
        except Exception as e:
            raise PluginLoadError(str(path), f"WASM instantiation failed: {e}")

        class WASMPluginWrapper:
            def __init__(self, store: Any, instance: Any) -> None:
                self.store = store
                self.instance = instance

            def init(self) -> None:
                exports = self.instance.exports(self.store)
                if "init" in exports:
                    exports["init"](self.store)

            def on_gesture(
                self, event_name: str, hand: str, confidence: float, timestamp: int
            ) -> None:
                exports = self.instance.exports(self.store)
                if "on_gesture" in exports:
                    memory = exports.get("memory")
                    if memory:
                        event_bytes = event_name.encode("utf-8")
                        memory.write(self.store, event_bytes, 1024)
                        hand_code = 1 if hand == "Right" else 0
                        exports["on_gesture"](
                            self.store,
                            1024,
                            len(event_bytes),
                            hand_code,
                            confidence,
                            timestamp,
                        )

        wrapper = WASMPluginWrapper(store, instance)

        # Call init to allow gesture registration
        try:
            wrapper.init()
        except Exception as e:
            raise PluginLoadError(str(path), f"Plugin init call failed: {e}")

        # Return custom Plugin wrapper
        return Plugin(path=path, module=wrapper, meta=meta, gestures=gestures, actions={})
