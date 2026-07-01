import ast
import json
import os
import platform
import yaml
import jsonschema
import structlog
from pathlib import Path
from typing import Any, Callable

logger = structlog.get_logger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "data" / "default_config.yaml"

# User config locations per platform
USER_CONFIG_DIRS = {
    "Windows": Path(os.environ.get("APPDATA", "")) / "gesture_controller",
    "Darwin": Path.home() / "Library" / "Application Support" / "gesture_controller",
    "Linux": Path.home() / ".config" / "gesture_controller",
}

class SafeExpressionEvaluator:
    """A safe AST-based compiler and evaluator for boolean expression strings.
    It restricts AST node types to an allow-list to prevent arbitrary code execution."""

    ALLOWED_NODES = {
        ast.Expression,
        ast.BoolOp,
        ast.Compare,
        ast.Name,
        ast.Constant,
        ast.UnaryOp,
        # Operators
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Is,
        ast.IsNot,
        ast.Not,
        ast.USub,
        # Context
        ast.Load,
    }

    @classmethod
    def validate_node(cls, node: ast.AST) -> None:
        """Recursively check if the AST nodes are in the allow-list."""
        if type(node) not in cls.ALLOWED_NODES:
            raise ValueError(f"AST node type '{type(node).__name__}' is not allowed for security reasons.")
        for child in ast.iter_child_nodes(node):
            cls.validate_node(child)

    @classmethod
    def compile_expression(cls, expr_str: str) -> Any:
        """Parse, validate and compile a safe expression string into a code object."""
        try:
            # Parse in 'eval' mode (expects a single expression)
            tree = ast.parse(expr_str.strip(), mode='eval')
            cls.validate_node(tree)
            return compile(tree, filename="<safe_eval>", mode="eval")
        except Exception as e:
            raise ValueError(f"Unsafe or invalid condition string: '{expr_str}'. Error: {e}")

    @classmethod
    def evaluate(cls, compiled_code: Any, context: dict[str, Any]) -> bool:
        """Evaluate pre-compiled safe code with the given context variables."""
        try:
            # Run eval with absolutely no builtins
            return bool(eval(compiled_code, {"__builtins__": None}, context))
        except Exception as e:
            logger.warning("Failed to evaluate pre-compiled condition", error=str(e))
            return False


class ConfigManager:
    """Manages system configuration loading, schema validation, and merging user overrides."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config: dict[str, Any] = {}
        self._schema: dict[str, Any] = {}
        self._load_schema()
        self._load_config(config_path)

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
        sys_name = platform.system()
        user_dir = USER_CONFIG_DIRS.get(sys_name)
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
