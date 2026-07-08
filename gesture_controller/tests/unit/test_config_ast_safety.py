import ast
import os
from pathlib import Path
import pytest


def test_no_unsafe_eval_or_exec_in_codebase() -> None:
    """Scan the codebase to verify eval() and exec() are not called,
    except for the pre-approved safe evaluation in config_manager.py."""

    gc_dir = Path(__file__).parent.parent.parent
    py_files = list(gc_dir.glob("**/*.py"))

    for py_file in py_files:
        # Skip the tests directory itself
        if "tests" in py_file.parts:
            continue

        # Allow only config_manager.py to use eval()
        is_config_manager = py_file.name == "config_manager.py"
        # Allow plugin_loader.py to use exec() under the sandbox
        is_plugin_loader = py_file.name == "plugin_loader.py"

        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError as e:
            pytest.fail(f"Syntax error while parsing AST for {py_file}: {e}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name == "eval":
                        if not is_config_manager:
                            pytest.fail(
                                f"Unsafe Call to eval() found in {py_file.relative_to(gc_dir)}"
                            )
                    elif func_name == "exec":
                        if not is_plugin_loader:
                            pytest.fail(
                                f"Unsafe Call to exec() found in {py_file.relative_to(gc_dir)}"
                            )
