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
    It restricts AST node types to an allow-list and evaluates expressions recursively,
    guaranteeing zero calls to eval()."""

    ALLOWED_NODES = {
        ast.Expression,
        ast.BoolOp,
        ast.Compare,
        ast.Name,
        ast.Constant,
        ast.UnaryOp,
        ast.BinOp,
        ast.Call,
        # Operators
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Not,
        ast.USub,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        # Context
        ast.Load,
    }

    @classmethod
    def validate_node(cls, node: ast.AST) -> None:
        """Recursively check if the AST nodes are in the allow-list."""
        if type(node) not in cls.ALLOWED_NODES:
            raise ValueError(
                f"AST node type '{type(node).__name__}' is not allowed for security reasons."
            )
        # If it's a function call, restrict the function name to allowed names only (e.g. abs)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in {"abs"}:
                func_name = node.func.id if isinstance(node.func, ast.Name) else "complex"
                raise ValueError(
                    f"Function call to '{func_name}' is not allowed for security reasons."
                )
        for child in ast.iter_child_nodes(node):
            cls.validate_node(child)

    @classmethod
    def compile_expression(cls, expr_str: str) -> ast.Expression:
        """Parse, validate and compile a safe expression string into an AST Expression."""
        try:
            tree = ast.parse(expr_str.strip(), mode="eval")
            cls.validate_node(tree)
            return tree
        except Exception as e:
            raise ValueError(f"Unsafe or invalid condition string: '{expr_str}'. Error: {e}")

    @classmethod
    def evaluate(cls, compiled_ast: ast.Expression, context: dict[str, Any]) -> bool:
        """Evaluate pre-compiled safe AST with the given context variables."""
        try:
            return bool(cls._evaluate_node(compiled_ast.body, context))
        except Exception as e:
            logger.warning("metric_condition_eval_exception", error=str(e))
            return False

    @classmethod
    def _evaluate_node(cls, node: ast.AST, context: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        elif isinstance(node, ast.Name):
            if node.id == "True":
                return True
            if node.id == "False":
                return False
            if node.id in context:
                return context[node.id]
            raise NameError(f"Name '{node.id}' is not defined in context.")

        elif isinstance(node, ast.UnaryOp):
            operand = cls._evaluate_node(node.operand, context)
            if isinstance(node.op, ast.Not):
                return not operand
            elif isinstance(node.op, ast.USub):
                return -operand
            raise TypeError(f"Unsupported unary operator: {type(node.op)}")

        elif isinstance(node, ast.BinOp):
            left = cls._evaluate_node(node.left, context)
            right = cls._evaluate_node(node.right, context)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
            elif isinstance(node.op, ast.Mod):
                return left % right
            raise TypeError(f"Unsupported binary operator: {type(node.op)}")

        elif isinstance(node, ast.BoolOp):
            # Short-circuit evaluation
            if isinstance(node.op, ast.And):
                for val_node in node.values:
                    if not cls._evaluate_node(val_node, context):
                        return False
                return True
            elif isinstance(node.op, ast.Or):
                for val_node in node.values:
                    if cls._evaluate_node(val_node, context):
                        return True
                return False
            raise TypeError(f"Unsupported logical operator: {type(node.op)}")

        elif isinstance(node, ast.Compare):
            left = cls._evaluate_node(node.left, context)
            for op, comparator_node in zip(node.ops, node.comparators):
                right = cls._evaluate_node(comparator_node, context)
                if isinstance(op, ast.Eq):
                    res = left == right
                elif isinstance(op, ast.NotEq):
                    res = left != right
                elif isinstance(op, ast.Lt):
                    res = left < right
                elif isinstance(op, ast.LtE):
                    res = left <= right
                elif isinstance(op, ast.Gt):
                    res = left > right
                elif isinstance(op, ast.GtE):
                    res = left >= right
                else:
                    raise TypeError(f"Unsupported comparison operator: {type(op)}")

                if not res:
                    return False
                left = right
            return True

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "abs":
                if len(node.args) != 1:
                    raise ValueError("abs() takes exactly 1 argument.")
                return abs(cls._evaluate_node(node.args[0], context))
            raise ValueError(f"Calling function '{node.func}' is not permitted.")

        raise ValueError(f"Unsupported AST node type: {type(node).__name__}")


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
