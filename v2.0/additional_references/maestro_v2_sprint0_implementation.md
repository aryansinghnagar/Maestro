# Maestro v2.0 Sprint 0 — Critical Blocker Fixes (IMPLEMENTED)

**Repository:** https://github.com/aryansinghnagar/Maestro
**Base commit:** `2025bf6` — "build: resolve cross-platform CI pipeline blocks"
**Status:** ✅ ALL 5 CRITICAL BLOCKERS FIXED AND VERIFIED
**Verification:** 192 tests pass, 0 failures, 81.24% coverage, black/mypy/bandit/pip-audit all clean

---

## What Was Done

I implemented all 5 critical blockers identified in the v2.0 roadmap, plus 1 privacy fix and the test updates needed to match the new (correct) behavior. Every fix is verified by the full CI check suite.

### Blocker 1: Plugin sandbox is theater → FIXED

**File:** `gesture_controller/plugins/plugin_loader.py` (+112 lines)

**Was:** `compile_restricted()` was called but the output was discarded. The module was executed via standard `spec.loader.exec_module()` — zero actual sandboxing. Any plugin could `import socket; socket.socket(...)` and exfiltrate data.

**Now:** The `compile_restricted()` output is used. The module is executed via `exec(code, restricted_globals)` with:
- `safe_builtins` from RestrictedPython (no `__import__`, no `open`, no `eval`, no `exec`, no `globals`, no `locals`)
- A **guarded `__import__`** that only allows whitelisted packages (time, math, json, structlog, numpy, etc.) + permission-gated packages (pyautogui requires `os:input` permission)
- `safer_getattr` and `guarded_setattr` guards

**Honest caveat:** RestrictedPython is still not a full sandbox — `getattr`-based reflection can theoretically bypass it. The v2.0 roadmap's WASM component model (Phase 6) is the proper fix. But this interim fix blocks the 6 known bypass vectors identified in the roadmap analysis.

**Test update:** `test_plugin_ast_sandbox_passes_with_permission` now mocks `pyautogui` in `sys.modules` (the old test patched `importlib.util.spec_from_file_location` which is no longer used).

---

### Blocker 2: TLS verification disabled → FIXED

**File:** `gesture_controller/core/updater.py` (+27 lines)

**Was:**
```python
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
```
Textbook MITM vulnerability. An attacker on the network could spoof `api.github.com`, inject a malicious `html_url`, and the user would click through to a phishing site.

**Now:**
```python
ctx = ssl.create_default_context()  # TLS verification ENABLED
```

Plus: the `html_url` from the response body is now validated to be on `github.com` before being emitted to the GUI. The previous code only validated the API URL, not the response's `html_url`.

**Bonus fix:** `_is_newer()` no longer falls back to lexicographic comparison on `ValueError`. The previous code returned `True` for `"abc" > "1.0.0"`, triggering spurious "update available" notifications. Now returns `False` and logs a warning.

**Test update:** `test_updater_is_newer` now asserts `_is_newer("abc", "1.0.0") is False` (was `True`).

---

### Blocker 3: SharedMemory chmod broken on Linux → FIXED

**File:** `gesture_controller/core/engine.py` (+5 lines)

**Was:**
```python
shm_file = Path("/dev/shm") / f"psm_{self._shm_name}"
```
Python's `multiprocessing.shared_memory` creates the file at `/dev/shm/{name}` (no `psm_` prefix). `self._shm_name` is already the full name. So the code looked for a non-existent file, `shm_file.exists()` returned `False`, and `chmod(0o600)` **never ran**. Raw camera frames were world-readable (0666) on many Linux distros.

**Now:**
```python
shm_file = Path("/dev/shm") / self._shm_name  # correct path
```

---

### Blocker 4: No hand-ID tracking → INTERIM FIX (cap max_hands at 2)

**File:** `gesture_controller/vision/landmark_extractor.py` (+21 lines)

**Was:** `max_hands` config allowed any value. With `max_hands > 2`, the engine's per-handedness filter dict collided (only 2 keys: "Left"/"Right"), the DTW buffer interleaved frames from 3+ hands, and FSM state was corrupted.

**Now:** `max_hands` is capped at 2 with a warning log. Values > 2 are silently capped. Values < 1 are capped at 1. The full fix (hand-ID tracking via centroid IoU) is Phase 1 of the v2.0 roadmap (Rust core).

---

### Blocker 5: Sync dispatch blocks engine → FIXED

**File:** `gesture_controller/core/event_bus.py` (+39 lines)

**Was:** `SYNC_EVENTS = {"gesture_triggered"}`. The engine thread blocked for up to 250ms per gesture (subprocess calls to `swaymsg`/`xdotool`/`hyprctl`), dropping 7 frames at 30 FPS.

**Now:** `SYNC_EVENTS: set[str] = set()` — `gesture_triggered` is async. The ActionDispatcher runs on the EventBus worker thread. The engine thread never blocks on OS action execution.

**Bonus fix:** `_failures` dict is now keyed by `(event_type, handler)` tuple instead of `handler` alone. The previous keying meant a handler subscribed to both `raw_landmarks` and `gesture_triggered` shared a single failure counter — if it failed 3× on `raw_landmarks` (non-critical telemetry), it got auto-unsubscribed from `gesture_triggered` (the critical action channel).

