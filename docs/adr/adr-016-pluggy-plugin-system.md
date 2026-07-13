---
title: "ADR-016: pluggy Plugin System"
---

### ADR-016: pluggy Plugin System

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Custom `PluginLoader` (602 LOC) handles discovery + AST validation + RestrictedPython exec + WASM runtime + hot-reload. It's a god class with known sandbox bypasses (B19, B20).

**Decision:** Replace with `pluggy` (hookspec/hookimpl system behind pytest) + `importlib.metadata` entry points. Third-party plugins declare `[project.entry-points."maestro.plugins"]` in their `pyproject.toml`. Keep RestrictedPython as defense-in-depth for legacy Python plugins.

**Consequences:**
- Positive: Standard plugin architecture; pip-installable plugins; no custom discovery code; community marketplace path.
- Negative: Existing plugins must migrate to entry-point format; backward-compatible adapter needed.

**Migration plan:**
1. Implement `PluginManager` (§39) using pluggy
2. Create adapter for existing Python plugins (convert `PLUGIN_META` + `GESTURE_DEFINITIONS` to hookimpls)
3. Keep `RestrictedPython` as optional sandbox for legacy plugins
4. Third-party plugins use `pyproject.toml` entry points

**Supersedes:** ADR-010 (plugin hot-reload) — pluggy uses `importlib.reload()` instead of `exec()`.