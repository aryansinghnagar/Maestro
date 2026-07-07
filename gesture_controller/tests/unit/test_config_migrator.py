import pytest
from gesture_controller.core.config_migrator import migrate_config


def test_migrate_v1_to_v2() -> None:
    old_config = {
        "version": "1.0",
        "camera": {"device_id": 0},
        "safety": {"pause_hotkey": "Ctrl+Shift+P", "safety_gesture_enabled": False},
    }

    migrated = migrate_config(old_config)

    assert migrated["version"] == "2.0"
    assert "pause_hotkey" not in migrated["safety"]
    assert migrated["safety"]["toggle_recognition_hotkey"] == "Ctrl+Shift+P"
    assert migrated["safety"]["safety_gesture_enabled"] is False


def test_migrate_already_v2() -> None:
    v2_config = {"version": "2.0", "safety": {"toggle_recognition_hotkey": "Ctrl+Shift+P"}}

    migrated = migrate_config(v2_config)
    assert migrated == v2_config  # Unchanged


def test_migrate_missing_version_defaults_to_v1() -> None:
    no_ver_config = {"safety": {"pause_hotkey": "Ctrl+Shift+X"}}

    migrated = migrate_config(no_ver_config)
    assert migrated["version"] == "2.0"
    assert migrated["safety"]["toggle_recognition_hotkey"] == "Ctrl+Shift+X"
