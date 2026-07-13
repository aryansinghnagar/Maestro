---
title: "RFC-002: Shared Module Extraction"
---

### RFC-002: Shared Module Extraction

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 3)

#### Problem
7 modules each implement their own copy of platform-specific path resolution (`~/.config/gesture_controller` on Linux, `~/Library/Application Support/gesture_controller` on macOS, `%APPDATA%/gesture_controller` on Windows). This is 7 copies of the same logic. Similar duplication for FRAME_* constants (4 copies), CONNECTIONS (2 copies), keycodes (3 copies).

#### Proposed Solution

```python
# core/paths.py
def user_config_dir() -> Path:
    """Return the user config directory for Maestro."""
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", ...)) / "gesture_controller"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "gesture_controller"
    else:
        return Path(os.environ.get("XDG_CONFIG_HOME", ...)) / "gesture_controller"
```

All 7 modules import from `core.paths` instead of implementing their own.

#### Alternatives Considered
1. **Use `platformdirs` library** — Considered, but adds dependency; we only need 5 functions
2. **Singleton config** — Rejected; paths are stateless functions

#### Migration Plan
1. Create `core/paths.py` with full implementation (§104.1)
2. Update each of the 7 modules to import from `core.paths`
3. Remove inline path logic from each module
4. Add tests for `core/paths.py` on all 3 platforms
5. Same pattern for `vision/constants.py`, `models/hand_topology.py`, `os_integration/keycodes.py`

#### Backward Compatibility
Internal API change; no external API impact.

#### Tests
- `test_paths.py` — verify correct paths on each platform
- `test_constants.py` — verify constants match expected values
- `test_keycodes.py` — verify key normalization and lookup

---