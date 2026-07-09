import os
import json
import shutil
import zipfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gesture_controller.core.compliance import (
    erase_data,
    sanitize_config_text,
    redact_logs_text,
    export_data,
    get_plugins_metadata,
)


def test_sanitize_config_text() -> None:
    raw_config = """
engine:
  min_detection_confidence: 0.7
gestures:
  SwipeRight: "KeyPress:Right"
  Fist: "OS:ShowDesktop"
profiles:
  - app: "notepad.exe"
    hotkey: "ctrl+shift+n"
"""
    sanitized = sanitize_config_text(raw_config)
    assert "KeyPress:Right" not in sanitized
    assert "OS:ShowDesktop" not in sanitized
    assert "ctrl+shift+n" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "0.7" in sanitized  # Non-sensitive value preserved


def test_redact_logs_text() -> None:
    # 1. Test JSON line log format (structlog)
    json_log = json.dumps({
        "timestamp": "2026-07-09T08:00:00Z",
        "event": "Action executed",
        "app": "chrome.exe",
        "gesture": "SwipeLeft",
        "action": "KeyPress:Left",
    })
    redacted = redact_logs_text(json_log)
    data = json.loads(redacted)
    assert data["app"] == "[REDACTED]"
    assert data["gesture"] == "[REDACTED]"
    assert data["action"] == "[REDACTED]"
    assert data["timestamp"] == "2026-07-09T08:00:00Z"

    # 2. Test plaintext log format fallback
    plain_log = "Executed SwipeLeft on chrome.exe (action='KeyPress:Left')"
    redacted_plain = redact_logs_text(plain_log)
    assert "SwipeLeft" not in redacted_plain
    assert "chrome.exe" not in redacted_plain
    assert "KeyPress:Left" not in redacted_plain


def test_erase_data() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        sub_dir = temp_dir / "gesture_controller"
        sub_dir.mkdir()
        (sub_dir / "config.yaml").touch()

        with patch("gesture_controller.core.compliance.get_user_data_dirs", return_value=[sub_dir]):
            erase_data()

        assert not sub_dir.exists()
    finally:
        shutil.rmtree(temp_dir)


def test_export_data() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Set up mock config/data directories
        config_dir = temp_dir / "gesture_controller"
        config_dir.mkdir()
        
        config_file = config_dir / "config.yaml"
        config_file.write_text("gestures:\n  SwipeRight: \"KeyPress:Right\"\n", encoding="utf-8")
        
        logs_dir = config_dir / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "activity.log"
        log_file.write_text("{\"app\": \"chrome.exe\", \"gesture\": \"SwipeLeft\"}\n", encoding="utf-8")
        
        templates_dir = config_dir / "templates"
        templates_dir.mkdir()
        template_file = templates_dir / "test_template.json"
        template_file.write_text("{}", encoding="utf-8")
        
        zip_output = temp_dir / "export.zip"
        
        with patch("gesture_controller.core.compliance.get_user_data_dirs", return_value=[config_dir]):
            export_data(zip_output)
            
        assert zip_output.exists()
        
        # Verify ZIP contents
        with zipfile.ZipFile(zip_output, "r") as zipf:
            namelist = zipf.namelist()
            assert "config.yaml" in namelist
            assert "logs/activity.log" in namelist
            assert "templates/test_template.json" in namelist
            
            # Verify config redaction inside zip
            cfg_content = zipf.read("config.yaml").decode("utf-8")
            assert "KeyPress:Right" not in cfg_content
            assert "[REDACTED]" in cfg_content
            
            # Verify log redaction inside zip
            log_content = zipf.read("logs/activity.log").decode("utf-8")
            assert "chrome.exe" not in log_content
            assert "[REDACTED]" in log_content

    finally:
        shutil.rmtree(temp_dir)
