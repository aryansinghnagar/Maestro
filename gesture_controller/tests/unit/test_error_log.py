import pytest
from pathlib import Path
from unittest.mock import MagicMock
from gesture_controller.tests.conftest import (
    pytest_runtest_logreport,
    pytest_warning_recorded,
    pytest_unconfigure,
    failed_reports,
    collected_warnings
)

def test_error_log_generation(tmp_path: Path) -> None:
    # Clear any previous runs
    failed_reports.clear()
    collected_warnings.clear()
    
    # 1. Mock a failed test report
    mock_report = MagicMock()
    mock_report.when = "call"
    mock_report.failed = True
    mock_report.nodeid = "gesture_controller/tests/unit/test_dummy.py::test_fail"
    mock_report.outcome = "failed"
    mock_report.longrepr = "AssertionError: 1 != 2"
    mock_report.capstdout = "some stdout"
    mock_report.capstderr = "some stderr"
    
    pytest_runtest_logreport(mock_report)
    assert len(failed_reports) == 1
    
    # 2. Mock a warning
    mock_warning = MagicMock()
    mock_warning.message = DeprecationWarning("Feature X is deprecated")
    mock_warning.category = DeprecationWarning
    mock_warning.filename = "dummy_file.py"
    mock_warning.lineno = 42
    
    pytest_warning_recorded(mock_warning, "call", "test_node_id", ("dummy_file.py", 42, "func"))
    assert len(collected_warnings) == 1
    
    # 3. Trigger unconfigure with a mock config
    mock_config = MagicMock()
    mock_config.rootdir = tmp_path
    
    pytest_unconfigure(mock_config)
    
    # 4. Verify generated error_log.md
    log_file = tmp_path / "error_log.md"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    
    assert "# Maestro Test Execution Error & Warning Log" in content
    assert "## ❌ Test Failures" in content
    assert "test_dummy.py::test_fail" in content
    assert "AssertionError: 1 != 2" in content
    assert "## ⚠️ Pytest Warnings" in content
    assert "DeprecationWarning" in content
    assert "Feature X is deprecated" in content
    
    # Cleanup global state
    failed_reports.clear()
    collected_warnings.clear()
