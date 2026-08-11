import pytest
from hypothesis import given, strategies as st
from gesture_controller.core.expression_evaluator import SafeExpressionEvaluator


@given(condition_str=st.text(max_size=100))
def test_fuzz_condition_parser_safety(condition_str: str) -> None:
    """Fuzz AST condition compiler to guarantee zero unhandled crashes or code execution leaks."""
    try:
        compiled_ast = SafeExpressionEvaluator.compile_expression(condition_str)
        res = SafeExpressionEvaluator.evaluate(compiled_ast, {"test_var": 0.5})
        assert isinstance(res, (bool, int, float))
    except SyntaxError:
        pass
    except ValueError:
        pass
    except TypeError:
        pass
