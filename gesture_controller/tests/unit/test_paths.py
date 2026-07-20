from pathlib import Path
from gesture_controller.core.paths import (
    user_config_dir,
    user_data_dir,
    user_cache_dir,
    user_plugin_dir,
    user_template_dir,
    user_log_dir,
    onboarded_marker_path,
    api_token_path,
    broker_socket_path,
    ensure_dirs,
)


def test_user_dirs_returns_path_objects() -> None:
    assert isinstance(user_config_dir(), Path)
    assert isinstance(user_data_dir(), Path)
    assert isinstance(user_cache_dir(), Path)
    assert isinstance(user_plugin_dir(), Path)
    assert isinstance(user_template_dir(), Path)
    assert isinstance(user_log_dir(), Path)
    assert isinstance(onboarded_marker_path(), Path)
    assert isinstance(api_token_path(), Path)
    assert isinstance(broker_socket_path(), Path)


def test_ensure_dirs_creates_folders(tmp_path, monkeypatch) -> None:
    # Point configuration home to tmp_path to avoid modifying user home
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    ensure_dirs()
    assert user_config_dir().exists()
    assert user_data_dir().exists()
    assert user_cache_dir().exists()
    assert user_plugin_dir().exists()
    assert user_template_dir().exists()
    assert user_log_dir().exists()
