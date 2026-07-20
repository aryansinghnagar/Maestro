"""Safe AST-based compilation and evaluation of boolean expression strings.

Allows safe execution of conditions without eval().
"""
from __future__ import annotations

import ast
from typing import Any
import structlog

logger = structlog.get_logger(__name__)


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
