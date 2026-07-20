"""
Config schema migration registry.
"""

from typing import Any, Callable
import structlog

logger = structlog.get_logger(__name__)

# Registry of migration functions
# Key is the source version. Value is a tuple of (target_version, callable)
_registry: dict[str, tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = {}


def register_migration(
    from_version: str, to_version: str
) -> Callable[
    [Callable[[dict[str, Any]], dict[str, Any]]], Callable[[dict[str, Any]], dict[str, Any]]
]:
    """Decorator to register a migration function."""

    def decorator(
        func: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> Callable[[dict[str, Any]], dict[str, Any]]:
        _registry[from_version] = (to_version, func)
        return func

    return decorator


@register_migration("1.0", "2.0")
def migrate_1_to_2(config: dict[str, Any]) -> dict[str, Any]:
    """Migration from version 1.0 to 2.0.
    Renames safety.pause_hotkey to safety.toggle_recognition_hotkey.
    """
    logger.info("Migrating configuration schema from 1.0 to 2.0")
    config["version"] = "2.0"

    if "safety" in config and isinstance(config["safety"], dict):
        if "pause_hotkey" in config["safety"]:
            config["safety"]["toggle_recognition_hotkey"] = config["safety"].pop("pause_hotkey")

    return config


@register_migration("2.0", "3.0")
def migrate_2_to_3(config: dict[str, Any]) -> dict[str, Any]:
    """Migration from version 2.0 to 3.0.
    Renames/splits resolution, renames derivate_cutoff, and updates version.
    """
    logger.info("Migrating configuration schema from 2.0 to 3.0")
    config["version"] = "3.0"

    # camera.resolution -> camera.frame_width/frame_height
    if "camera" in config and isinstance(config["camera"], dict):
        if "resolution" in config["camera"]:
            res = config["camera"].pop("resolution")
            if isinstance(res, list) and len(res) == 2:
                config["camera"]["frame_width"] = res[0]
                config["camera"]["frame_height"] = res[1]
            elif isinstance(res, dict) and "width" in res and "height" in res:
                config["camera"]["frame_width"] = res["width"]
                config["camera"]["frame_height"] = res["height"]

    # filtering.one_euro.derivate_cutoff -> filtering.one_euro.derivative_cutoff
    if "filtering" in config and isinstance(config["filtering"], dict):
        if "one_euro" in config["filtering"] and isinstance(config["filtering"]["one_euro"], dict):
            if "derivate_cutoff" in config["filtering"]["one_euro"]:
                config["filtering"]["one_euro"]["derivative_cutoff"] = config["filtering"][
                    "one_euro"
                ].pop("derivate_cutoff")

    # engine.use_onnx -> engine.inference_backend
    if "engine" in config and isinstance(config["engine"], dict):
        if "use_onnx" in config["engine"]:
            use_onnx = config["engine"].pop("use_onnx")
            config["engine"]["inference_backend"] = "onnx" if use_onnx else "auto"

    return config


def migrate_config(config: dict[str, Any], target_version: str = "3.0") -> dict[str, Any]:
    """Sequentially apply registered migrations to bring the config up to the target version."""
    current_version = config.get("version", "1.0")
    if not isinstance(current_version, str):
        current_version = str(current_version)

    steps = 0
    while current_version != target_version and steps < 100:
        if current_version not in _registry:
            logger.debug("No migration path found from current version", version=current_version)
            break

        next_version, migration_func = _registry[current_version]
        try:
            config = migration_func(config)
            current_version = next_version
            steps += 1
        except Exception as e:
            logger.exception(
                "Migration step failed",
                from_version=current_version,
                to_version=next_version,
                error=str(e),
            )
            raise RuntimeError(f"Failed to migrate config from version {current_version}: {e}")

    return config
