"""Single source of truth for platform-specific path resolution.

Replaces 7 copies of platform-path logic across:
  config_manager, compliance, dtw_matcher, plugin_loader,
  onboarding, broker, updater
"""

from __future__ import annotations

import os
import platform
from pathlib import Path


def user_config_dir() -> Path:
    """Return the user configuration directory for Maestro.

    Platform behavior:
      Linux:   ~/.config/gesture_controller/ (respects XDG_CONFIG_HOME)
      macOS:   ~/Library/Application Support/gesture_controller/
      Windows: %APPDATA%/gesture_controller/
    """
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "gesture_controller"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "gesture_controller"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        if not base:
            base = str(Path.home() / ".config")
        return Path(base) / "gesture_controller"


def user_data_dir() -> Path:
    """Return the user data directory (templates, logs, models)."""
    system = platform.system()
    if system == "Linux":
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base) / "gesture_controller"
    return user_config_dir()


def user_cache_dir() -> Path:
    """Return the user cache directory (ONNX compiled models, etc.)."""
    system = platform.system()
    if system == "Linux":
        base = os.environ.get("XDG_CACHE_HOME")
        if base:
            return Path(base) / "gesture_controller"
        return Path.home() / ".cache" / "gesture_controller"
    elif system == "Darwin":
        return Path.home() / "Library" / "Caches" / "gesture_controller"
    else:
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
        return Path(base) / "gesture_controller" / "cache"


def user_plugin_dir() -> Path:
    """Return the user plugin directory."""
    return user_config_dir() / "plugins"


def user_template_dir() -> Path:
    """Return the custom gesture template directory."""
    return user_config_dir() / "custom_templates"


def user_log_dir() -> Path:
    """Return the log file directory."""
    return user_config_dir() / "logs"


def onboarded_marker_path() -> Path:
    """Return the path to the onboarding completion marker file."""
    return user_config_dir() / ".onboarded"


def api_token_path() -> Path:
    """Return the path to the REST API authentication token file."""
    return user_config_dir() / "api_token"


def broker_socket_path() -> Path:
    """Return the Unix socket path for the input injection broker."""
    system = platform.system()
    if system == "Linux":
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        if runtime_dir:
            return Path(runtime_dir) / "gesture_controller_broker.sock"
    # Fallback with safe UID lookup
    getuid_fn = getattr(os, "getuid", None)
    uid = getuid_fn() if getuid_fn else "default"
    return Path("/tmp") / f"gesture_controller_broker_{uid}.sock"  # nosec B108


def ensure_dirs() -> None:
    """Create all user directories if they don't exist."""
    for dir_fn in [
        user_config_dir,
        user_data_dir,
        user_cache_dir,
        user_plugin_dir,
        user_template_dir,
        user_log_dir,
    ]:
        d = dir_fn()
        d.mkdir(parents=True, exist_ok=True)
