import pytest
from gesture_controller.core.expression_evaluator import SafeExpressionEvaluator


def test_safe_evaluator_valid_expressions() -> None:
    # Test compilation
    code = SafeExpressionEvaluator.compile_expression(
        "index_extended == True and middle_extended == False"
    )

    # Test evaluation
    context = {"index_extended": True, "middle_extended": False}
    assert SafeExpressionEvaluator.evaluate(code, context) is True

    context2 = {"index_extended": True, "middle_extended": True}
    assert SafeExpressionEvaluator.evaluate(code, context2) is False


def test_safe_evaluator_operator_precedence() -> None:
    code = SafeExpressionEvaluator.compile_expression("x > 5 and y < 10 or z == True")
    assert SafeExpressionEvaluator.evaluate(code, {"x": 6, "y": 8, "z": False}) is True
    assert SafeExpressionEvaluator.evaluate(code, {"x": 4, "y": 8, "z": True}) is True


def test_safe_evaluator_invalid_node_types_raises() -> None:
    # Function calls are prohibited
    with pytest.raises(ValueError, match="is not allowed"):
        SafeExpressionEvaluator.compile_expression("print('hello')")

    # Attribute access is prohibited
    with pytest.raises(ValueError, match="is not allowed"):
        SafeExpressionEvaluator.compile_expression("index.extended == True")
