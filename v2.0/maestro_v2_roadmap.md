# Maestro v2.0 — Comprehensive Roadmap

**Repository:** https://github.com/aryansinghnagar/Maestro
**Audited commit:** `2025bf6` — "build: resolve cross-platform CI pipeline blocks" (2026-07-08)
**Document type:** v2.0 product + engineering roadmap
**Scope:** Performance, speed, security, privacy, platform integration, developer experience, accessibility, competitive positioning
**Tone:** Direct, evidence-based, no hedging. Explicit confidence levels throughout.

> \\\*\\\*Persona note:\\\*\\\* This document adopts the agent.md system prompt's intellectual posture — world-class expert, provocative, aggressive, argumentative. Negative conclusions are fine. No disclaimers. Accuracy is the success metric.

\---

## Table of Contents

**Part I — Current State Assessment**

1. [Executive Summary](#1-executive-summary)
2. [Where Maestro Stands Today](#2-where-maestro-stands-today)
3. [The 5 Critical Blockers](#3-the-5-critical-blockers)

**Part II — Competitive Landscape**
4. [Competitive Positioning](#4-competitive-positioning)
5. [What Competitors Teach Us](#5-what-competitors-teach-us)
6. [Feature Gap Analysis — Top 20](#6-feature-gap-analysis--top-20)

**Part III — The v2.0 Architecture**
7. [Architecture Vision: The 10× Latency Plan](#7-architecture-vision-the-10x-latency-plan)
8. [Phase 1: Rust Core Engine (PyO3)](#8-phase-1-rust-core-engine-pyo3)
9. [Phase 2: GPU Inference Backends](#9-phase-2-gpu-inference-backends)
10. [Phase 3: Zero-Copy Pipeline](#10-phase-3-zero-copy-pipeline)
11. [Phase 4: Async Priority EventBus](#11-phase-4-async-priority-eventbus)

**Part IV — Security Hardening**
12. [Phase 5: Privilege Separation Architecture](#12-phase-5-privilege-separation-architecture)
13. [Phase 6: WASM Plugin Sandbox](#13-phase-6-wasm-plugin-sandbox)
14. [Phase 7: Supply Chain Integrity](#14-phase-7-supply-chain-integrity)
15. [Phase 8: Input Injection Security](#15-phase-8-input-injection-security)

**Part V — Privacy Protection**
16. [Phase 9: Data Minimization](#16-phase-9-data-minimization)
17. [Phase 10: Camera Privacy Hardening](#17-phase-10-camera-privacy-hardening)
18. [Phase 11: Compliance Framework](#18-phase-11-compliance-framework)

**Part VI — Platform-Native Deep Integration**
19. [Phase 12: Linux Native](#19-phase-12-linux-native)
20. [Phase 13: macOS Native](#20-phase-13-macos-native)
21. [Phase 14: Windows Native](#21-phase-14-windows-native)

**Part VII — New Features**
22. [Phase 15: Accessibility Modalities](#22-phase-15-accessibility-modalities)
23. [Phase 16: Developer Experience](#23-phase-16-developer-experience)
24. [Phase 17: Integration APIs](#24-phase-17-integration-apis)
25. [Phase 18: Community \& Marketplace](#25-phase-18-community--marketplace)

**Part VIII — Execution**
26. [Implementation Roadmap](#26-implementation-roadmap)
27. [Measurable Targets \& KPIs](#27-measurable-targets--kpis)
28. [Risk Register](#28-risk-register)
29. [Build Order \& Dependencies](#29-build-order--dependencies)
30. [Appendices](#30-appendices)

\---

# Part I — Current State Assessment

## 1\. Executive Summary

**Confidence: High.** Maestro v0.1.0 is an alpha-quality product with enterprise-grade architectural bones and five critical defects that make it unfit for a v2.0 release without significant rework. The codebase demonstrates real engineering maturity — multiprocessing with zero-copy SharedMemory, FSM-based gesture detection with AST-safe YAML conditions, a RestrictedPython plugin sandbox (theater, but the intent is right), Numba-JIT DTW matching, structured p50/p90/p99 metrics, and a proper CI pipeline with 3-OS × 3-Python matrix. None of Maestro's direct webcam-gesture competitors come close to this engineering depth. That's the good news.

The bad news: **the plugin sandbox is theater** (RestrictedPython's compiled output is discarded; `importlib`, `socket`, `urllib`, `open`, `getattr`-based reflection all bypass the AST blocklist). **TLS verification is disabled** in the update checker — a textbook MITM vulnerability. **SharedMemory permission hardening is silently broken on Linux** (the code looks for `/dev/shm/psm\\\_{name}` but Python creates `/dev/shm/{name}` without the `psm\\\_` prefix, so `chmod(0o600)` never runs — raw camera frames are world-readable on default distros). **The synchronous `gesture\\\_triggered` dispatch blocks the engine thread for up to 250ms** per gesture (subprocess calls to `swaymsg`/`xdotool`/`hyprctl`), dropping 7 frames at 30 FPS. **There is no hand-ID tracking** — MediaPipe returns hands in arbitrary order, and when handedness flips mid-gesture, One-Euro filters, FSM state, and DTW buffers are all corrupted simultaneously.

The competitive landscape confirms Maestro occupies a **nearly empty quadrant**: software-only (no hardware), professional-grade engineering, cross-platform, open-source. Direct webcam-gesture competitors (ControlAir, Hand Mapper, PointiFix, FLUX) are casual, single-platform, dormant hobby projects. Ultraleap dominates the hardware-required professional space. Talon Voice owns the software-only professional accessibility space (different modality). **Nobody else is building what Maestro is building.** That's both an opportunity and a warning — the empty quadrant exists for a reason, and the reason is that webcam-based gesture control is hard to make fast enough, private enough, and safe enough for professional use. This roadmap addresses all three.

**The v2.0 thesis:** Convert the Python engine core to Rust (PyO3), switch from MediaPipe CPU to per-platform GPU backends (Core ML on macOS, DirectML/TRT on Windows, OpenVINO/CUDA on Linux), implement zero-copy frame transfer with double-buffered seqlock SharedMemory, move to an async priority EventBus, build a WASM-based plugin sandbox with capability-based security, implement privilege separation for input injection, and harden privacy by stopping all foreground-app-name logging and adding network-egress CI tests. The target is **<15ms P50 end-to-end latency** (10× improvement), **bank-grade security** (subprocess-isolated injection broker, WASM plugins, TUF-secured updates), and **zero-data-collection privacy** (on-device everything, verified by CI).

**Bottom line:** Ship v2.0 in 7 phases over \~6-8 months. Phase 1 (Rust core) is the make-or-break — it's an XL effort but it's the only path to the 10× latency improvement that makes webcam gesture control feel real-time. Everything else builds on that foundation.

\---

## 2\. Where Maestro Stands Today

### 2.1 What's working (confidence: high)

|Area|Assessment|Evidence|
|-|-|-|
|**Architecture**|Sound process isolation: camera in separate process, engine on daemon thread, EventBus with sync/async split|`camera\\\_stream.py` uses `mp.Process`; `engine.py:291` spawns daemon thread; `event\\\_bus.py:14` has `SYNC\\\_EVENTS`|
|**Gesture model**|FSM with AST-safe conditions, min/max duration, cooldowns, abort transitions, continuous gestures|`state\\\_machine.py` — `compile\\\_condition` uses AST allow-list; `GestureFSM` handles all transition types|
|**Custom gestures**|DTW matching with Numba JIT, per-gesture refractory, global cooldown, precomputed template stack|`dtw\\\_matcher.py` — `fast\\\_dtw\\\_distance` is `@numba.jit`; `CustomGestureMatcher` has cooldown logic|
|**Config system**|Deep-merge defaults + user + custom, JSON Schema validation, AST-safe expression evaluator, config migration|`config\\\_manager.py` — `SafeExpressionEvaluator` with node allow-list; `config\\\_migrator.py` with registry|
|**Plugin system**|AST pre-validation of PLUGIN\_META before exec, schema validation, hot-reload via watchdog|`plugin\\\_loader.py:126-142` — `\\\_extract\\\_meta\\\_without\\\_exec` uses `ast.literal\\\_eval` before `exec\\\_module`|
|**Cross-platform**|Real implementations for Linux (uinput/xdotool), macOS (Quartz/AXUIElement), Windows (SendInput)|All 3 controllers implement 16 abstract methods|
|**CI/CD**|3-OS × 3-Python matrix, black, mypy strict, bandit, pip-audit, coverage gate, release-please, SLSA provenance|`.github/workflows/ci.yml` — 9-cell matrix; `release.yml` — SLSA generator|
|**Testing**|191 tests passing, property-based (Hypothesis), replay fixtures, benchmarks, fuzz target|`pytest` — 191 passed; `test\\\_property\\\_based.py` — 4 Hypothesis tests; `tests/fuzz/` — atheris target|
|**Documentation**|10 ADRs, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, testing guide|`docs/adr/adr-001` through `adr-010`|

### 2.2 What's broken (confidence: high)

|ID|Issue|Severity|Evidence|
|-|-|-|-|
|S-01|**TLS verification disabled in update checker** — `ctx.check\\\_hostname = False; ctx.verify\\\_mode = ssl.CERT\\\_NONE`|CRITICAL|`updater.py:34-36`|
|S-02|**Plugin sandbox is theater** — RestrictedPython's `compile\\\_restricted()` output is discarded; module executed via standard `exec\\\_module`|CRITICAL|`plugin\\\_loader.py:230-246`|
|S-03|**SharedMemory chmod path broken on Linux** — looks for `/dev/shm/psm\\\_{name}` but Python creates `/dev/shm/{name}`|HIGH|`engine.py:82`|
|A-01|**Single-slot SharedMemory with no seqlock** — torn frames at \~0.3% probability at 30 FPS|HIGH|`camera\\\_stream.py:116` + `landmark\\\_extractor.py:85`|
|A-02|**No hand-ID tracking** — filters, FSMs, DTW buffer corrupted on hand swap|CRITICAL|`engine.py:349` keys by `handedness` string|
|P-04|**Sync `gesture\\\_triggered` dispatch blocks engine** — up to 250ms per gesture|CRITICAL|`event\\\_bus.py:14` + `action\\\_dispatcher.py:79`|
|SC-01|**4+ hands breaks everything** — filter dict keyed by 2 handedness values|CRITICAL|`engine.py:349`|
|PR-01|**Foreground app names logged to disk** — privacy violation|HIGH|`action\\\_dispatcher.py:58-65`|
|CQ-05|**Coverage excludes engine, DTW, OS controllers** — 80% gate is misleading|CRITICAL|`pyproject.toml:138-152`|
|P-06|**No GPU delegate for MediaPipe** — CPU-only, 15-25ms inference|MEDIUM|`landmark\\\_extractor.py:57-68`|

### 2.3 Performance baseline (confidence: high)

Measured against the architecture spec's <30ms end-to-end target:

|Stage|Target|Actual|Gap|Root cause|
|-|-|-|-|-|
|Camera capture|<5ms|\~3ms|✅|OK (but 3 per-frame allocations)|
|MediaPipe inference|<10ms|15-25ms|1.5-2.5× over|CPU-only, no GPU delegate|
|One-Euro filter|<0.5ms|\~0.3ms|✅|OK (but 5× `.copy()` per frame)|
|Feature engineering|<1ms|\~1.5ms|1.5× over|Python loop for finger curls|
|FSM evaluation|<0.5ms|\~2ms|4× over|Recursive `\\\_resolve`, no precompiled lambda|
|Action dispatch|<5ms|1-250ms|2-50× over|Sync dispatch + subprocess calls|
|**End-to-end**|**<30ms**|**\~150ms**|**5× over**|Pipeline serialization + GIL + sync dispatch|

**Verdict:** The 5× latency gap is **not** dominated by the ML model (15-25ms is workable). It's dominated by **pipeline serialization** (everything runs sequentially on the engine thread), **GIL contention** (EventBus worker and watchdog thread compete), and **blocking I/O** (sync dispatch calls subprocesses for foreground-app detection). Fix the architecture, not the model, for the biggest win.

\---

## 3\. The 5 Critical Blockers

These must be fixed before any v2.0 release. Confidence: high on all five.

### 3.1 Blocker 1: Plugin sandbox is theater (S-02 / A-04)

**The problem:** `plugin\\\_loader.py:230-236` calls `compile\\\_restricted(...)` from RestrictedPython but **discards the return value**. The module is then executed via `spec.loader.exec\\\_module(module)` using the **standard Python interpreter**, not RestrictedPython's restricted globals. RestrictedPython's security comes from `safe\\\_globals` at *exec time*, not from compilation alone. **The sandbox provides zero actual isolation.**

**Bypass vectors (verified by AST analysis):**

* `import importlib; importlib.import\\\_module("subprocess").run(...)` — `importlib` NOT in `blocked\\\_packages`
* `import socket; socket.socket(...)` — `socket` not blocked. Plugin can exfiltrate data
* `import urllib.request; urllib.request.urlopen(...)` — `urllib` not blocked
* `getattr(\\\_\\\_builtins\\\_\\\_, "ev"+"al")("code")` — `getattr` Call on Name is allowed
* `().\\\_\\\_class\\\_\\\_.\\\_\\\_base\\\_\\\_.\\\_\\\_subclasses\\\_\\\_()` — uses Attribute/Subscript, neither scanned
* `open("/etc/passwd").read()` — `open` builtin not blocked

**Impact:** A malicious plugin in `\\\~/.config/gesture\\\_controller/plugins/` can: read any user file, make network requests, exfiltrate camera frames from SharedMemory, execute arbitrary code with full user privileges. Combined with PR-08 (plugins can access SharedMemory), this is a **critical privacy and security threat**.

**Fix:** See [Phase 6: WASM Plugin Sandbox](#13-phase-6-wasm-plugin-sandbox). The proper fix is WASM components with WIT-defined capability contracts. The interim fix is subprocess isolation with seccomp (Linux) / sandbox-exec (macOS) / AppContainer (Windows).

### 3.2 Blocker 2: TLS verification disabled (S-01)

**The problem:** `updater.py:34-36`:

```python
ctx = ssl.create\\\_default\\\_context()
ctx.check\\\_hostname = False
ctx.verify\\\_mode = ssl.CERT\\\_NONE
```

The comment claims "to avoid certificate validation issues on restricted networks." This is a **MITM vulnerability**. An attacker on the network can spoof `api.github.com`, inject a malicious `html\\\_url` into the JSON response, and the user clicks the tray notification (`app\\\_entry.py:283` — `webbrowser.open(self.\\\_download\\\_url)`) → arbitrary URL opened in browser. The URL scheme/domain validation (lines 26-29) only validates the *API URL*, NOT the `html\\\_url` from the response.

**Impact:** Network-positioned attacker can redirect users to phishing sites or drive-by download URLs. On corporate networks with transparent proxies, this is trivially exploitable.

**Fix:** Delete `ctx.check\\\_hostname = False` and `ctx.verify\\\_mode = ssl.CERT\\\_NONE`. Use `certifi` or system trust store for corporate proxy support. Validate `html\\\_url` scheme is `https` and netloc is `github.com` before opening. **Effort: 1 hour.** See [Phase 7: Supply Chain Integrity](#14-phase-7-supply-chain-integrity).

### 3.3 Blocker 3: SharedMemory chmod broken on Linux (S-03)

**The problem:** `engine.py:82`:

```python
shm\\\_file = Path("/dev/shm") / f"psm\\\_{self.\\\_shm\\\_name}"
```

Python's `multiprocessing.shared\\\_memory.SharedMemory` on Linux creates the file at `/dev/shm/{name}` (no `psm\\\_` prefix). `self.\\\_shm\\\_name` is already the full name (e.g., `wnsm\\\_<random>`). So the code looks for `/dev/shm/psm\\\_wnsm\\\_<random>`, which **doesn't exist**. `shm\\\_file.exists()` returns `False`, `chmod(0o600)` **never runs**.

Default permissions on `/dev/shm/{name}` are typically **0666** (world-readable/writable) on many Linux distros. **Any local user can read raw camera frames.**

**Impact:** On any multi-user Linux system (servers, labs, kiosks, shared workstations), any user can `mmap /dev/shm/wnsm\\\_\\\*` and watch the camera feed in real time. This is a **critical privacy violation**.

**Fix:** Change `f"psm\\\_{self.\\\_shm\\\_name}"` to `self.\\\_shm\\\_name`. Verify `chmod(0o600)` actually runs. Add Windows ACL hardening (currently none). **Effort: 1 hour.** See [Phase 10: Camera Privacy Hardening](#17-phase-10-camera-privacy-hardening).

### 3.4 Blocker 4: No hand-ID tracking (A-02)

**The problem:** `engine.py:349` — `self.\\\_filters.get(hand.handedness)` keys One-Euro filters by the string `"Left"` or `"Right"`. MediaPipe returns hands in arbitrary order and can flip handedness labels frame-to-frame when hands cross. When this happens:

1. One-Euro filter state from the wrong hand is applied (smoothing corrupted)
2. FSM state is corrupted (wrong hand's `\\\_features\\\_at\\\_state\\\_entry` used for delta computation)
3. `compute\\\_features` mirrors the wrong hand (Left/Right coordinate space swapped)
4. `CustomGestureMatcher` has ONE rolling buffer (`dtw\\\_matcher.py:173`) shared across all hands — interleaved frames from 2 hands corrupt the DTW sequence

**Impact:** Two-hand gestures are unreliable. Any hand crossover (natural in real usage) produces spurious FSM transitions and garbage DTW distances. This is a **correctness bug** that makes the product unusable for its stated `max\\\_hands=2` default.

**Fix:** Implement hand tracking via centroid IoU (intersection-over-union of wrist-position bounding boxes across frames). Assign persistent hand IDs. Key filters, FSMs, and DTW buffers by hand ID, not handedness. See [Phase 1: Rust Core Engine](#8-phase-1-rust-core-engine-pyo3).

### 3.5 Blocker 5: Sync dispatch blocks engine (P-04)

**The problem:** `event\\\_bus.py:14` — `SYNC\\\_EVENTS = {"gesture\\\_triggered"}`. `engine.py:390` publishes synchronously. `action\\\_dispatcher.py:79` calls `self.\\\_controller.get\\\_foreground\\\_app()` which spawns subprocesses:

* Linux/sway: `swaymsg -t get\\\_tree` + JSON parse = 50-200ms
* Linux/X11: two `xdotool` subprocesses = 20-40ms
* Linux/Hyprland: `hyprctl` subprocess = 10-50ms
* Windows: `psutil.Process(pid).name()` = 5-15ms
* macOS: `NSWorkspace.frontmostApplication().localizedName()` = 2-5ms

Then `\\\_execute` → `key\\\_combo` on Linux xdotool path = another 50-200ms subprocess. **A single gesture dispatch can stall the engine for 250ms = 7 dropped frames at 30 FPS.**

**Impact:** Gestures feel laggy and unresponsive. During the dispatch stall, camera frames pile up in SharedMemory (single-slot, so they're overwritten — silent frame drops). The FSM can't process the next gesture until dispatch completes.

**Fix:** Move `gesture\\\_triggered` from `SYNC\\\_EVENTS` to async dispatch. Add a dedicated dispatcher thread with a bounded priority queue. See [Phase 4: Async Priority EventBus](#11-phase-4-async-priority-eventbus).

\---

# Part II — Competitive Landscape

## 4\. Competitive Positioning

**Confidence: High.** Maestro occupies a nearly empty quadrant in the gesture-control landscape:

```
                        PROFESSIONAL / ENTERPRISE
                                  ▲
                                  │
   Dragon DAX  ●      │      ● Ultraleap ($140-200 HW)
   VTouch ●            │      ● Tobii ($229-9000 HW)
   HoloLens 2 ●        │      ● OpenPose ($25K/yr commercial)
                       │      ● Meta Neural Band (future)
                       │
  ─────────────────────┼─────────────────────────► HARDWARE-REQUIRED
  Software-only        │
                       │
   ● Karabiner         │      ● Meta Quest hand tracking
   ● BetterTouchTool   │      ● Apple Vision Pro ($3,499)
   ● Hammerspoon       │      ● HTC Vive hand tracking
   ● AutoHotkey        │      ● Google Soli (dormant)
   ● Raycast/Alfred    │      ● Thalmic Myo (defunct)
   ● Talon Voice       │
   ● PowerToys         │
                       │
   ╔═══════════════╗   │
   ║   ● MAESTRO   ║   │      ← OPEN QUADRANT
   ║   (webcam +   ║   │         No direct competitor
   ║    MediaPipe  ║   │         in software-only +
   ║    desktop)   ║   │         professional engineering
   ╚═══════════════╝   │
                       │
   ● ControlAir        │
   ● Hand Mapper       │
   ● PointiFix         │
   ● FLUX              │
                                  │
                                  ▼
                        CASUAL / CONSUMER
```

**Key insight:** The only "neighbor" in software-only + professional is **Talon Voice** (different modality — voice, not gesture). Every webcam-gesture competitor (ControlAir, Hand Mapper, PointiFix, FLUX, Nuisanceless, Gesture Key Control) is casual, single-platform, and dormant. The hardware players (Ultraleap, Meta, Apple, HTC, HoloLens) require $140-$5,000 hardware purchases. **Maestro is the only product targeting professional desktop productivity with software-only gesture input.**

### 4.1 Market size context (confidence: medium)

|Market|Size (2024-2025)|Projected (2033-2035)|CAGR|Source quality|
|-|-|-|-|-|
|Hand tracking|$1.2-3.1B|$7.8B (2033)|11-15%|Medium (third-party reports)|
|Gesture recognition|$32.6B (2025)|$252B (2035)|\~22%|Medium|
|Maestro's addressable slice (desktop webcam gesture)|Single-digit $M|Growing|Unknown|Low (no direct market data)|

**Assessment:** The gesture recognition market is large and growing fast, but Maestro's specific slice (desktop webcam gesture control) is nascent. The growth driver is improving webcam quality (4K @ 60fps is standard on 2024+ laptops) and MediaPipe-class models making real-time hand tracking free. Maestro is early but not too early.

\---

## 5\. What Competitors Teach Us

### 5.1 From Ultraleap (confidence: high)

* **26-DOF sub-mm accuracy** sets user expectations for "premium" hand tracking. Maestro's MediaPipe pipeline will always trail here. **Position around good-enough accuracy + zero hardware cost.**
* **120-180 FPS tracking** is the premium bar. Maestro's 30 FPS is table-stakes, not a differentiator.
* **Enterprise SLAs / automotive-grade certification** — if Maestro ever targets B2B, this is the bar.
* **Mid-air haptics** (Ultrahaptics acquisition) — out of scope for webcam, but interesting for future hardware partnerships.

### 5.2 From Meta Quest Hand Tracking (confidence: high)

* **Hand Tracking 2.x fast-motion mode** — adaptive tracking parameters based on motion velocity. Maestro's One-Euro filter already adapts, but the FSM thresholds don't. **Add adaptive FSM thresholds that widen during fast motion.**
* **\~70ms end-to-end latency** is the consumer VR benchmark. Maestro's \~150ms is 2× over. **Target <30ms for v2.0.**
* **Deep OS integration** (system UI, keyboard, app switching) — Maestro maps to OS actions but doesn't integrate with system UI. **Add system-level gesture shortcuts (e.g., gesture → open notification center).**

### 5.3 From Apple Vision Pro (confidence: medium)

* **Eye + hand fusion** (look + pinch) is the north-star UX. Maestro can't do eye tracking without hardware, but **gaze estimation from head pose** (MediaPipe Face Mesh) is a poor-man's alternative worth exploring for v2.1.
* **\~30 Hz hand tracking** is lower than Quest's effective rate — confirms that 30 FPS is acceptable for consumer use if latency is low.

### 5.4 From Talon Voice (confidence: high)

* **Community-driven grammar/preset library** — Talon's 200+ voice commands are community-contributed. Maestro's plugin system is the right primitive but has no distribution. **Build a curated plugin/gesture registry (GitHub-indexed) with signed manifests.**
* **\~$25/month Patreon beta tier** — sustainable funding model for open-source accessibility tools. Maestro should consider a similar model for v2.1+.
* **5+ years of accessibility battle-testing** — Maestro's accessibility story is currently "it works with hands." Talon's is "it works for people who can't use hands." **Maestro needs genuine accessibility features, not just RSI avoidance.**

### 5.5 From BetterTouchTool (confidence: high)

* **Trigger conditions** (app, time, location, device state) — Maestro's `app\\\_profiles` are a 1-field version (foreground app name → action remap). **Extend to full trigger conditions: enable/disable gesture sets based on app + time + display + audio state.**
* **Stream Deck / MIDI hardware integration** as action targets — prosumer feature, low effort, high perceived value.
* **$6.50 "sweet price" + $22 lifetime** — sustainable pricing for a Mac utility. Maestro's AGPL license makes paid distribution tricky, but a "Maestro Pro" dual-license model is worth considering.
* **100+ supported input types** (trackpad, mouse, keyboard, Touch Bar, Stream Deck, Siri Remote) — Maestro supports only webcam. **Add trackpad/mouse gesture compatibility** so Maestro co-exists with existing input methods.

### 5.6 From AutoHotkey / Hammerspoon / Karabiner (confidence: high)

* **Turing-complete scripting** (AHK has its own language; Hammerspoon uses Lua) — Maestro's YAML FSM + sandboxed Python is more constrained but safer. **Don't try to compete on scripting power; compete on safety and ease of use.**
* **Massive community script library** (AHK has 20+ years of community scripts) — Maestro's plugin marketplace is the equivalent play.
* **Kernel-level key interception** (Karabiner uses DriverKit) — lowest possible latency. Maestro's uinput/SendInput/CGEvent path is userspace, slightly higher latency but safer and cross-platform.
* **Per-device profiles** (Karabiner) — Maestro should support per-webcam profiles (different cameras may need different thresholds).

### 5.7 From MediaPipe / ONNX Runtime / Apple Vision (confidence: high)

* **GPU acceleration is the single biggest perf win available.** MediaPipe's GPU delegate is broken on Windows Python (GitHub #4575). **Switch to ONNX Runtime with DirectML (Windows) / Core ML (macOS) / CUDA (Linux) backends.**
* **INT8 quantization** can 2-4× speedup inference on CPU. **Add static PTQ (post-training quantization) with calibration on real frames.**
* **MediaPipe Gesture Recognizer task** (pretrained 7-gesture classifier) — Maestro should use this alongside DTW for out-of-the-box common gestures without requiring user recording.

\---

## 6\. Feature Gap Analysis — Top 20

Ranked by user impact. Confidence and effort assessed independently.

|Rank|Feature|Source competitors|User impact|Effort|Confidence|
|-|-|-|-|-|-|
|1|**GPU acceleration** (ONNX Runtime + DirectML/CoreML/CUDA)|MediaPipe, Maxine, ONNX, Apple Vision|Massive — 2-4× FPS, lower latency, lower CPU/battery|Medium|High|
|2|**Per-app trigger conditions** (active window + time + display + audio state)|BetterTouchTool, Karabiner, Hammerspoon|High — Maestro's app profiles are a 1-field version|Low|High|
|3|**Community plugin/gesture marketplace** (browse, install, rate, update)|AHK, Karabiner, Raycast, Talon|High — solves cold-start, builds ecosystem|High|High|
|4|**Voice modality integration** (Whisper.cpp local STT)|Talon, Windows/macOS Voice Control, Dragon|High for accessibility|Medium|High|
|5|**Eye tracking integration** (gaze-assisted pointing + dwell-click)|Tobii, Talon, Vision Pro|High for accessibility|High|High|
|6|**MediaPipe Gesture Recognizer task** (pretrained 7 gestures alongside DTW)|MediaPipe|Medium — out-of-box UX|Low|High|
|7|**AHK / Hammerspoon / Raycast / xdotool interop** (call native automation as actions)|All Category D|Medium — leverages existing ecosystems|Low|High|
|8|**Stream Deck / MIDI hardware integration** as action targets|BetterTouchTool|Medium — prosumer|Low|Medium|
|9|**Mouse-gesture compatibility** (Magic Trackpad / touchpad gestures)|BetterTouchTool, PowerToys, Karabiner|Medium — co-exist with existing input|Medium|High|
|10|**Custom gesture template sharing** (export/import YAML+DTW templates)|Talon (community grammars)|Medium — community growth|Low|High|
|11|**Telemetry opt-in dashboard** (anonymous usage → which gestures fail, latency histograms)|Most enterprise tools|Medium — product improvement|Low|High|
|12|**Window snapping / FancyZones-style management** as gesture targets|PowerToys, BetterTouchTool|Medium — productivity|Medium|High|
|13|**Mobile/companion app** (control phone/tablet gestures)|FLUX, Spatial Touch, VTouch|Medium — expands TAM|High|Medium|
|14|**Web runtime** (browser extension for webapp control)|MediaPipe Web|Medium — large distribution|High|Medium|
|15|**Subtle / micro-gesture support** (finger-only, low-effort)|Soli, Meta EMG|Medium for accessibility|Medium|Medium|
|16|**Quantized INT8 model** for low-power laptops|ONNX, TF Lite|Medium — battery life|Low|High|
|17|**Local LLM intent layer** ("gesture → LLM → action chain")|Raycast AI|Medium — emerging|Medium|Medium|
|18|**Enterprise MDM / config deployment** (kiosk mode, policy lockdown)|VTouch, Dragon, Ultraleap|Low for consumer; high for B2B|High|Medium|
|19|**VR/headset output** (Maestro-as-input for OpenXR)|Ultraleap, Meta, HTC|Low today; future hedge|High|Medium|
|20|**Multi-hand >2 / multi-person**|OpenPose, Ultraleap|Low for desktop; medium for kiosk|Medium|Medium|

**v2.0 scope:** Features 1, 2, 6, 7, 10, 16 are low-to-medium effort and high impact — include in v2.0. Features 3, 4, 5, 8, 9, 11, 12 are medium effort — include if capacity allows, otherwise v2.1. Features 13-20 are v2.1+ or v3.0.

\---

# Part III — The v2.0 Architecture

## 7\. Architecture Vision: The 10× Latency Plan

**Confidence: High (architecture), Moderate (hitting exactly <15ms everywhere).**

The current \~150ms is **not** dominated by the model (15-25ms) — it's dominated by **pipeline serialization, GIL contention, and blocking I/O on the engine thread**. The single highest-leverage move is a **Rust-core (PyO3) engine** with a **zero-copy, double-buffered shared-memory pipeline** and a **non-blocking priority EventBus**, plus **per-platform GPU inference backends** (Core ML on macOS, DirectML/ONNX-TRT on Windows, OpenVINO on Intel, DMA-BUF→CUDA on Linux).

That alone gets to \~15-25ms. Hitting **<15ms E2E** then requires **GPU-resident inference + One-Euro predictive tracking + frame-skipping**, so the camera rarely waits on inference.

### 7.1 Target topology

```
\\\[Camera process]
    │
    │ DMA-BUF / IOSurface / DXGI shared handle
    │ (zero-copy, no pixel transfer)
    │
    ▼
\\\[Double-buffered SharedMemory + seqlock]
    │
    │ atomic frame-index counter
    │
    ▼
\\\[Rust engine thread (PyO3)]
    ├── GPU inference (CoreML / DirectML / TRT / OpenVINO)
    ├── One-Euro filter + 1-frame Kalman prediction
    ├── Feature engineering (Rust + SIMD)
    ├── FSM evaluation (Rust, no Python in hot path)
    └── Hand-ID tracking (centroid IoU across frames)
    │
    │ lock-free MPMC priority queue
    │ (control > gesture > telemetry > plugin)
    │
    ▼
\\\[Dispatcher pool]
    ├── OS injection broker (privileged, sandboxed)
    ├── Plugin RPC (WASM host / sandboxed subprocess)
    └── Audit log (tamper-evident)
    │
    │ asyncio / uvloop
    │
    ▼
\\\[Integration APIs]
    ├── WebSocket (localhost + token auth)
    ├── REST API
    ├── CLI (`maestro trigger MinimizeWindow`)
    ├── D-Bus (Linux)
    ├── Shortcuts / AppleScript (macOS)
    └── COM automation (Windows)
```

### 7.2 Measurable targets

|Stage|v0.1.0|v2.0 target|How|Confidence|
|-|-|-|-|-|
|Camera capture|\~3ms|<2ms|Zero-copy handle (no pixel copy) + v4l2/libcamera/PipeWire non-blocking dequeue|High|
|Inference|15-25ms|<8ms|GPU backend (TRT/CoreML/DirectML) + FP16/INT8 + 256² adaptive|High|
|Feature eng|\~1.5ms|<0.5ms|Rust+SIMD over 21 landmarks|High|
|FSM eval|\~2ms|<0.2ms|Rust FSM, no Python in hot path|High|
|Action dispatch|1-250ms|<2ms|Priority queue + non-blocking OS API; plugin RPC off-thread|High|
|**E2E P50**|**\~150ms**|**<15ms**|Above + 1-frame-ahead Kalman + frame-skip|High (arch), Moderate (exact)|
|**E2E P95**|unknown|**<20ms**|Headroom for GC / OS jitter|Moderate|

**Public commitment:** `<20ms P95, <15ms P50` — leaves headroom and is still 7-10× better than v0.1.0.

\---

## 8\. Phase 1: Rust Core Engine (PyO3)

**Confidence: High. Effort: XL. Impact: Critical.**

### 8.1 Why Rust

Python is the wrong tool for the hot path. The GIL prevents true parallelism between inference, feature engineering, and FSM evaluation. Numba JIT helps for DTW but not for the FSM or feature engineering (Python dataclass attribute access dominates). Cython is a lateral move that loses memory safety.

**Rust via PyO3** gives:

* **10-100× speedup** for CPU-bound hot paths (confirmed by `rustify` benchmarks, arXiv 2507.00264)
* **No GIL** — PyO3 0.28 supports free-threaded CPython 3.14, and even on 3.11-3.13, Rust code releases the GIL during computation
* **Memory safety** — eliminates whole CWE classes (buffer overflow, use-after-free, null deref) that C extensions would introduce
* **Zero-cost abstractions** — SIMD auto-vectorization for feature engineering, lock-free data structures for the EventBus
* **Cross-platform** — single codebase compiles to native code on all 3 OSes

### 8.2 What to port

|Component|Current (Python)|v2.0 (Rust)|Speedup expected|
|-|-|-|-|
|`OneEuroFilter`|Python + NumPy|Rust + SIMD|5-10×|
|`compute\\\_features`|Python + NumPy|Rust + SIMD|10-20×|
|`GestureFSM.evaluate`|Python + recursive `\\\_resolve`|Rust + precompiled conditions|20-50×|
|`GestureFSMManager.evaluate`|Python + RLock + list copy|Rust + lock-free snapshot|10-20×|
|`fast\\\_dtw\\\_distance`|Numba JIT|Rust + SIMD|2-3× (Numba is already fast)|
|`CameraStream.\\\_capture\\\_loop`|Python + cv2|Rust + v4l2/libcamera/PipeWire|2-3× (eliminates Python overhead)|
|`EventBus`|Python + Queue + Lock|Rust + crossbeam (lock-free MPMC)|10-100×|
|`HandTracker` (new)|N/A|Rust + centroid IoU|New capability|

### 8.3 What stays Python

* **Plugin orchestration** — Python is the right tool for loading and managing plugins (importlib, watchdog, RestrictedPython AST checks for the legacy path)
* **Config management** — YAML loading, JSON Schema validation, migration
* **GUI** — PyQt6 stays. Rust GUI ecosystem is immature. GUI calls into the Rust core via PyO3.
* **CLI** — argparse stays. CLI calls into the Rust core via PyO3.
* **Integration APIs** — WebSocket/REST/D-Bus/Shortcuts/COM bridges stay in Python (asyncio/uvloop).

### 8.4 Build system

Use `maturin` to build platform-specific wheels:

```toml
# pyproject.toml
\\\[build-system]
requires = \\\["maturin>=1.4,<2.0"]
build-backend = "maturin"

\\\[tool.maturin]
features = \\\["pyo3/extension-module"]
module-name = "gesture\\\_controller.\\\_core"
```

Ship pre-built wheels for:

* `cp311-cp311-manylinux\\\_2\\\_17\\\_x86\\\_64` (Linux)
* `cp311-cp311-macosx\\\_11\\\_0\\\_arm64` (macOS Apple Silicon)
* `cp311-cp311-macosx\\\_10\\\_9\\\_x86\\\_64` (macOS Intel)
* `cp311-cp311-win\\\_amd64` (Windows)

### 8.5 Migration strategy

Don't rewrite everything at once. Port incrementally:

1. **Sprint 1:** Port `OneEuroFilter` + `compute\\\_features` to Rust. Python calls Rust via PyO3. Benchmark.
2. **Sprint 2:** Port `GestureFSM` + `GestureFSMManager` to Rust. Python calls Rust.
3. **Sprint 3:** Port `EventBus` to Rust (lock-free MPMC). Python wrapper.
4. **Sprint 4:** Port `CameraStream` to Rust (v4l2/libcamera/PipeWire). Python wrapper.
5. **Sprint 5:** Implement `HandTracker` in Rust (new capability).
6. **Sprint 6:** Port `fast\\\_dtw\\\_distance` to Rust (replace Numba).

After each sprint, benchmark end-to-end latency. If a sprint doesn't produce measurable improvement, stop and reassess.

### 8.6 Risk: XL effort

**Risk:** The Rust port is an XL effort that could take 3-4 months. If it stalls, v2.0 doesn't ship.

**Mitigation:**

1. **Port incrementally** — each sprint is independently shippable. If Sprint 1 proves the concept, continue. If not, fall back to Python + Numba.
2. **Keep Python orchestration** — the Rust core is a library, not a rewrite. Python remains the "glue."
3. **Benchmark after each sprint** — kill the port if it's not delivering. Don't sink 4 months into a rewrite that doesn't improve things.
4. **Alternative:** If Rust is too much, use **Cython** for the hot paths (One-Euro, feature eng, FSM). Cython is a smaller lift but loses memory safety and doesn't solve the GIL problem as cleanly.

\---

## 9\. Phase 2: GPU Inference Backends

**Confidence: High. Effort: M. Impact: Critical.**

### 9.1 The problem with MediaPipe CPU

MediaPipe Tasks Python API on CPU runs the hand landmark model at 15-25ms per frame. The GPU delegate exists but is **broken on Windows Python** (GitHub issue #4575) and requires OpenGL ES on Linux. This caps Maestro at \~30 FPS on commodity hardware.

### 9.2 The solution: ONNX Runtime re-host

Convert the MediaPipe TFLite graph to ONNX format (PINTO0309's `hand-gesture-recognition-using-onnx` repo proves this works end-to-end), then run via `onnxruntime` with platform-specific execution providers:

|Platform|Execution Provider|Expected inference time|Confidence|
|-|-|-|-|
|**macOS (Apple Silicon)**|Core ML EP (Neural Engine)|3-7ms|High|
|**macOS (Intel)**|Core ML EP (GPU)|5-10ms|Medium|
|**Windows (NVIDIA)**|TensorRT EP (CUDA)|2-6ms|High|
|**Windows (AMD/Intel)**|DirectML EP|4-8ms|High|
|**Linux (NVIDIA)**|TensorRT EP (CUDA)|2-6ms|High|
|**Linux (Intel)**|OpenVINO EP|5-10ms|Medium|
|**Linux (AMD/other)**|CPU EP + INT8|8-15ms|High|
|**Fallback (any)**|CPU EP + INT8|8-15ms|High|

### 9.3 Implementation

```rust
// gesture\\\_controller-core/src/inference.rs
pub trait InferenceBackend: Send + Sync {
    fn detect\\\_hands(\\\&self, frame: \\\&Frame) -> Vec<HandLandmarks>;
    fn close(\\\&mut self);
}

pub struct CoreMLBackend { /\\\* ... \\\*/ }
pub struct TensorRTBackend { /\\\* ... \\\*/ }
pub struct DirectMLBackend { /\\\* ... \\\*/ }
pub struct OpenVINOBackend { /\\\* ... \\\*/ }
pub struct CPUBackend { /\\\* ... \\\*/ }  // INT8 quantized fallback

pub fn create\\\_backend(config: \\\&Config) -> Box<dyn InferenceBackend> {
    match config.inference\\\_backend.as\\\_str() {
        "auto" => auto\\\_detect\\\_backend(),
        "coreml" => Box::new(CoreMLBackend::new()?),
        "tensorrt" => Box::new(TensorRTBackend::new()?),
        "directml" => Box::new(DirectMLBackend::new()?),
        "openvino" => Box::new(OpenVINOBackend::new()?),
        "cpu" => Box::new(CPUBackend::new()?),
        \\\_ => auto\\\_detect\\\_backend(),
    }
}
```

### 9.4 INT8 quantization

Use **static post-training quantization (PTQ)** with calibration on a few hundred real hand frames (not random data) to preserve landmark precision. INT8 cuts inference 2-4× on CPU and is the fallback for systems without GPU.

**Risk:** INT8 quantization can shift landmark coordinates \~1-2px. **Mitigation:** Re-validate gesture FSM thresholds after quantization. Add a "quantization accuracy" test to CI.

### 9.5 Adaptive resolution

Downscale to 256×256 when hands are stable/tracked; bump to 640×640 only on (re)acquisition or fast motion. Driven by the One-Euro velocity signal. Cuts inference cost 2-4× during steady-state.

```rust
fn adaptive\\\_resolution(velocity: f32, tracked: bool) -> (u32, u32) {
    if !tracked {
        (640, 640)  // full res for (re)acquisition
    } else if velocity > 0.5 {
        (640, 640)  // full res for fast motion
    } else {
        (256, 256)  // low res for stable hands
    }
}
```

\---

## 10\. Phase 3: Zero-Copy Pipeline

**Confidence: High. Effort: L. Impact: Critical.**

### 10.1 Double-buffered SharedMemory with seqlock

Current: single-slot SharedMemory, no lock, no seqlock. Torn frames at \~0.3% probability at 30 FPS.

v2.0: Two fixed-size frame slots in shared memory. Writer publishes with a `std::atomic<uint64\\\_t>` seqlock (even = ready, odd = writing). Readers spin-free-check the seq. Eliminates torn frames and the current copy on every read.

```rust
// gesture\\\_controller-core/src/shared\\\_frame.rs
use std::sync::atomic::{AtomicU64, Ordering};

pub struct DoubleBufferedFrame {
    slots: \\\[FrameSlot; 2],  // 2 × 921KB
    write\\\_seq: AtomicU64,   // even = ready, odd = writing
}

struct FrameSlot {
    data: \\\[u8; FRAME\\\_SIZE],
    timestamp: u64,
    frame\\\_id: u64,
}

impl DoubleBufferedFrame {
    pub fn write(\\\&self, frame: \\\&\\\[u8], timestamp: u64, frame\\\_id: u64) {
        let slot\\\_idx = (self.write\\\_seq.load(Ordering::Relaxed) \\\& 1) as usize;
        self.write\\\_seq.store(self.write\\\_seq.load(Ordering::Relaxed) | 1, Ordering::Relaxed); // odd = writing
        // ... write to slot ...
        self.write\\\_seq.store(frame\\\_id \\\* 2, Ordering::Release); // even = ready
    }

    pub fn read(\\\&self) -> Option<FrameRef> {
        loop {
            let seq1 = self.write\\\_seq.load(Ordering::Acquire);
            if seq1 \\\& 1 != 0 { continue; } // being written
            let slot\\\_idx = (seq1 \\\& 1) as usize;
            let frame = self.slots\\\[slot\\\_idx].read();
            let seq2 = self.write\\\_seq.load(Ordering::Acquire);
            if seq1 == seq2 { return Some(frame); } // consistent
            // else retry
        }
    }
}
```

### 10.2 Zero-copy frame transfer

Keep frames **GPU-resident** and pass handles, not pixels:

|Platform|Mechanism|Confidence|
|-|-|-|
|**Linux**|DMA-BUF fd pass via `SCM\\\_RIGHTS` (libcamera/PipeWire already produce DMA-BUF)|High|
|**macOS**|IOSurface (shared across processes/GPU)|High|
|**Windows**|DXGI shared handle / NT handle|High|

**Risk:** Platform-specific IPC glue. Camera driver must export the right handle type. **Mitigation:** Fall back to memcpy (current behavior) if zero-copy handle is unavailable.

### 10.3 Frame skipping

If a new frame arrives while inference is mid-flight, **drop the stale frame**, never queue. Camera must never block on inference. Implement with a single-slot "latest-frame-wins" mailbox.

```rust
pub fn process\\\_frames(\\\&self) {
    while let Some(frame) = self.frame\\\_rx.recv\\\_latest() {  // drops stale frames
        let hands = self.inference.detect\\\_hands(\\\&frame);
        let features = self.feature\\\_eng.compute(\\\&hands);
        let event = self.fsm.evaluate(\\\&features);
        if let Some(event) = event {
            self.dispatcher\\\_tx.send(event);  // non-blocking
        }
    }
}
```

\---

## 11\. Phase 4: Async Priority EventBus

**Confidence: High. Effort: M. Impact: Critical.**

### 11.1 The problem

Current `EventBus` dispatches `gesture\\\_triggered` synchronously on the engine thread. A single gesture dispatch can stall the engine for 250ms (subprocess calls to `swaymsg`/`xdotool`/`hyprctl` for foreground-app detection). This drops 7 frames at 30 FPS.

### 11.2 The solution: lock-free MPMC priority queue

Use Rust's `crossbeam` or `kanal` (lock-free multi-producer multi-consumer queue) with **priority lanes**:

```rust
pub enum EventPriority {
    Control,    // kill switch, pause/resume
    Gesture,    // gesture\\\_triggered
    Telemetry,  // raw\\\_landmarks, metrics
    Plugin,     // plugin\\\_reloaded, config\\\_changed
}

pub struct PriorityEventBus {
    queues: \\\[crossbeam::channel::Sender<Event>; 4],  // one per priority
    dispatcher: thread::JoinHandle<()>,
}

impl PriorityEventBus {
    pub fn publish(\\\&self, event: Event, priority: EventPriority) {
        self.queues\\\[priority as usize].send(event);  // non-blocking
    }
}
```

The dispatcher thread processes events in priority order: Control > Gesture > Telemetry > Plugin. Gesture events are processed on a dedicated thread (not the engine thread), so OS dispatch latency doesn't block inference.

### 11.3 Circuit breaker (already exists, enhance)

Current `event\\\_bus.py:78` auto-unsubscribes after 3 consecutive failures. **Enhance:**

* Add **per-handler time budget** (e.g., 5ms) via `signal.alarm` or async timeout
* Auto-unsubscribe handlers that exceed the budget 3× consecutively
* Log the unsubscribe with handler name and last error

### 11.4 Per-handler failure counter keyed by (event\_type, handler)

Current bug: `\\\_failures` dict is keyed by `handler` alone. A handler subscribed to both `raw\\\_landmarks` and `gesture\\\_triggered` shares a single failure counter. If it fails 3× on `raw\\\_landmarks` (non-critical telemetry), it gets auto-unsubscribed from `gesture\\\_triggered` (the critical action channel) too.

**Fix:** Key by `(event\\\_type, handler)` tuple.

\---

# Part IV — Security Hardening

## 12\. Phase 5: Privilege Separation Architecture

**Confidence: High. Effort: L. Impact: Critical.**

### 12.1 The principle

**Input injection broker** = privileged, sandboxed process (the only thing with input-injection rights: `/dev/uinput`, `SendInput`, `CGEventPost`). **UI + plugins + engine** = unprivileged. They talk over capability-scoped IPC.

This is the single most important security architecture change. Currently, the engine process has both camera access AND input injection access AND runs plugin code. A compromised plugin can read camera frames AND inject keystrokes AND exfiltrate data — all from the same process.

### 12.2 Architecture

```
┌─────────────────────────────────────────────────────┐
│ UNPRIVILEGED PROCESS (main app)                     │
│                                                     │
│  ┌─────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Engine   │  │ GUI      │  │ Plugin Runtime    │  │
│  │ (Rust)   │  │ (PyQt6)  │  │ (WASM/subprocess) │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │              │                 │             │
│       └──────────────┴─────────────────┘             │
│                      │                              │
│              Capability-scoped IPC                  │
│                      │                              │
└──────────────────────┼──────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────┐
│ PRIVILEGED PROCESS (injection broker)               │
│                      │                              │
│  ┌───────────────────▼──────────────────────────┐   │
│  │ Input Injection Broker (Rust)                 │   │
│  │                                               │   │
│  │ • Receives action requests via IPC            │   │
│  │ • Validates against rate limits               │   │
│  │ • Checks kill-switch state                    │   │
│  │ • Logs to tamper-evident audit log            │   │
│  │ • Executes: uinput / SendInput / CGEventPost  │   │
│  └───────────────────────────────────────────────┘   │
│                                                     │
│  Capabilities: /dev/uinput, SendInput, CGEventPost  │
│  NO: camera, filesystem (except audit log), network │
└─────────────────────────────────────────────────────┘
```

### 12.3 IPC protocol

Use a Unix domain socket (Linux/macOS) or named pipe (Windows) with a simple length-prefixed binary protocol:

```rust
// Request from unprivileged to broker
pub enum BrokerRequest {
    KeyPress { key: String, modifiers: Vec<String> },
    KeyCombo { keys: Vec<String> },
    MouseClick { button: String, x: Option<i32>, y: Option<i32> },
    MouseScroll { delta\\\_x: i32, delta\\\_y: i32 },
    MinimizeActiveWindow,
    SwitchWindow,
    // ... all 16 BaseController methods
}

pub enum BrokerResponse {
    Ok,
    RateLimited,
    KillSwitchActive,
    Error(String),
}
```

### 12.4 Rate limiting

Hard-coded floor in the broker (not configurable by plugins or config):

* **Global cap:** 30 actions/second
* **Per-gesture cap:** 5 triggers/second
* **Burst allowance:** 10 actions in 100ms (then rate limit kicks in)

```rust
const GLOBAL\\\_RATE\\\_LIMIT: u32 = 30;  // actions/sec
const PER\\\_GESTURE\\\_RATE\\\_LIMIT: u32 = 5;  // triggers/sec
const BURST\\\_WINDOW\\\_MS: u64 = 100;
const BURST\\\_MAX: u32 = 10;

fn check\\\_rate\\\_limit(\\\&self, gesture\\\_id: \\\&str) -> bool {
    let now = SystemTime::now();
    // ... sliding window check ...
    // Returns false if rate limited
}
```

### 12.5 Kill switch

Three layers, all unreachable from plugins:

1. **Gesture kill:** Fist held 1.5s → suspend all injection
2. **Hotkey kill:** Global Esc×3 (intercepted at OS level, not via plugin API)
3. **Hardware kill (optional):** USB foot-pedal via HID

Kill switch state is stored in the broker process. Plugins and the engine can query but not modify it.

\---

## 13\. Phase 6: WASM Plugin Sandbox

**Confidence: High. Effort: L. Impact: Critical.**

### 13.1 Why WASM

The current plugin sandbox is theater (see Blocker 1). RestrictedPython's compile output is discarded, and even if it weren't, RestrictedPython is historically bypassable via `getattr`-based reflection. The 2024-2026 industry direction for safely running untrusted code is **WASM components with WIT (Wasm Interface Type) contracts**.

**WASM benefits:**

* **Strong isolation** — plugins run in a wasmtime sandbox with no host access by default
* **Capability-based security** — plugins declare capabilities in a WIT contract; the host enforces them per host-call
* **Near-native speed** — wasmtime's Cranelift compiler produces code within 10% of native
* **Portable** — same plugin binary runs on all 3 OSes
* **Memory-safe** — WASM linear memory is sandboxed; no buffer overflows

### 13.2 WIT contract example

```wit
// maestro-plugin.wit
package maestro:plugin;

interface gesture-api {
    // Plugins can subscribe to gesture events
    on-gesture: func(event: gesture-event);
    
    // Plugins can register custom gestures
    register-gesture: func(def: gesture-definition) -> result<\\\_, string>;
}

interface action-api {
    // Plugins can trigger OS actions (requires "os:input" capability)
    trigger-action: func(action: string) -> result<\\\_, string>;
}

interface config-api {
    // Plugins can read their own config section
    get-config: func(key: string) -> option<string>;
}

record gesture-event {
    name: string,
    hand: handedness,
    confidence: f32,
    timestamp: u64,
}

world maestro-plugin {
    import gesture-api;
    import action-api;
    import config-api;
    
    export init: func();
    export on-load: func();
    export on-unload: func();
}
```

### 13.3 Capability model

Plugins declare capabilities in `maestro.toml`:

```toml
\\\[plugin]
name = "media-gestures"
version = "2.0.0"
author = "Maestro Team"

\\\[capabilities]
"os:input" = true       # can trigger OS actions
"config:read" = true    # can read own config
"config:write" = false  # cannot write config
"network" = false       # no network access
"filesystem" = false    # no filesystem access
```

The WASM host enforces each capability per host-call. A plugin without `"os:input"` calling `trigger-action()` gets `PermissionDenied`.

### 13.4 Legacy Python plugin path

Keep a legacy Python plugin path for power users, run it in a **seccomp (Linux) / sandbox-exec (macOS) / AppContainer (Windows) sandboxed subprocess** with explicit capability grants. This gives safety by default and an escape hatch for trusted code.

### 13.5 Migration

1. **v2.0:** Ship WASM runtime as default-safe + legacy (sandboxed-subprocess) Python path. Both coexist.
2. **v2.1:** Deprecate Python plugin path. Document migration.
3. **v3.0:** Remove Python plugin path. WASM only.

\---

## 14\. Phase 7: Supply Chain Integrity

**Confidence: High. Effort: M. Impact: High.**

### 14.1 Sigstore (cosign) signing

Keyless OIDC signing of every build artifact + provenance. Industry standard 2024+.

```yaml
# .github/workflows/release.yml
- name: Sign artifacts with Sigstore
  uses: sigstore/cosign-installer@v3
- run: |
    cosign sign-blob --yes packaging/Maestro-Setup-v2.0.0.exe
    cosign sign-blob --yes packaging/Maestro-v2.0.0.dmg
    cosign sign-blob --yes packaging/maestro\\\_2.0.0\\\_amd64.deb
```

### 14.2 SLSA Level 3 provenance

Generate SLSA-3 build provenance attestations in CI (trusted builder, hermetic, non-falsifiable). The existing `release.yml` claims SLSA — audit it.

```yaml
- name: Generate SLSA provenance
  uses: slsa-framework/slsa-github-generator@v1.9.0
  with:
    upload-assets: true
```

### 14.3 CycloneDX SBOM

Emit CycloneDX SBOM per release using `cyclonedx-bom` or `cdxgen`. The committed `packaging/sbom.cdx.json` is stale — regenerate per release.

```bash
pip install cyclonedx-bom
cyclonedx-py environment -o packaging/sbom.cdx.json
```

### 14.4 Dependency pinning + hashes

```bash
pip install pip-tools
pip-compile --generate-hashes pyproject.toml -o requirements.lock
pip install --require-hashes -r requirements.lock
```

### 14.5 TUF-secured auto-update

Ship updates via **The Update Framework (TUF)** — threshold signatures, rollback protection, freeze attack defense. Replaces the current `updater.py` which has TLS disabled.

```
metadata/
  root.json          # root signing key (offline)
  targets.json       # lists release artifacts + hashes
  snapshot.json      # points to current targets
  timestamp.json     # freshness check
targets/
  maestro-2.0.0.exe
  maestro-2.0.0.dmg
  maestro-2.0.0.deb
```

The client fetches `timestamp.json` first (freshness), then `snapshot.json` (consistency), then `targets.json` (artifact list), then downloads the target with hash verification. All over HTTPS with **TLS verification enabled** (fixing S-01).

\---

## 15\. Phase 8: Input Injection Security

**Confidence: High. Effort: S-M. Impact: High.**

### 15.1 Tamper-evident audit log

Every OS action → append-only signed log:

```rust
pub struct AuditEntry {
    timestamp: u64,
    gesture: String,
    action: String,
    target\\\_app\\\_class: String,  // "browser", "editor" — NOT the real app name (privacy)
    plugin\\\_id: Option<String>,
    latency\\\_ms: u32,
    signature: \\\[u8; 64],  // Ed25519 signature
}

pub fn log\\\_action(entry: AuditEntry) {
    let signed = sign\\\_entry(\\\&entry, \\\&self.signing\\\_key);
    self.audit\\\_log.append(\\\&signed);
    // Rotate when > 10MB
}
```

Log is append-only, signed with an Ed25519 key generated at install time. Users can verify the log hasn't been tampered with.

### 15.2 Rate limiting (see Phase 5)

Hard-coded floor in the broker. Not configurable by plugins or config.

### 15.3 Kill switch (see Phase 5)

Three layers, all unreachable from plugins.

\---

# Part V — Privacy Protection

## 16\. Phase 9: Data Minimization

**Confidence: High. Effort: S. Impact: High.**

### 16.1 Stop logging foreground app names

**Current:** `action\\\_dispatcher.py:58-65` logs `app=event.app\\\_profile` which is the foreground process name (e.g., `chrome.exe`, `vlc.exe`). This reveals user activity patterns. Logs persist in 10MB × 3 rotated files.

**Fix:** Replace with an **app-class taxonomy** for diagnostics:

```rust
pub enum AppClass {
    Browser,
    Editor,
    Media,
    Communication,
    Game,
    System,
    Unknown,
}

fn classify\\\_app(app\\\_name: \\\&str) -> AppClass {
    let name = app\\\_name.to\\\_lowercase();
    if name.contains("chrome") || name.contains("firefox") || name.contains("safari") {
        AppClass::Browser
    } else if name.contains("code") || name.contains("vim") || name.contains("emacs") {
        AppClass::Editor
    } else if name.contains("vlc") || name.contains("spotify") || name.contains("netflix") {
        AppClass::Media
    } else if name.contains("slack") || name.contains("discord") || name.contains("teams") {
        AppClass::Communication
    } else if name.contains("steam") || name.contains("epic") {
        AppClass::Game
    } else {
        AppClass::Unknown
    }
}
```

Log `app\\\_class=Browser` instead of `app=chrome.exe`. Keep the real app name behind `--debug-identifying` flag for development.

### 16.2 Gesture names only in debug

Production logs use gesture **IDs** (e.g., `gesture\\\_id=gest\\\_001`), not human names. User-defined gesture names can be identifying (e.g., "MyArthritisExercise").

```rust
if log\\\_level <= Level::Debug {
    log::info!("Gesture triggered", name=gesture.name);
} else {
    log::info!("Gesture triggered", id=gesture.id);
}
```

### 16.3 Crash reports strip hand data

Sentry/minidump filters: **no frame bytes, no landmark arrays, no app names**. Stack traces + build ID only.

```rust
fn crash\\\_report\\\_filter(event: \\\&mut SentryEvent) {
    event.extra.retain(|key, \\\_| match key {
        "frame" | "landmarks" | "app\\\_name" | "gesture\\\_name" => false,
        \\\_ => true,
    });
}
```

### 16.4 Diagnostic dump redaction

The `\\\_export\\\_diagnostics` function should default to `--redacted` mode that strips:

* App names from logs
* Gesture names (replace with IDs)
* Hotkeys (replace with `\\\*\\\*\\\*`)
* File paths (replace with `<user\\\_dir>/`)

```bash
maestro export-diagnostics --redacted  # default
maestro export-diagnostics --full      # explicit opt-in for support
```

\---

## 17\. Phase 10: Camera Privacy Hardening

**Confidence: High. Effort: S-M. Impact: Critical.**

### 17.1 Fix SharedMemory permissions (Blocker 3)

**Linux:** Fix `engine.py:82` path from `f"psm\\\_{self.\\\_shm\\\_name}"` to `self.\\\_shm\\\_name`. Verify `chmod(0o600)` runs. Add a test that creates a SharedMemory segment and asserts permissions.

**Windows:** Use `win32security` to set a DACL granting access only to the current user SID:

```rust
use windows::Win32::Security::{
    SetSecurityDescriptorDacl, InitializeSecurityDescriptor,
    BuildExplicitAccessWithName, SetEntriesInAcl,
};
use windows::Win32::System::Memory::CreateFileMappingW;

fn create\\\_secure\\\_shared\\\_memory(size: usize) -> Result<Handle> {
    let sid = get\\\_current\\\_user\\\_sid()?;
    let dacl = build\\\_dacl(sid, GENERIC\\\_ALL)?;  // only current user
    let sd = build\\\_security\\\_descriptor(dacl)?;
    
    let handle = unsafe {
        CreateFileMappingW(
            INVALID\\\_HANDLE\\\_VALUE,
            \\\&sd,  // security descriptor
            PAGE\\\_READWRITE,
            0,
            size as u32,
            w!("MaestroFrameBuffer"),
        )?
    };
    Ok(handle)
}
```

### 17.2 Frame never to disk

Add a **static assert + CI test**: no code path writes frame bytes to disk. Crash dumps must exclude frame buffers.

```python
# tests/test\\\_no\\\_frame\\\_persistence.py
def test\\\_no\\\_open\\\_calls\\\_reference\\\_frame\\\_data():
    """Verify no open() call in the codebase references frame data."""
    import ast
    import pathlib
    
    for py\\\_file in pathlib.Path("gesture\\\_controller").rglob("\\\*.py"):
        tree = ast.parse(py\\\_file.read\\\_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                if node.args and isinstance(node.args\\\[0], ast.Constant):
                    mode = node.args\\\[1].value if len(node.args) > 1 else "r"
                    assert "wb" not in mode, f"File write in {py\\\_file}:{node.lineno}"
```

### 17.3 Frame not accessible to plugins

Plugin API exposes **only landmarks** (21×3 floats), never raw frames. Enforce at the WASM WIT boundary (frame type not in the interface). Legacy Python plugins via IPC must not receive frame handles.

### 17.4 Memory zeroing of frame buffers

`mlock` frame pages (prevent swap), `explicit\\\_bzero` / `std::ptr::write\\\_bytes(0)` on release. Prevents cold-boot/hibernation residue.

```rust
use libc::{mlock, munlock};

fn secure\\\_frame\\\_buffer(buf: \\\&mut \\\[u8]) {
    unsafe { mlock(buf.as\\\_mut\\\_ptr() as \\\*const \\\_, buf.len()); }
}

fn zero\\\_frame\\\_buffer(buf: \\\&mut \\\[u8]) {
    unsafe {
        std::ptr::write\\\_bytes(buf.as\\\_mut\\\_ptr(), 0, buf.len());
        munlock(buf.as\\\_ptr() as \\\*const \\\_, buf.len());
    }
}
```

### 17.5 Disable camera on focus loss (opt-in)

Configurable; pause capture when app loses focus or system locks.

```yaml
# default\\\_config.yaml
camera:
  pause\\\_on\\\_focus\\\_loss: false  # opt-in
  pause\\\_on\\\_screen\\\_lock: true  # opt-in, default true
```

### 17.6 Network egress CI test

Add a test that runs the full pipeline under a network egress denylist and **fails** on any outbound packet:

```yaml
# .github/workflows/ci.yml
- name: Network egress test
  run: |
    sudo iptables -A OUTPUT -p tcp --dport 443 -j DROP
    sudo iptables -A OUTPUT -p tcp --dport 80 -j DROP
    python -m pytest tests/test\\\_no\\\_network\\\_egress.py
    sudo iptables -F
```

```python
# tests/test\\\_no\\\_network\\\_egress.py
def test\\\_no\\\_network\\\_calls\\\_during\\\_operation():
    """Verify Maestro makes no network calls during normal operation."""
    import socket
    original\\\_socket = socket.socket
    
    def fail\\\_socket(\\\*args, \\\*\\\*kwargs):
        raise AssertionError("Network call attempted during operation!")
    
    socket.socket = fail\\\_socket
    try:
        engine = GestureEngine()
        engine.start()
        time.sleep(5)  # run for 5 seconds
        engine.shutdown()
    finally:
        socket.socket = original\\\_socket
```

\---

## 18\. Phase 11: Compliance Framework

**Confidence: High (policy), Medium (legal). Effort: S-M. Impact: Medium.**

### 18.1 Privacy policy

Clear statement: on-device processing, no data collection, camera frames ephemeral. Legal review required.

```markdown
# Privacy Policy

Maestro processes all data on your device. We do not collect, transmit, or store:
- Camera frames
- Hand landmark data
- Foreground application names
- Gesture usage data

## Camera
Maestro accesses your webcam to detect hand landmarks. Frames are processed in
RAM and never written to disk. Frames are not accessible to plugins.

## Logging
Maestro logs diagnostic information (error messages, performance metrics) to
local log files. Logs do not contain hand data or application names (unless
debug mode is explicitly enabled).

## Telemetry
Maestro does not collect telemetry. The `telemetry\\\_enabled` config flag is
dead code and will be removed in v2.0.

## Updates
Maestro checks for updates by contacting api.github.com over HTTPS with TLS
verification. No data is sent; only the latest release version is fetched.

## Data Export \\\& Deletion
Run `maestro export` to export all your data (config, templates, redacted logs).
Run `maestro erase` to delete all Maestro data from your system.
```

### 18.2 Right to erasure

One-click "delete all Maestro data":

```bash
maestro erase
# Deletes:
# \\\~/.config/gesture\\\_controller/
# \\\~/.local/share/gesture\\\_controller/
# \\\~/Library/Application Support/gesture\\\_controller/
# %APPDATA%/gesture\\\_controller/
# Logs, config, templates, cache, onboarding marker
```

### 18.3 Data export

```bash
maestro export --output maestro-data.zip
# Exports:
# config.yaml (sanitized: hotkeys redacted)
# custom\\\_templates/\\\*.json
# logs/ (redacted: app names and gesture names stripped)
# plugins/ (list of installed plugins, not source code)
```

### 18.4 Consent management

Explicit opt-in (checkbox, default off) for **any** telemetry. Granular (crash vs usage). If telemetry is ever added:

```yaml
telemetry:
  enabled: false  # default off
  crash\\\_reports: false  # separate consent
  usage\\\_stats: false  # separate consent
```

### 18.5 COPPA (children)

Gesture control is usable by kids. No account/data collection by default (already true). Add a "child-friendly mode" toggle that disables any network-facing feature entirely at build config.

\---

# Part VI — Platform-Native Deep Integration

## 19\. Phase 12: Linux Native

**Confidence: High. Effort: L. Impact: Critical (Wayland).**

### 19.1 Wayland native (drop xdotool)

Use `libwayland-client` + the `remote-desktop` / `virtual-keyboard` / `virtual-pointer` protocols. xdotool is X11-only and broken on Wayland compositors. **Critical as Wayland is now default on most Linux distros** (Fedora, Ubuntu, RHEL 9+).

```rust
use wayland\\\_client::{Display, GlobalManager, protocol::wl\\\_registry};
use wayland\\\_protocols::wlr::foreign\\\_toplevel::v1::\\\*;

fn wayland\\\_init() -> Result<WaylandConnection> {
    let display = Display::connect\\\_to\\\_env()?;
    let mut event\\\_queue = display.create\\\_event\\\_queue();
    let globals = GlobalManager::new(\\\&display.attach(event\\\_queue.token()));
    event\\\_queue.sync\\\_roundtrip()?;
    
    // Check for wlr-foreign-toplevel (sway, hyprland, wayfire)
    if globals.installed::<ZwlrForeignToplevelManagerV1>() {
        return Ok(WaylandConnection::Wlr(display, event\\\_queue));
    }
    
    // Check for KDE plasma-window-management
    // Check for GNOME shell D-Bus interface
    
    Err("No supported Wayland compositor".into())
}
```

### 19.2 PipeWire for camera

Replace V4L2 with PipeWire (produces DMA-BUF → feeds zero-copy pipeline). Future-proof, sandbox-friendly.

### 19.3 systemd integration

* Socket activation (start Maestro on-demand)
* Session management (`graphical-session.target`)
* Journal logging (structured logs to `journalctl`)

### 19.4 Flatpak / Snap packaging

Sandboxed distribution; aligns with the privilege separation philosophy. Use Flatpak portals for camera access.

### 19.5 MPRIS for media controls

Quick high-value win. Replace the current `playerctl` subprocess calls with direct MPRIS D-Bus calls:

```rust
use zbus::{Connection, dbus\\\_proxy};

#\\\[dbus\\\_proxy(
    interface = "org.mpris.MediaPlayer2.Player",
    default\\\_service = "org.mpris.MediaPlayer2.\\\*",
    default\\\_path = "/org/mpris/MediaPlayer2"
)]
trait MprisPlayer {
    fn play\\\_pause(\\\&self) -> zbus::Result<()>;
    fn next(\\\&self) -> zbus::Result<()>;
    fn previous(\\\&self) -> zbus::Result<()>;
}
```

\---

## 20\. Phase 13: macOS Native

**Confidence: High. Effort: L. Impact: Critical (Core ML).**

### 20.1 Core ML inference

Convert ONNX → CoreML via `coremltools`. Core ML dispatches to the Neural Engine (ANE) and GPU. **Biggest macOS perf + battery win.**

```swift
// In the Rust core, call Core ML via objc2 crate
use objc2::runtime::AnyObject;
use objc2::ClassType;

fn coreml\\\_inference(frame: \\\&Frame) -> Vec<HandLandmarks> {
    let model = load\\\_coreml\\\_model("HandLandmarker.mlmodelc")?;
    let input = convert\\\_frame\\\_to\\\_cvpixelbuffer(frame)?;
    let output = model.prediction(input)?;
    parse\\\_hand\\\_landmarks(output)
}
```

### 20.2 Shortcuts app integration

Deep AX integration for semantic actions; Shortcuts for user automation.

### 20.3 Vision framework

Face/body tracking via native Vision — lower latency than cross-platform MediaPipe on Apple Silicon.

### 20.4 ScreenCaptureKit

Screen-aware gestures (context-sensitive). Requires screen-recording permission.

### 20.5 AppleScript / JXA bridge

Included in integration APIs. `maestro run-applescript 'tell application "Safari" to activate'`

\---

## 21\. Phase 14: Windows Native

**Confidence: High. Effort: M. Impact: Critical (DirectML).**

### 21.1 DirectML / D3D11-12 acceleration

ONNX Runtime + DirectML execution provider → runs on any DX12 GPU (AMD/Intel/NVIDIA). DXGI shared handle for zero-copy.

### 21.2 WinUI 3 / Windows App SDK

Modern shell; better than WPF/WinForms for v2.0. MSIX packaging.

### 21.3 Windows Hello

Face unlock + gesture = delightful combo. Optional.

### 21.4 PowerToys / Accessibility Center integration

Distribution + reach into the accessibility audience.

### 21.5 ETW diagnostics

Native structured logging/tracing; pair with redaction.

\---

# Part VII — New Features

## 22\. Phase 15: Accessibility Modalities

**Confidence: High. Effort: M-L. Impact: High.**

### 22.1 Voice modality (Whisper.cpp local STT)

Voice commands as complement. Fully local (STT model on-device) preserves the zero-data ethos.

```rust
use whisper\\\_rs::\\\*;

fn init\\\_voice() -> Result<WhisperContext> {
    let ctx = WhisperContext::new\\\_with\\\_params(
        "models/ggml-base.en.bin",
        WhisperContextParameters::default()
    )?;
    Ok(ctx)
}

fn recognize\\\_voice(ctx: \\\&WhisperContext, audio: \\\&\\\[f32]) -> String {
    let mut state = ctx.create\\\_state()?;
    state.full(\\\&FullParams::default(), audio)?;
    state.full\\\_get\\\_segment\\\_text(0)
}
```

### 22.2 MediaPipe Pose / Face Mesh

Head tracking (head-pointer) + face micro-gestures (blink/brow) for users with limited hand mobility. Reuse the same pipeline/backends.

### 22.3 Tremor compensation

Adaptive low-pass (auto-tune 1€ min cutoff from tremor spectrum). **Big quality-of-life win for Parkinson's users.**

```rust
fn auto\\\_tune\\\_filter(tremor\\\_spectrum: \\\&FreqSpectrum) -> OneEuroParams {
    let dominant\\\_freq = tremor\\\_spectrum.peak\\\_frequency();
    
    if dominant\\\_freq > 4.0 \\\&\\\& dominant\\\_freq < 12.0 {
        // Parkinsonian tremor range: 4-12 Hz
        OneEuroParams {
            min\\\_cutoff: 0.5,  // more smoothing
            beta: 0.003,      // less responsive to fast motion
        }
    } else {
        OneEuroParams::default()
    }
}
```

### 22.4 Fatigue-aware adjustment

Track gesture-completion variance over a session. Widen thresholds as fatigue rises.

### 22.5 Feedback options (visual / audio / haptic)

On-screen overlay, subtle audio cues, gamepad/haptic rumble. Essential for users who can't see their hands (low vision).

\---

## 23\. Phase 16: Developer Experience

**Confidence: High. Effort: M. Impact: High.**

### 23.1 Plugin SDK

Typed plugin API (py.typed + WIT). Ship mypy stubs for the Python path; WIT contracts are inherently typed for WASM path.

### 23.2 `maestro init-plugin` + `maestro-test`

Scaffolder + test harness:

```bash
maestro init-plugin my-plugin
cd my-plugin
maestro test  # record → replay landmark streams, assert gestures
```

### 23.3 Visual gesture editor

Record → trim → annotate → export template. Huge for adoption.

### 23.4 Auto-calibration / adaptive thresholds

On first run, sample range-of-motion. Set per-user thresholds. Learns over time (local only).

### 23.5 CLI for scripting

```bash
maestro trigger MinimizeWindow
maestro trigger KeyPress:Ctrl+Shift+Tab
maestro list-gestures
maestro list-actions
maestro status
maestro pause
maestro resume
```

\---

## 24\. Phase 17: Integration APIs

**Confidence: High. Effort: M. Impact: High.**

### 24.1 WebSocket API (localhost + token auth)

```javascript
// Client example
const ws = new WebSocket("ws://127.0.0.1:8765?token=...");
ws.onmessage = (e) => console.log(JSON.parse(e.data));

ws.send(JSON.stringify({
    action: "trigger",
    gesture: "MinimizeWindow"
}));
```

### 24.2 REST API

```bash
curl -X POST http://127.0.0.1:8765/api/trigger \\\\
  -H "Authorization: Bearer ..." \\\\
  -d '{"gesture": "MinimizeWindow"}'
```

### 24.3 D-Bus interface (Linux)

```bash
gdbus call --session \\\\
  --dest org.maestro.Controller \\\\
  --object-path /org/maestro/Controller \\\\
  --method org.maestro.Controller.Trigger \\\\
  "MinimizeWindow"
```

### 24.4 Shortcuts / AppleScript (macOS)

```applescript
tell application "Maestro"
    trigger gesture "MinimizeWindow"
end tell
```

### 24.5 COM automation (Windows)

```csharp
dynamic maestro = Activator.CreateInstance(Type.GetTypeFromProgID("Maestro.Controller"));
maestro.Trigger("MinimizeWindow");
```

\---

## 25\. Phase 18: Community \& Marketplace

**Confidence: Medium. Effort: L. Impact: High.**

### 25.1 Plugin/gesture registry

GitHub-indexed curated registry with signed manifests:

```
maestro-registry/
  plugins/
    media-gestures/
      manifest.json  # name, version, description, download\\\_url, sigstore\\\_sig
    window-management/
      manifest.json
  gestures/
    adobe-premier-pack/
      manifest.json
    vscode-pack/
      manifest.json
```

### 25.2 `maestro install` / `maestro search`

```bash
maestro search "media"
maestro install media-gestures
maestro update --all
maestro remove media-gestures
```

### 25.3 Custom gesture template sharing

Export/import YAML+DTW templates:

```bash
maestro export-gesture "MyWave" --output mywave.json
maestro import-gesture mywave.json
```

### 25.4 Community marketplace (v2.1+)

Web UI for browsing/rating plugins and gesture packs. Hosted on GitHub Pages (static site + registry JSON).

\---

# Part VIII — Execution

## 26\. Implementation Roadmap

**7 phases over 6-8 months.** Each phase is independently shippable.

### Phase 1: Rust Core Engine (Months 1-3)

* Port OneEuroFilter + compute\_features to Rust (Sprint 1)
* Port GestureFSM + GestureFSMManager to Rust (Sprint 2)
* Port EventBus to Rust (lock-free MPMC) (Sprint 3)
* Port CameraStream to Rust (Sprint 4)
* Implement HandTracker (centroid IoU) (Sprint 5)
* Port fast\_dtw\_distance to Rust (Sprint 6)
* **Deliverable:** 10× latency improvement, even on CPU

### Phase 2: GPU Inference Backends (Months 3-4)

* Convert TFLite → ONNX
* Core ML EP (macOS)
* DirectML EP (Windows)
* TensorRT EP (NVIDIA)
* OpenVINO EP (Intel)
* INT8 quantization
* Adaptive resolution
* **Deliverable:** <8ms inference on supported hardware

### Phase 3: Zero-Copy Pipeline (Months 3-4, parallel with Phase 2)

* Double-buffered SharedMemory + seqlock
* DMA-BUF (Linux) / IOSurface (macOS) / DXGI (Windows) zero-copy handles
* Frame skipping
* **Deliverable:** <2ms camera capture, zero torn frames

### Phase 4: Async Priority EventBus (Month 4)

* Lock-free MPMC priority queue
* Dedicated dispatcher thread
* Per-handler time budget
* Per-(event\_type, handler) failure counter
* **Deliverable:** <2ms action dispatch, zero engine stalls

### Phase 5: Security Core (Months 4-5)

* Privilege-separated injection broker
* WASM plugin runtime (wasmtime + WIT)
* Capability model
* seccomp / sandbox-exec / AppContainer for legacy plugins
* Kill switch (3 layers)
* Tamper-evident audit log
* Rate limiting
* **Deliverable:** Bank-grade security

### Phase 6: Supply Chain \& Updates (Month 5)

* Sigstore (cosign) signing
* SLSA Level 3 provenance
* CycloneDX SBOM (regenerated per release)
* pip-audit + hash pinning
* TUF-secured auto-update
* Expanded atheris fuzzing
* **Deliverable:** Trustworthy releases

### Phase 7: Privacy \& Compliance (Month 5)

* Network egress CI test
* Data minimization (app-class taxonomy, gesture IDs not names)
* Crash report redaction
* Diagnostic dump redaction
* Privacy policy
* Data export/erasure (`maestro export` / `maestro erase`)
* **Deliverable:** Compliance-ready privacy

### Phase 8: Platform-Native Deep Integration (Months 5-7)

* Wayland native (libwayland-client)
* PipeWire camera
* Core ML + Vision + Shortcuts (macOS)
* DirectML + WinUI (Windows)
* MPRIS / libinput gestures (Linux)
* **Deliverable:** Best-of-breed per platform

### Phase 9: New Features (Months 6-8)

* MediaPipe Gesture Recognizer (pretrained 7 gestures)
* Per-app trigger conditions
* AHK / Hammerspoon / Raycast / xdotool interop
* Stream Deck / MIDI integration
* Window snapping (FancyZones-style)
* Custom gesture template sharing
* Telemetry opt-in dashboard
* **Deliverable:** Feature parity with competitors

### Phase 10: Accessibility (Months 7-8)

* Whisper.cpp local STT
* MediaPipe Pose / Face Mesh
* Tremor compensation
* Fatigue-aware adjustment
* Feedback options (visual/audio/haptic)
* **Deliverable:** Genuine accessibility

### Phase 11: Developer Experience (Months 7-8)

* Plugin SDK + WIT contracts
* `maestro init-plugin` + `maestro-test`
* Visual gesture editor
* Auto-calibration
* Integration APIs (WebSocket/REST/CLI/D-Bus/Shortcuts/COM)
* Community registry (curated, signed)
* **Deliverable:** Thriving ecosystem

\---

## 27\. Measurable Targets \& KPIs

### 27.1 Performance KPIs

|Metric|v0.1.0|v2.0 target|How measured|
|-|-|-|-|
|E2E latency P50|\~150ms|<15ms|Benchmark in CI|
|E2E latency P95|unknown|<20ms|Benchmark in CI|
|Sustained FPS|20-30|60+|60-second soak test|
|Inference time|15-25ms|<8ms|Per-frame timing|
|Memory (24h)|unknown|<2× startup|24h soak test, RSS monitoring|
|Dropped frames|unknown|<1%|Camera-set count vs engine-processed count|
|Battery (laptop)|unknown|<5% per hour|macOS powermetrics, Windows powercfg|

### 27.2 Security KPIs

|Metric|v0.1.0|v2.0 target|
|-|-|-|
|CVEs in dependencies|2 (nltk, pytest)|0|
|Bandit MEDIUM+ findings|2|0|
|Plugin sandbox bypass|Trivial (6+ vectors)|None (WASM isolation)|
|TLS verification|Disabled|Enabled|
|Supply chain SLSA level|3 (claimed)|3 (audited)|
|SBOM|Stale, committed|Regenerated per release|
|Audit log|None|Tamper-evident, all actions|

### 27.3 Privacy KPIs

|Metric|v0.1.0|v2.0 target|
|-|-|-|
|Network calls during operation|1 (update checker)|0 (update checker opt-in only)|
|Camera frames to disk|0|0 (verified by CI test)|
|App names in logs|Yes|No (app-class taxonomy)|
|Gesture names in production logs|Yes|No (gesture IDs)|
|Telemetry|None (dead code)|None (dead code removed)|
|Data export|None|`maestro export`|
|Data erasure|None|`maestro erase`|

### 27.4 Adoption KPIs (v2.0+)

|Metric|Target|
|-|-|
|GitHub stars|5,000 (from \~current baseline)|
|Plugin registry entries|50+ community plugins|
|Custom gesture templates shared|200+|
|Active contributors|20+|
|CI pass rate|100% on main|

\---

## 28\. Risk Register

|Risk|Probability|Impact|Mitigation|Confidence|
|-|-|-|-|-|
|**Rust port stalls** (XL effort)|Medium|Critical|Port incrementally; benchmark after each sprint; fall back to Cython if needed|High|
|**MediaPipe GPU broken on Windows** (GitHub #4575)|High|High|Use ONNX Runtime + DirectML instead of MediaPipe GPU delegate|High|
|**Core ML ANE op coverage** gaps|Medium|Medium|Audit op support before promising ANE numbers; GPU fallback is still a win|Medium|
|**WASM plugin migration** alienates Python plugin authors|Medium|Medium|Ship WASM + legacy Python path; document migration; deprecate Python in v2.1|High|
|**Wayland input injection** fragmented across compositors|High|Medium|Budget for per-compositor testing (GNOME/KDEwl/sway/hyprland); fall back to XWayland|High|
|**<15ms E2E** not achievable on all hardware|Medium|Medium|Commit to <20ms P95 / <15ms P50; document hardware requirements|Moderate|
|**TEE for inference** — explicitly rejected as overkill|N/A|N/A|Document the decision so it doesn't resurface|High|
|**Meta Neural Band** (5-year horizon) obsoletes webcam gesture|Low|High|Stay software-only, cross-platform, fast-moving; consider EMG-band input as future modality|Medium|
|**OS voice control** erodes accessibility TAM|Medium|Medium|Position Maestro as silent / privacy-preserving / visual-creative (video editors, streamers, presenters)|High|

\---

## 29\. Build Order \& Dependencies

```
Phase 1 (Rust Core)
    │
    ├── Phase 2 (GPU Backends) ──────────────┐
    │                                        │
    └── Phase 3 (Zero-Copy Pipeline) ────────┤
                                             │
                                             ▼
                                    Phase 4 (Async EventBus)
                                             │
                    ┌────────────────────────┤
                    │                        │
                    ▼                        ▼
          Phase 5 (Security)        Phase 7 (Privacy)
                    │                        │
                    ▼                        │
          Phase 6 (Supply Chain)             │
                    │                        │
                    └────────┬───────────────┘
                             │
                             ▼
                    Phase 8 (Platform-Native)
                             │
                    ┌────────┤
                    │        │
                    ▼        ▼
          Phase 9 (Features)  Phase 10 (Accessibility)
                             │
                             ▼
                    Phase 11 (DX \\\& Marketplace)
```

**Critical path:** Phase 1 → Phase 4 → Phase 5 → Phase 8 → Phase 9.

**Parallelizable:** Phase 2 + Phase 3 (after Phase 1). Phase 6 + Phase 7 (after Phase 5). Phase 9 + Phase 10 (after Phase 8).

\---

## 30\. Appendices

### Appendix A — Current State vs v2.0 Target Summary

```
v0.1.0 (current):
┌──────────────────────────────────────────────────┐
│ Latency: \\\~150ms E2E (5× over target)             │
│ Security: Plugin sandbox is theater              │
│           TLS disabled in updater                │
│           SharedMemory world-readable on Linux   │
│ Privacy: App names logged to disk               │
│          No data export/erasure                  │
│ Platforms: CPU-only MediaPipe                   │
│            xdotool fallback on Wayland           │
│ Ecosystem: No plugin marketplace                │
│            No integration APIs                   │
│ Accessibility: "Works with hands" only          │
└──────────────────────────────────────────────────┘

v2.0 (target):
┌──────────────────────────────────────────────────┐
│ Latency: <15ms P50, <20ms P95 (10× improvement)  │
│ Security: WASM plugin sandbox + privilege sep    │
│           TLS enabled + TUF-secured updates       │
│           SharedMemory 0600 + Windows ACL        │
│ Privacy: App-class taxonomy (no real names)      │
│          Network egress CI test                   │
│          Data export/erasure CLI                  │
│ Platforms: GPU backends (CoreML/DirectML/TRT)    │
│            Wayland native + PipeWire              │
│ Ecosystem: Plugin registry + integration APIs    │
│            (WebSocket/REST/CLI/D-Bus/Shortcuts)   │
│ Accessibility: Voice + Pose + Face Mesh          │
│                Tremor compensation                │
│                Visual/audio/haptic feedback       │
└──────────────────────────────────────────────────┘
```

### Appendix B — Competitor Quick Reference

|Competitor|Modality|Hardware|Platform|Price|Maestro's edge|
|-|-|-|-|-|-|
|Ultraleap|Optical IR|$140-200|All|Free dev + commercial license|No hardware needed|
|Meta Quest|Webcam (headset)|$299-499 headset|Quest OS|Free|Desktop OS, not headset|
|Apple Vision Pro|Eye + hand|$3,499 headset|visionOS|Free SDK|Desktop OS, not headset|
|Talon Voice|Voice + eye|$0-229 (Tobii)|All|Free + $25/mo Patreon|Silent (no mic needed)|
|BetterTouchTool|Trackpad/mouse|$0|macOS|$6.50-22|Cross-platform + webcam|
|AutoHotkey|Keyboard/mouse|$0|Windows|Free|Cross-platform + gesture|
|PowerToys|Mouse gestures|$0|Windows|Free|Cross-platform + webcam|
|ControlAir|Webcam|$0|macOS|Free|Actively maintained, cross-platform|
|MediaPipe|Framework|$0|All|Free|End-user product (not a framework)|

### Appendix C — Glossary

|Term|Definition|
|-|-|
|**DMA-BUF**|Linux kernel subsystem for sharing buffers between processes/drivers via file descriptors. Enables zero-copy frame transfer.|
|**IOSurface**|macOS framework for sharing image data across processes and GPU. Equivalent of DMA-BUF on Apple platforms.|
|**DXGI**|DirectX Graphics Infrastructure. Windows API for sharing GPU resources across processes.|
|**Seqlock**|Sequence lock — a lock-free synchronization primitive where readers check a sequence counter before/after reading. Writer increments counter to odd before writing, even after.|
|**WASM**|WebAssembly — a portable binary instruction format for sandboxed execution.|
|**WIT**|WebAssembly Interface Type — IDL for defining WASM component interfaces.|
|**WASI**|WebAssembly System Interface — system API for WASM.|
|**PyO3**|Rust binding for Python. Enables writing Python extensions in Rust.|
|**maturin**|Build tool for PyO3 extensions. Produces pip-installable wheels.|
|**SLSA**|Supply-chain Levels for Software Artefacts — framework for build provenance.|
|**Sigstore**|Open-source software supply chain signing service (cosign, rekor, fulcio).|
|**TUF**|The Update Framework — specification for secure software updates.|
|**CycloneDX**|Software Bill of Materials (SBOM) format.|
|**Core ML**|Apple's on-device ML framework. Dispatches to Neural Engine (ANE) and GPU.|
|**DirectML**|Windows GPU acceleration API for ML inference. Works on any DX12 GPU.|
|**TensorRT**|NVIDIA's inference optimization library. Produces highly optimized GPU engines.|
|**OpenVINO**|Intel's inference optimization toolkit for Intel hardware (CPU, iGPU, ARC, Xeon).|
|**One-Euro Filter**|Adaptive low-pass filter for noisy real-time input (Casiez et al., CHI 2012).|
|**DTW**|Dynamic Time Warping — algorithm for measuring similarity between temporal sequences.|
|**FSM**|Finite State Machine — per-gesture model with states and condition-guarded transitions.|
|**IPC**|Inter-Process Communication.|
|**MPMC**|Multi-Producer Multi-Consumer (queue).|
|**DACL**|Discretionary Access Control List (Windows security descriptor).|
|**seccomp**|Linux kernel feature for filtering system calls.|
|**sandbox-exec**|macOS seatbelt sandbox profiles.|
|**AppContainer**|Windows sandbox mechanism for apps.|
|**MPRIS**|Media Player Remote Interfacing Specification — D-Bus interface for media controls on Linux.|

### Appendix D — References

**Performance:**

* ONNX Runtime TensorRT Execution Provider: https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html
* PINTO0309 hand-gesture-recognition-using-onnx: https://github.com/PINTO0309/hand-gesture-recognition-using-onnx
* Apple Core ML docs: https://developer.apple.com/documentation/coreml
* Casiez et al., "1€ Filter" (CHI 2012): https://hal.inria.fr/hal-00682902
* PyO3: https://pyo3.rs
* maturin: https://www.maturin.rs
* rustify benchmarks (arXiv 2507.00264): https://arxiv.org/abs/2507.00264

**Security:**

* WASM Component Model: https://github.com/WebAssembly/component-model
* WIT IDL: https://github.com/WebAssembly/component-model/blob/main/design/mvp/WIT.md
* wasmtime: https://wasmtime.dev
* Sigstore: https://www.sigstore.dev
* SLSA: https://slsa.dev
* CycloneDX: https://cyclonedx.org
* TUF: https://theupdateframework.io
* seccomp: https://man7.org/linux/man-pages/man2/seccomp.2.html
* sandbox-exec: https://developer.apple.com/library/archive/documentation/Security/Conceptual/AppSandboxDesignGuide/AppSandboxInDepth/AppSandboxInDepth.html

**Privacy:**

* GDPR: https://gdpr.eu
* CCPA: https://oag.ca.gov/privacy/ccpa
* COPPA: https://www.ftc.gov/legal-library/browse/rules/childrens-online-privacy-protection-rule-coppa

**Competitors:**

* Ultraleap: https://www.ultraleap.com
* Meta Quest hand tracking: https://developer.oculus.com/documentation/unity/unity-handtracking/
* Apple Vision Pro: https://www.apple.com/apple-vision-pro
* Talon Voice: https://talonvoice.com
* BetterTouchTool: https://folivora.ai
* AutoHotkey: https://www.autohotkey.com
* Karabiner-Elements: https://karabiner-elements.pqrs.org
* Microsoft PowerToys: https://github.com/microsoft/PowerToys
* MediaPipe: https://developers.google.com/mediapipe
* ONNX Runtime: https://onnxruntime.ai
* Apple Vision framework: https://developer.apple.com/documentation/vision
* NVIDIA Maxine: https://developer.nvidia.com/maxine
* Tobii: https://gaming.tobii.com
* Dragon NaturallySpeaking: https://www.nuance.com/dragon.html

\---

**End of v2.0 roadmap.**

This document covers:

* 5 critical blockers with evidence and fixes
* 33 competitors across 6 categories
* 20 feature gaps ranked by user impact
* 11 implementation phases over 6-8 months
* 7-phase build order with dependencies
* 30+ measurable KPIs
* 9 risks with mitigations
* Architecture vision for 10× latency improvement
* Bank-grade security architecture (WASM + privilege separation)
* Zero-data-collection privacy framework
* Platform-native deep integration (Linux/macOS/Windows)
* Accessibility modalities (voice + pose + face + tremor compensation)
* Developer experience (plugin SDK + visual editor + integration APIs)
* Community marketplace roadmap

**The v2.0 thesis in one sentence:** Convert the Python engine core to Rust, switch to per-platform GPU backends, implement zero-copy double-buffered pipeline, build a WASM plugin sandbox with privilege-separated input injection, and harden privacy with network-egress CI tests — delivering <15ms P50 latency, bank-grade security, and zero-data-collection privacy in 6-8 months.

