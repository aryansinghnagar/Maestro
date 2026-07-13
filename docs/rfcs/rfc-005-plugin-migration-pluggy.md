---
title: "RFC-005: Plugin Migration to pluggy"
---

### RFC-005: Plugin Migration to pluggy

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 7)

#### Problem
Custom `PluginLoader` (602 LOC) has known sandbox bypasses and is a god class.

#### Proposed Solution

```python
# core/plugin_manager.py
import pluggy

hookspec = pluggy.HookspecMarker("maestro")
hookimpl = pluggy.HookimplMarker("maestro")

class MaestroSpec:
    @hookspec
    def get_gestures(self) -> list[dict]: ...
    @hookspec
    def get_action_handlers(self) -> dict[str, Callable]: ...

class PluginManager:
    def __init__(self):
        self.pm = pluggy.PluginManager("maestro")
        self.pm.add_hookspecs(MaestroSpec)
    def discover(self):
        from importlib.metadata import entry_points
        for ep in entry_points(group="maestro.plugins"):
            plugin = ep.load()
            self.pm.register(plugin(), name=ep.name)
```

#### Alternatives Considered
1. **Keep custom PluginLoader, fix bugs** — Rejected: 602 LOC of duplicated effort
2. **Use pytest's plugin system directly** — Rejected: too tightly coupled to pytest
3. **Use click's plugin system** — Rejected: CLI-focused, not general-purpose

#### Migration Plan
1. Implement `PluginManager` using `pluggy`
2. Create adapter for existing Python plugins (convert `PLUGIN_META` + `GESTURE_DEFINITIONS` to hookimpls)
3. Keep `RestrictedPython` as optional sandbox for legacy plugins
4. Third-party plugins use `pyproject.toml` entry points

#### Backward Compatibility
- Existing `PLUGIN_META` and `GESTURE_DEFINITIONS` continue to work via adapter
- Adapter deprecated; removal in v1.0

#### Tests
- `test_plugin_manager.py` — discovery, registration, hook invocation
- `test_plugin_adapter.py` — legacy plugin compatibility
- `test_plugin_sandbox.py` — AST scanner (§51)

---