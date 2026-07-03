import os
from pathlib import Path
import pytest

def test_no_unsafe_eval_or_exec_in_codebase() -> None:
    """Scan the codebase to verify eval() and exec() are not called,
    except for the pre-approved safe evaluation in config_manager.py."""
    
    gc_dir = Path(__file__).parent.parent.parent
    py_files = list(gc_dir.glob("**/*.py"))
    
    for py_file in py_files:
        # Skip the tests directory itself, the config_manager file where safe eval is defined,
        # and GUI files which call QApplication.exec() / QDialog.exec() (Qt methods, not Python's exec)
        if "tests" in py_file.parts or py_file.name in ("config_manager.py", "app_entry.py", "settings_window.py"):
            continue
            
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Check for direct calls to eval or exec
            assert "eval(" not in content.replace("literal_eval(", ""), f"Unsafe 'eval(' call found in {py_file.relative_to(gc_dir)}"
            assert "exec(" not in content.replace("exec_module(", "").replace("_exec(", ""), f"Unsafe 'exec(' call found in {py_file.relative_to(gc_dir)}"
