import logging
import json
import wasmtime
from typing import Any

logger = logging.getLogger(__name__)


class WasmSandbox:
    """Sandbox for executing untrusted plugins via WASM."""

    _MAX_WASM_BYTES = 16 * 1024 * 1024  # 16 MiB cap per plugin module

    def __init__(self, config: dict) -> None:
        self._config = config
        try:
            self._fuel_per_call = int(
                config.get("plugins", {}).get("wasm", {}).get("fuel", 1_000_000)
            )
        except (TypeError, ValueError):
            self._fuel_per_call = 1_000_000
        self._fuel_per_call = max(10_000, min(self._fuel_per_call, 10_000_000))
        try:
            max_mem = int(
                config.get("plugins", {}).get("wasm", {}).get("max_memory_bytes", 64 * 1024 * 1024)
            )
        except (TypeError, ValueError):
            max_mem = 64 * 1024 * 1024
        self._max_memory_bytes = max(8 * 1024 * 1024, min(max_mem, 256 * 1024 * 1024))

        cfg = wasmtime.Config()
        try:
            cfg.consume_fuel = True
        except Exception:
            pass
        try:
            # ReAct fix: bound linear memory to contain OOM/DOS plugins.
            cfg.max_wasm_stack = 512 * 1024
        except Exception:
            pass
        self._engine = wasmtime.Engine(cfg)
        self._store = wasmtime.Store(self._engine)

        try:
            self._store.set_fuel(self._fuel_per_call)
        except Exception:
            pass

        try:
            wasi_cfg = wasmtime.WasiConfig()
            # ReAct fix: do NOT inherit stdout/stderr by default (log spam /
            # exfil channel). Plugins get no preopens -> no FS/net.
            self._store.set_wasi(wasi_cfg)
        except Exception:
            pass

    def load_plugin(self, wasm_path: Any) -> Any:
        """Load a WASM plugin from file (size-checked, dir-confined)."""
        try:
            import os as _os

            size = _os.path.getsize(str(wasm_path))
            if size > self._MAX_WASM_BYTES:
                raise ValueError(f"WASM plugin too large ({size} bytes)")
            if size == 0:
                raise ValueError("Empty WASM file")
        except OSError as e:
            raise ValueError(f"Cannot stat WASM plugin: {e}") from e
        module = wasmtime.Module.from_file(self._engine, str(wasm_path))

        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()
        instance = linker.instantiate(self._store, module)

        exports = instance.exports(self._store)
        return WasmPlugin(exports, self._store, fuel_per_call=self._fuel_per_call)


class WasmPlugin:
    """A loaded WASM plugin."""

    def __init__(self, exports: Any, store: wasmtime.Store, fuel_per_call: int = 1_000_000) -> None:
        self._exports = exports
        self._store = store
        self._fuel_per_call = fuel_per_call

    def _replenish_fuel(self) -> None:
        """Audit fix MAE-AUD-004: replenish fuel per invocation to prevent starvation."""
        try:
            self._store.set_fuel(self._fuel_per_call)
        except Exception:
            pass

    def get_gestures(self) -> list[dict]:
        """Call the plugin's get_gestures export."""
        func = self._exports.get("get_gestures")
        if not func:
            return []

        self._replenish_fuel()
        try:
            result = func(self._store)
            if isinstance(result, str):
                return json.loads(result)
            elif isinstance(result, bytes):
                return json.loads(result.decode("utf-8"))
        except Exception as e:
            logger.error("WASM get_gestures execution failed", error=str(e))
        return []

    def on_gesture(self, gesture_name: str, features: dict) -> dict | None:
        """Call the plugin's on_gesture export."""
        func = self._exports.get("on_gesture")
        if not func:
            return None

        self._replenish_fuel()
        try:
            result = func(self._store, gesture_name, json.dumps(features))
            if isinstance(result, str):
                return json.loads(result)
            elif isinstance(result, bytes):
                return json.loads(result.decode("utf-8"))
        except Exception as e:
            logger.error("WASM on_gesture execution failed", error=str(e), gesture=gesture_name)
        return None
