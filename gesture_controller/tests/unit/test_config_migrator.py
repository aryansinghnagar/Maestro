import pytest
from gesture_controller.core.config_migrator import migrate_config


def test_migrate_v1_to_v2() -> None:
    old_config = {
        "version": "1.0",
        "camera": {"device_id": 0},
        "safety": {"pause_hotkey": "Ctrl+Shift+P", "safety_gesture_enabled": False},
    }

    migrated = migrate_config(old_config, target_version="2.0")

    assert migrated["version"] == "2.0"
    assert "pause_hotkey" not in migrated["safety"]
    assert migrated["safety"]["toggle_recognition_hotkey"] == "Ctrl+Shift+P"
    assert migrated["safety"]["safety_gesture_enabled"] is False


def test_migrate_already_v2() -> None:
    v2_config = {"version": "2.0", "safety": {"toggle_recognition_hotkey": "Ctrl+Shift+P"}}

    migrated = migrate_config(v2_config, target_version="2.0")
    assert migrated == v2_config


def test_migrate_missing_version_defaults_to_v1() -> None:
    no_ver_config = {"safety": {"pause_hotkey": "Ctrl+Shift+X"}}

    migrated = migrate_config(no_ver_config, target_version="2.0")
    assert migrated["version"] == "2.0"
    assert migrated["safety"]["toggle_recognition_hotkey"] == "Ctrl+Shift+X"


def test_migrate_v2_to_v3() -> None:
    v2_config = {
        "version": "2.0",
        "camera": {
            "device_id": 0,
            "resolution": [1280, 720],
        },
        "filtering": {
            "one_euro": {
                "min_cutoff": 1.0,
                "derivate_cutoff": 2.0,
            }
        },
        "engine": {
            "use_onnx": True,
        }
    }

    migrated = migrate_config(v2_config)

    assert migrated["version"] == "3.0"
    assert "resolution" not in migrated["camera"]
    assert migrated["camera"]["frame_width"] == 1280
    assert migrated["camera"]["frame_height"] == 720
    assert "derivate_cutoff" not in migrated["filtering"]["one_euro"]
    assert migrated["filtering"]["one_euro"]["derivative_cutoff"] == 2.0
    assert "use_onnx" not in migrated["engine"]
    assert migrated["engine"]["inference_backend"] == "onnx"
