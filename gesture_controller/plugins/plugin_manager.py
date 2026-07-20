"""Plugin Manager — high-level façade over PluginLoader.

Provides:
- Persistent enable/disable state (stored in config)
- Plugin metadata introspection
- Install/uninstall from local directory
- Registry-based search/install (offline-first)
"""
from __future__ import annotations

import json
import shutil
import threading
import urllib.request
from pathlib import Path
from typing import Any

import structlog

from gesture_controller.plugins.plugin_loader import PluginLoader, Plugin, PluginLoadError, USER_PLUGIN_DIR

logger = structlog.get_logger(__name__)

# ── Registry ─────────────────────────────────────────────────────────────────
# Shipped registry is an offline snapshot; overrideable via config
_BUNDLED_REGISTRY = Path(__file__).parent.parent / "data" / "plugin_registry.json"
_REGISTRY_CACHE_TTL = 3600  # seconds


class PluginRecord:
    """Lightweight, serialisable view of a Plugin for the UI layer."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        author: str,
        permissions: list[str],
        path: Path,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.permissions = permissions
        self.path = path
        self.enabled = enabled

    @classmethod
    def from_plugin(cls, plugin: Plugin, enabled: bool = True) -> "PluginRecord":
        meta = plugin.meta
        return cls(
            name=meta.get("name", "unknown"),
            version=meta.get("version", "0.0.0"),
            description=meta.get("description", ""),
            author=meta.get("author", ""),
            permissions=meta.get("permissions", []),
            path=plugin.path,
            enabled=enabled,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "permissions": self.permissions,
            "path": str(self.path),
            "enabled": self.enabled,
        }


class PluginManager:
    """High-level plugin lifecycle manager.

    Wraps PluginLoader and persists enable/disable state via ConfigManager.
    """

    def __init__(self, event_bus: Any, config: Any) -> None:
        self._event_bus = event_bus
        self._config = config
        self._loader = PluginLoader(event_bus)
        self._lock = threading.Lock()
        self._records: dict[str, PluginRecord] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load_all(self) -> list[PluginRecord]:
        """Discover and load all plugins; apply saved enable/disable state."""
        plugins = self._loader.discover_all()
        disabled: list[str] = self._config.get("plugins.disabled", []) or []
        with self._lock:
            for plugin in plugins:
                name = plugin.meta.get("name", "unknown")
                enabled = name not in disabled
                self._records[name] = PluginRecord.from_plugin(plugin, enabled=enabled)
        logger.info("Plugin manager loaded", total=len(self._records))
        return list(self._records.values())

    def enable(self, name: str) -> bool:
        """Enable a plugin by name. Returns True on success."""
        with self._lock:
            if name not in self._records:
                return False
            self._records[name].enabled = True
        self._persist_disabled()
        self._event_bus.publish("plugin_enabled", name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a plugin by name (keeps it installed). Returns True on success."""
        with self._lock:
            if name not in self._records:
                return False
            self._records[name].enabled = False
        self._persist_disabled()
        self._event_bus.publish("plugin_disabled", name)
        return True

    def uninstall(self, name: str) -> bool:
        """Remove a user plugin from disk and unload it. Returns True on success."""
        with self._lock:
            record = self._records.get(name)
            if record is None:
                return False
            # Only allow uninstalling user plugins (not builtin)
            if not str(record.path).startswith(str(USER_PLUGIN_DIR)):
                logger.warning("Cannot uninstall builtin plugin", name=name)
                return False
            try:
                if record.path.is_file():
                    record.path.unlink()
                elif record.path.is_dir():
                    shutil.rmtree(record.path)
            except OSError as e:
                logger.error("Failed to delete plugin files", name=name, error=str(e))
                return False
            del self._records[name]
        self._persist_disabled()
        self._event_bus.publish("plugin_uninstalled", name)
        logger.info("Plugin uninstalled", name=name)
        return True

    def install_from_path(self, src: Path) -> PluginRecord | None:
        """Copy a plugin file/directory into the user plugin dir and load it.

        Returns the PluginRecord on success, None on failure.
        """
        USER_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        dest = USER_PLUGIN_DIR / src.name
        try:
            if src.is_file():
                shutil.copy2(src, dest)
            elif src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                logger.error("install_from_path: source not found", src=str(src))
                return None
        except OSError as e:
            logger.error("Failed to copy plugin to user dir", src=str(src), error=str(e))
            return None

        try:
            if dest.is_file():
                plugin = self._loader._load_plugin(dest)
            else:
                plugin = self._loader._load_wasm_plugin(dest)
        except PluginLoadError as e:
            logger.error("Failed to load installed plugin", reason=e.reason)
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        record = PluginRecord.from_plugin(plugin, enabled=True)
        with self._lock:
            self._records[record.name] = record
        self._event_bus.publish("plugin_installed", record.name)
        logger.info("Plugin installed", name=record.name, version=record.version)
        return record

    # ── Query ─────────────────────────────────────────────────────────────────

    def list_plugins(self, include_disabled: bool = True) -> list[PluginRecord]:
        """Return a sorted list of all known plugin records."""
        with self._lock:
            records = list(self._records.values())
        if not include_disabled:
            records = [r for r in records if r.enabled]
        return sorted(records, key=lambda r: r.name.lower())

    def get(self, name: str) -> PluginRecord | None:
        with self._lock:
            return self._records.get(name)

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            rec = self._records.get(name)
            return rec.enabled if rec else False

    # ── Registry ──────────────────────────────────────────────────────────────

    def search_registry(self, query: str) -> list[dict[str, Any]]:
        """Search the offline plugin registry JSON for matching plugins.

        Returns list of registry entry dicts (name, version, description, url).
        """
        registry = self._load_registry()
        q = query.lower()
        return [
            entry for entry in registry
            if q in entry.get("name", "").lower()
            or q in entry.get("description", "").lower()
            or q in entry.get("tags", [])
        ]

    def fetch_registry(self, url: str, timeout: float = 10.0) -> list[dict[str, Any]]:
        """Download an updated registry JSON from *url* and cache it locally.

        Falls back to the bundled registry on network failure.
        """
        cache_path = _BUNDLED_REGISTRY.parent / "plugin_registry_cache.json"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info("Plugin registry refreshed", url=url, count=len(data))
            return data
        except Exception as exc:
            logger.warning("Failed to fetch plugin registry, using cache", error=str(exc))
            return self._load_registry()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _load_registry(self) -> list[dict[str, Any]]:
        """Load the best available registry (cache → bundled → empty)."""
        cache = _BUNDLED_REGISTRY.parent / "plugin_registry_cache.json"
        for path in (cache, _BUNDLED_REGISTRY):
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
        return []

    def _persist_disabled(self) -> None:
        """Write the current disabled plugin list to config."""
        with self._lock:
            disabled = [name for name, rec in self._records.items() if not rec.enabled]
        self._config.set("plugins.disabled", disabled)
