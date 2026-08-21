import logging
import json
import wasmtime
from typing import Any

logger = logging.getLogger(__name__)


class WasmSandbox:
    """Sandbox for executing untrusted plugins via WASM."""

    def __init__(self, config: dict) -> None:
        self._config = config
        self._fuel_per_call = config.get("plugins", {}).get("wasm", {}).get("fuel", 1_000_000)

        cfg = wasmtime.Config()
        try:
            cfg.consume_fuel = True
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
            wasi_cfg.inherit_stdout()
            wasi_cfg.inherit_stderr()
            self._store.set_wasi(wasi_cfg)
        except Exception:
            pass

    def load_plugin(self, wasm_path: Any) -> Any:
        """Load a WASM plugin from file."""
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