**Test update:** All 6 `test_event_bus.py` tests updated to use `time.sleep(0.05)` for async dispatch. Added new `test_gesture_triggered_is_async` regression test that verifies the handler runs on the worker thread, not the publisher thread.

**Test update:** All 5 `test_action_dispatcher.py` tests updated with `time.sleep(0.05)` after `publish()`.

---

### Privacy Fix: Stop logging foreground app names → FIXED

**File:** `gesture_controller/os_integration/action_dispatcher.py` (+32 lines)

**Was:**
```python
logger.info("Action executed", ..., app=event.app_profile, ...)
```
`event.app_profile` is the foreground process name (e.g., `chrome.exe`, `vlc.exe`). This reveals user activity patterns. Logs persist in 10MB × 3 rotated files.

**Now:**
```python
app_class = self._classify_app(event.app_profile or "")
logger.info("Action executed", ..., app_class=app_class, ...)
```

`_classify_app()` returns a coarse taxonomy: `browser`, `editor`, `media`, `communication`, `game`, `system`, `unknown`. Never the real app name. Diagnostics still useful; privacy preserved.

---

### Test Infrastructure Fix: AST safety whitelist

**File:** `gesture_controller/tests/unit/test_config_ast_safety.py` (+20 lines)

**Was:** The test flagged any `exec()` call in the codebase. My RestrictedPython fix uses `exec(code, restricted_globals)` — which is the correct, intentional use of `exec` with safe globals.

**Now:** The test has an `EXEC_WHITELIST = {"plugin_loader.py"}` that allows `exec()` in the plugin loader (with a comment explaining why it's safe).

---

## Verification Results

```
========== COMPLETE CI VERIFICATION ==========

=== 1. BLACK ===        ✅ 87 files clean
=== 2. MYPY ===          ✅ 0 errors in 39 files
=== 3. BANDIT ===        ✅ 0 MEDIUM/HIGH findings
=== 4. PIP-AUDIT ===     ✅ 0 vulnerabilities
=== 5. PYTEST ===        ✅ 192 passed, 0 failed, 81.24% coverage

========== ALL 5 CI CHECKS PASS ==========
```

## Changed Files (11 files, +275/-54 lines)

| File | Lines changed | What |
|---|---|---|
| `gesture_controller/core/engine.py` | +5/-2 | Fix SharedMemory chmod path |
| `gesture_controller/core/event_bus.py` | +39/-10 | Move gesture_triggered to async; fix _failures keying |
| `gesture_controller/core/updater.py` | +27/-5 | Re-enable TLS; validate html_url; fix _is_newer fallback |
| `gesture_controller/os_integration/action_dispatcher.py` | +32/-5 | Privacy: app-class taxonomy instead of raw app names |
| `gesture_controller/plugins/plugin_loader.py` | +112/-15 | Actually use RestrictedPython safe_globals + guarded __import__ |
| `gesture_controller/vision/landmark_extractor.py` | +21/-2 | Cap max_hands at 2 |
| `gesture_controller/tests/unit/test_action_dispatcher.py` | +6/-0 | Add time.sleep for async dispatch |
| `gesture_controller/tests/unit/test_config_ast_safety.py` | +20/-10 | Whitelist plugin_loader.py for exec() |
| `gesture_controller/tests/unit/test_event_bus.py` | +47/-30 | Update for async gesture_triggered; add regression test |
| `gesture_controller/tests/unit/test_plugin_loader.py` | +13/-8 | Mock pyautogui for RestrictedPython test |
| `gesture_controller/tests/unit/test_updater.py` | +6/-2 | Fix _is_newer assertion (abc → False, not True) |

## To Commit and Push

```bash
cd /path/to/Maestro

git add -A
git commit -m "fix(v2.0-sprint-0): resolve 5 critical blockers — TLS, sandbox, shm, dispatch, max_hands

Blockers fixed:
- S-01: Re-enable TLS verification in update checker (was MITM-vulnerable)
- S-02: Actually use RestrictedPython safe_globals for plugin sandbox (was theater)
- S-03: Fix SharedMemory chmod path on Linux (was world-readable)
- P-04: Move gesture_triggered to async dispatch (was blocking engine 250ms)
- SC-01: Cap max_hands at 2 (was corrupting filters/FSMs/DTW with 3+ hands)

Privacy fix:
- PR-01: Log app_class (browser/editor/media/...) instead of raw app name

Test updates:
- test_event_bus: async dispatch semantics + regression test
- test_action_dispatcher: async dispatch timing
- test_updater: _is_newer('abc','1.0.0') now returns False (was True — bug)
- test_config_ast_safety: whitelist plugin_loader.py exec() (RestrictedPython)
- test_plugin_loader: mock pyautogui for sandbox test

Verification: 192 passed, 0 failed, 81.24% coverage, black/mypy/bandit/pip-audit clean"

git push origin main
```

## What's Next (v2.0 Roadmap Phase 1)

The 5 critical blockers are resolved. The v2.0 roadmap's Phase 1 (Rust core engine) is the next milestone — it delivers the 10× latency improvement and proper hand-ID tracking that replaces the interim `max_hands=2` cap. See `maestro_v2_roadmap.md` §8 for the full Phase 1 plan.
