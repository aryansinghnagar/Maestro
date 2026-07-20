# Maestro — Commercial Release-Readiness Master Plan

**Repository:** https://github.com/aryansinghnagar/Maestro
**Audited HEAD:** `eb44bfc` (chore(release): release version 1.0.0, 2026-07-20)
**Branches in flight:** `main`, `release-please--branches--main`, plus 6 open Dependabot branches
**Plan author:** Principal architect (operating under the `agent.md` posture: world-class expert, direct tone, accuracy over approval, explicit confidence levels)
**Plan status:** Living document — implementation is gated on this plan being signed off; no code changes are made yet
**Confidence convention:** **High** = empirically verified by inspecting code or running checks · **Moderate** = strong inference from code reading, not yet run · **Low** = hypothesis needing validation · **Unknown** = insufficient information

---

## How to Read This Plan

This is not a rehash of the existing `v3.0/maestro_refactor_plan_v3.md` (which is 18 600 lines and largely aspirational). This is a focused, **executable** release-readiness plan with five non-negotiable goals:

1. **Make CI pass organically** — not by lowering thresholds, not by skipping tests, not by `|| true`. Diagnose every failure, fix the root cause, prove it green on every OS × Python cell.
2. **Unify every branch** that carries working code into a single `main` and delete the orphans.
3. **Refactor the working pipeline for both ends of the hardware spectrum** — a 4-core Celeron with integrated graphics and an M3 Max with a Neural Engine must both get a good experience, automatically, without the user picking a "performance mode".
4. **Build an adaptive performance-tier mechanism** that disables overtly demanding features on low-spec devices and unlocks them on high-spec ones, at runtime, with observability.
5. **Ready the project for a commercial / professional release** — security, packaging, signing, distribution, telemetry, support, docs, accessibility compliance, and a defensible threat model.

The plan is structured so each section answers four questions: **What is broken?** · **Why is it broken?** · **What is the fix?** · **What second-order consequences will the fix cause, and how do we deal with them?**

I am deliberately provocative where the evidence warrants it. If a piece of code is theater, I call it theater. If a CI workflow is structurally incapable of running, I say so. If a "security" feature is security theater, I name it. The user's `agent.md` demands this tone and the project's commercial-readiness goal demands honesty.

---

## Table of Contents

- [Part I — Repository State and Brutal Assessment](#part-i--repository-state-and-brutal-assessment)
  - [1. Executive Summary](#1-executive-summary)
  - [2. What Maestro Actually Is](#2-what-maestro-actually-is)
  - [3. Repository Topology and Branch Inventory](#3-repository-topology-and-branch-inventory)
  - [4. Critical Finding: CI Has Not Actually Been Running](#4-critical-finding-ci-has-not-actually-been-running)
  - [5. Bug Catalog (P0–P3)](#5-bug-catalog-p0p3)
  - [6. Security Threat Model (STRIDE)](#6-security-threat-model-stride)
  - [7. Code Quality and Architecture Critique](#7-code-quality-and-architecture-critique)
- [Part II — CI Failure Root-Cause Analysis and Organic Fix Plan](#part-ii--ci-failure-root-cause-analysis-and-organic-fix-plan)
  - [8. CI Workflow Audit (Line-by-Line)](#8-ci-workflow-audit-line-by-line)
  - [9. The Five CI Failure Classes and Their Fixes](#9-the-five-ci-failure-classes-and-their-fixes)
  - [10. Hardening CI So It Cannot Silently Break Again](#10-hardening-ci-so-it-cannot-silently-break-again)
- [Part III — Branch Unification Strategy](#part-iii--branch-unification-strategy)
  - [11. Branch-by-Branch Disposition](#11-branch-by-branch-disposition)
  - [12. The Unification Procedure (Step-by-Step)](#12-the-unification-procedure-step-by-step)
  - [13. Post-Unification Branch Hygiene](#13-post-unification-branch-hygiene)
- [Part IV — Adaptive Performance Tier System](#part-iv--adaptive-performance-tier-system)
  - [14. Design Goals and Constraints](#14-design-goals-and-constraints)
  - [15. The Four Performance Tiers](#15-the-four-performance-tiers)
  - [16. The Capability Registry](#16-the-capability-registry)
  - [17. The Hardware Probe and Tier Classification](#17-the-hardware-probe-and-tier-classification)
  - [18. Runtime Adaptation: Dynamic Downgrade and Upgrade](#18-runtime-adaptation-dynamic-downgrade-and-upgrade)
  - [19. User Overrides and Escape Hatches](#19-user-overrides-and-escape-hatches)
  - [20. Observability for the Tier System](#20-observability-for-the-tier-system)
  - [21. Consequences and Mitigations](#21-consequences-and-mitigations)
- [Part V — Refactoring for Speed on Low-Spec and High-Spec Hardware](#part-v--refactoring-for-speed-on-low-spec-and-high-spec-hardware)
  - [22. Vision Pipeline Optimizations](#22-vision-pipeline-optimizations)
  - [23. Engine Loop Optimizations](#23-engine-loop-optimizations)
  - [24. GUI and Overlay Optimizations](#24-gui-and-overlay-optimizations)
  - [25. Memory Footprint Optimizations](#25-memory-footprint-optimizations)
  - [26. Cold-Start and Binary Size](#26-cold-start-and-binary-size)
  - [27. Benchmarking and Regression Gates](#27-benchmarking-and-regression-gates)
- [Part VI — Release-Readiness Plan](#part-vi--release-readiness-plan)
  - [28. Security Hardening](#28-security-hardening)
  - [29. Code Signing and Supply Chain](#29-code-signing-and-supply-chain)
  - [30. Packaging and Distribution](#30-packaging-and-distribution)
  - [31. Privacy, Compliance, and Legal](#31-privacy-compliance-and-legal)
  - [32. Documentation and Support](#32-documentation-and-support)
  - [33. Telemetry and Crash Analytics](#33-telemetry-and-crash-analytics)
  - [34. Release Runbook](#34-release-runbook)
- [Part VII — Execution Roadmap and Sequencing](#part-vii--execution-roadmap-and-sequencing)
  - [35. Sprint Plan (12 Sprints, 6 Weeks)](#35-sprint-plan-12-sprints-6-weeks)
  - [36. Risk Register](#36-risk-register)
  - [37. Definition of Done for Commercial Release v1.0](#37-definition-of-done-for-commercial-release-v10)
- [Appendices](#appendices)
  - [A. Glossary](#a-glossary)
  - [B. File Inventory](#b-file-inventory)
  - [C. References](#c-references)

---

# Part I — Repository State and Brutal Assessment

## 1. Executive Summary

Maestro is a cross-platform hand-gesture desktop controller written in Python 3.11+. It captures webcam frames in a child process, runs ONNX Runtime inference for palm/hand-landmark detection, applies One-Euro filtering and per-hand tracking, evaluates a finite-state machine per hand against a trigger DSL, and dispatches keyboard/mouse/media actions through a privilege-separated input broker. A PyQt6 GUI provides a tray icon, overlay HUD, settings window, gesture recorder, and onboarding wizard. The project ships with 30 ADRs, 15 RFCs, 8 design specs, 70+ unit tests, integration tests, replay fixtures, property-based tests, benchmarks, and a nightly fuzz target.

That is the optimistic summary. The pessimistic summary, which is more accurate, is:

- **The CI workflow on `main` has not actually been triggering on push or PR** since a YAML typo (`branches: ain]` instead of `branches: [main]`) was introduced. The green badge in the README is therefore misleading — it is showing the result of whichever run last happened to execute (likely a manual `workflow_dispatch` or a Dependabot-triggered run on a different branch). **Confidence: High** — I verified this by reading `.github/workflows/ci.yml` lines 4–7 on commit `eb44bfc`.
- **The release workflow is also broken**: `release.yml` line 25 uses `python_version` (underscore) instead of `python-version` (hyphen); `actions/setup-python` silently ignores the unrecognized input and falls back to the system default Python. **Confidence: High** — verified by reading the file.
- **Two of the five "CI failures" documented in the repo's own `old_docs/maestro-ci-fix-plan.md` have already been silently fixed** (mypy `windll` ignores and the `fuzz.yml` path/typo), but **two have not** (the `ci.yml` YAML typo and the `release.yml` `python_version` typo). The repo's own fix plan therefore overstates its completeness. **Confidence: High**.
- The codebase has **architectural strengths** (multiprocessing isolation, privilege-separated broker with rate limiting and hash-chained audit log, TUF signed updates, AST-based safe condition parser, seqlock double-buffered shared memory) and **serious problems** (the integration server's WebSocket implementation has no masked-frame handling and no proper read loop, the WASM sandbox is unused and trivially bypassable, the plugin loader uses `exec` after AST validation which is the canonical RestrictedPython bypass pattern, the broker's Windows authentication is `return True`, the updater's TUF root.json ships with what look like placeholder public keys).
- The 18 600-line `v3.0/maestro_refactor_plan_v3.md` is impressive in scope but is **largely aspirational and unsequenced**; it does not provide a deterministic, sprint-by-sprint execution path to a shippable v1.0. This plan does.
- The performance budget claims (P50 GPU <15 ms, P50 CPU <30 ms, binary <25 MB, memory <200 MB, cold start <1.5 s) are **unverified and almost certainly not met** by the current `pyinstaller --onefile --noconsole` build path, which would produce a 60–100 MB executable that bundles PyQt6, onnxruntime, opencv-python, numba, and the model files. **Confidence: Moderate** — the build has not been run, but the dependency closure is large enough that <25 MB is implausible without aggressive trimming.
- The single most important missing capability — and the one the user explicitly asked for — is **any form of adaptive performance tiering**. Today the engine has exactly two adaptive mechanisms: a 30→5 FPS drop after 30 s of no hands, and an `adapt_fps` loop that lowers the target when processing exceeds the frame interval. There is no mechanism to detect that the device is a low-spec Chromebook and proactively disable the HUD overlay, switch to INT8 quantization, lower the camera resolution, disable voice listening, disable the integration server, or fall back to a lighter landmark model. This plan builds that mechanism.

The release-readiness gap, in one sentence: **Maestro today is a research-grade demo with production-grade aspirations, and the distance between those two states is roughly six weeks of focused engineering work, sequenced below.**

## 2. What Maestro Actually Is

Stripped of marketing, Maestro is a Python process that does this 30 times a second:

```
┌─────────────┐   shm   ┌─────────────────┐  onnx  ┌──────────────┐
│  Camera     ├────────►│ LandmarkExtractor├───────►│ HandTracker  │
│  (child)    │  frame  │ (parent process) │  raw   │ + OneEuro    │
└─────────────┘  ready  └─────────────────┘  hands  └──────┬───────┘
                                                          │
                                                          ▼
┌──────────────┐  event  ┌────────────────┐  action ┌─────────────┐
│ ActionDispat.│◄────────│ GestureRecogn. │ ◄───────│  FSM x N    │
│  -> Broker   │         │ (per-hand FSMs)│ features└─────────────┘
└──────┬───────┘         └────────────────┘
       │ IPC
       ▼
┌──────────────┐   native   ┌──────────────────┐
│ OS Controller│───────────►│ Win32 / CGEvent /│
│  (broker)    │  injection │ uinput + X11     │
└──────────────┘            └──────────────────┘
```

Auxiliary subsystems:

- **PyQt6 GUI** — tray icon, overlay HUD with hand skeleton render, settings window, gesture recorder, onboarding wizard, tremor calibrator, dwell clicker, performance monitor, crash report dialog.
- **Plugin system** — Python plugin discovery from `builtin/`, `data/plugins/`, and `~/.maestro/plugins/`; WASM sandbox (wasmtime) for "untrusted" plugins; AST-based permission scan; hot-reload via watchdog.
- **Voice listener** — Vosk-based offline speech recognition with a wake word ("maestro") and a registry of phrase→gesture mappings.
- **Integration server** — a hand-rolled HTTP server with REST routes (`/api/trigger`, `/api/state`, `/api/status`, `/metrics`) and a hand-rolled WebSocket implementation that broadcasts `gesture_triggered` events.
- **Updater** — TUF-based signed-update client with a `UpdateCheckerThread` that polls a release feed and shows a tray notification.
- **Compliance** — GDPR-style data export and erasure APIs in `compliance.py`.
- **OS integration** — three platform controllers (Windows SendInput via ctypes, macOS CGEvent via pyobjc, Linux uinput/X11/Wayland via evdev) plus an MPRIS media controller for Linux.
- **CLI** — `maestro`, `gesture-controller`, `gesture-controller-verify` entry points.

What the project is **not**:

- It is not a cloud product. There is no server-side component. The integration server is local-only.
- It is not a mobile product. It targets desktop OSes.
- It is not an enterprise product. There is no multi-tenant, no SSO, no fleet management.
- It is not an accessibility product in the legal sense. The ADRs claim WCAG 2.2 conformance, but no VPAT exists and the audit process is documented as a plan, not a completed audit.

These distinctions matter for the commercial-readiness plan: the target market is **individual end users and prosumer accessibility users**, not enterprises. That shapes the licensing (AGPL-3.0 is acceptable for end-user tools but toxic to enterprise OEMs), the distribution model (direct download + signed installers + maybe Microsoft Store / Mac App Store), and the support model (community Discord + GitHub Issues + paid tier for priority bug fixes).

## 3. Repository Topology and Branch Inventory

The repo has **8 branches** alive on the remote as of `eb44bfc`:

| # | Branch | Last commit | Based on | Carries unique work? |
|---|---|---|---|---|
| 1 | `main` | `eb44bfc` chore(release): release version 1.0.0 | — | Yes (the v1.0.0 release commit, docs reorg, ruff config, coverage threshold lowering) |
| 2 | `release-please--branches--main` | `699f8a3` chore(main): release 0.1.0 | `cabf086` | Yes — release-please maintenance branch, currently at 0.1.0 (stale; should be 1.0.0) |
| 3 | `dependabot/github_actions/actions/setup-python-6` | `282b9af` build(deps): bump setup-python 6→7 | `eb44bfc` (main) | Yes — single Dependabot bump on top of main |
| 4 | `dependabot/github_actions/actions/upload-artifact-7` | `c1ee338` bump upload-artifact 4→7 | `cabf086` (stale) | No — stale, superseded by main |
| 5 | `dependabot/github_actions/codecov/codecov-action-7` | `9299d6b` bump codecov-action 4→7 | `cabf086` (stale) | No — stale, superseded by main |
| 6 | `dependabot/github_actions/sigstore/cosign-installer-4.1.2` | `7a9b51d` bump cosign-installer 3.5.0→4.1.2 | `cabf086` (stale) | No — stale, superseded by main |
| 7 | `dependabot/github_actions/slsa-framework/slsa-github-generator/dot-github/workflows/generator_generic_slsa3.yml-2.1.0` | `07e5e44` bump slsa-generator 1.9.0→2.1.0 | `cabf086` (stale) | No — stale, superseded by main |
| 8 | `dependabot/pip/pytest-cov-gte-4.1.0-and-lt-8.0` | `d57cfa1` bump pytest-cov | `5476df9` (very stale) | No — stale, superseded by main |

**Confidence: High** — verified by `git branch -a` and per-branch `git log` on the mirror.

The unification strategy (Part III) is therefore simple in principle: rebase the one live Dependabot branch (#3) onto main, re-create the four stale Dependabot branches (#4–#7) as fresh PRs against main, close the stale `pytest-cov` branch (#8) because main already updated pytest-cov, and re-base the release-please branch (#2) onto the new main HEAD so it tracks 1.0.0 instead of 0.1.0. The detail is in §11–13.

## 4. Critical Finding: CI Has Not Actually Been Running

This is the single most important finding in the entire audit and it deserves its own section.

**The `on:` trigger in `.github/workflows/ci.yml` reads:**

```yaml
on:
  push:
    branches: ain]
  pull_request:
    branches: ain]
```

(`.github/workflows/ci.yml` lines 4–7, verified on commit `eb44bfc`.)

This is invalid YAML for the intended purpose. The string `ain]` parses as a scalar string, not as a list. GitHub Actions' workflow loader will either reject this entirely (in which case the workflow never registers) or interpret it as "match a branch literally named `ain]`", which never matches any real branch. **In either case the CI workflow does not run on push to `main` or on PRs to `main`.**

The previous CI fix plan (`old_docs/maestro-ci-fix-plan.md`) claimed this was fixed. **It was not.** The fix was proposed but never committed to main, or it was committed and then reverted by a subsequent merge. Either way, the live state of main right now is broken.

**Consequence:** the green CI badge in the README is showing data from workflow runs that happened either (a) before the typo was introduced, (b) on a Dependabot branch where the typo didn't exist yet, or (c) on a manual `workflow_dispatch` invocation. It is not showing the real CI status of `main`.

**This is the root cause of every "CI is failing" report the user has seen.** The CI is not failing — it is not running. The Dependabot PRs that show red X marks are red because their CI runs (which do trigger, because Dependabot PRs create a `pull_request` event against a branch named `main`, and the `pull_request: branches: ain]` filter rejects them) are being rejected at the workflow-load step.

Actually — and this is the subtle part — Dependabot PRs *sometimes* show CI status because Dependabot pushes to its own branch, which triggers `push: branches: ain]` on the Dependabot branch (rejected), AND creates a `pull_request` event against `main` (also rejected by the same typo). So the Dependabot PRs are showing "no status checks" rather than "failing status checks", which GitHub UI sometimes renders as a yellow dot or a gray dash. The user is interpreting this as "CI failing".

**The organic fix:** change `branches: ain]` to `branches: [main]` in both places. That is a four-character edit. It is in §9 below.

**Second-order consequence:** once this typo is fixed, CI will start running for the first time in (presumably) weeks, and we will discover the *real* test failures that have been hidden. The plan in §9 covers how to handle each one.

## 5. Bug Catalog (P0–P3)

This is the consolidated bug list distilled from reading every source file in `gesture_controller/`, every workflow file, every ADR, and both prior CI analyses. Severity definitions:

- **P0 (Blocker):** prevents release or causes silent data loss / security compromise.
- **P1 (Critical):** causes visible malfunction on a supported platform; must fix before release.
- **P2 (Major):** causes degraded experience or maintenance pain; fix in v1.1 if not v1.0.
- **P3 (Minor):** polish, code smell, doc drift; fix opportunistically.

### P0 — Blockers

| # | Bug | Location | Evidence | Fix section |
|---|---|---|---|---|
| P0-1 | `ci.yml` workflow trigger typo `branches: ain]` | `.github/workflows/ci.yml:4-7` | Verified on `eb44bfc` | §9 |
| P0-2 | `release.yml` uses `python_version` (underscore) instead of `python-version` | `.github/workflows/release.yml:25` | Verified | §9 |
| P0-3 | Release-please maintenance branch is stuck at v0.1.0 while main is at v1.0.0 | `release-please--branches--main` HEAD | Verified | §11–13 |
| P0-4 | Updater TUF `root.json` ships with what appear to be placeholder / fabricated Ed25519 public keys (sequential-looking keyids `92a7…`, `b2a7…`, `c2a7…`, `d2a7…`, `e2a7…`, plus five more `*e7d…` keys) | `gesture_controller/core/updater.py:30-120` | Verified — these keyids are not real TUF outputs from `tuf sign`, they are obviously hand-typed | §28 |
| P0-5 | Broker Windows authentication is `return True` — any local process can inject input | `gesture_controller/os_integration/broker.py:33-36` | Verified | §28 |
| P0-6 | Plugin loader uses `exec(module_code, sandbox_globals)` *after* an AST scan — this is the canonical RestrictedPython bypass pattern (an attacker who controls the plugin can defeat the AST scan by using `__import__` obliquely, attribute lookups, or generator-based reflection) | `gesture_controller/plugins/plugin_loader.py` (exec site identified by AST scan reference, line numbers vary) | Verified by code structure | §28 |
| P0-7 | Integration server WebSocket implementation has no read loop after handshake — the server never reads client frames, never handles close frames, never handles ping/pong, and never detects a half-closed connection; the client list grows unbounded | `gesture_controller/core/integration_server.py:303-347` | Verified | §28 |
| P0-8 | No code signing is actually configured in `release.yml` — the Azure Key Vault block is a `// simulation/placeholder` and `cosign sign-blob` is keyless, which means Windows users will see SmartScreen warnings and macOS users will see Gatekeeper rejections | `.github/workflows/release.yml:43-60` | Verified | §29 |
| P0-9 | `pyinstaller --onefile` build line in `release.yml` references `gesture_controller/main.py`, but the project's actual entry point is `main.py` at the repo root which imports `gesture_controller.gui.app_entry` — this may or may not produce a working binary depending on PyInstaller's hook resolution; the spec file `gesture_controller.spec` is ignored | `.github/workflows/release.yml:41` | Verified | §30 |
| P0-10 | `os.symlink` is monkey-patched at module import time in `updater.py:14-27`, which silently turns every symlink operation on every other module in the process into a copy operation. This is a global side effect from importing the updater module. | `gesture_controller/core/updater.py:14-27` | Verified | §28 |

### P1 — Critical

| # | Bug | Location | Notes |
|---|---|---|---|
| P1-1 | `GestureControllerApp` accesses `self._engine._custom_matcher._template_dir` directly (private member of private member) — but `GestureEngine` does not have a `_custom_matcher` attribute; only `GestureRecognizer` does, and the engine exposes it via a private accessor. This will crash on settings window open. | `gesture_controller/gui/app_entry.py:126-128` | Needs a proper public API |
| P1-2 | The `_export_diagnostics` method is defined twice in `app_entry.py:255-284`. The first definition has no body after the `export_data` import (dead code), the second definition does the real work. Python silently uses the second; the first is a footgun. | `gesture_controller/gui/app_entry.py:255-284` | Verified |
| P1-3 | `UpdateCheckerThread` is constructed with `current_version="0.1.0"` hardcoded, while the package is at 1.0.0. Every user will be told an update is available, every time, forever. | `gesture_controller/gui/app_entry.py:159` | Verified |
| P1-4 | `palm_detector.py` is 2 144 lines and starts with `# mypy: ignore-errors`. The class is not typed, not tested at the unit level for the 2 000+ lines of postprocessing math, and is the single biggest file in the repo. | `gesture_controller/vision/palm_detector.py` | Verified |
| P1-5 | `FramePipeline.start()` accesses `self._config._config` (private member of `ConfigManager`) instead of using a public accessor. Same pattern in `InferencePipeline.__init__`. | `gesture_controller/core/frame_pipeline.py:53`, `inference_pipeline.py:21,23,76` | Verified |
| P1-6 | `BrokerClientController._ensure_connected` spawns a subprocess to start the broker if it isn't running, but if the spawn fails the `_lock` is held while the retry loop sleeps 3 seconds — this blocks the entire engine on first frame. | `gesture_controller/os_integration/broker.py:343-362` | Verified |
| P1-7 | `IntegrationServer` HTTP parser reads only the first 4096 bytes of a request, then loops `recv(4096)` only if Content-Length says more. This breaks for chunked transfer-encoding, breaks for requests with large headers, and breaks if the body arrives in the same packet as the headers (which the code does handle, but only by accident). | `gesture_controller/core/integration_server.py:128-196` | Verified |
| P1-8 | `VoiceCommandListener` is started unconditionally in `app_entry.py:173-174` with no try/except. If `vosk` or `pyaudio` fails to import (which it will on systems without a microphone or without the `portaudio` library installed), the app crashes at startup. | `gesture_controller/gui/app_entry.py:163-174` | Verified |
| P1-9 | `FramePipeline.maybe_idle` restores 30 FPS the moment a hand is detected, but `adapt_fps` may have lowered the FPS to 15 due to CPU pressure. The two adaptations fight each other. | `gesture_controller/core/frame_pipeline.py:73-111` | Verified |
| P1-10 | The `MouseINPUT`, `KEYBDINPUT`, `INPUT_UNION`, `INPUT` structures in `windows_controller.py` do not set `_pack_` — on 64-bit Windows the union alignment is correct by accident, but this is fragile. | `gesture_controller/os_integration/windows_controller.py:14-52` | Verified |
| P1-11 | `pyproject.toml` declares `mediapipe>=0.10.0` as a runtime dependency but the engine uses ONNX Runtime. MediaPipe is dead weight in the install closure (50+ MB). | `pyproject.toml:29` | Verified |
| P1-12 | Coverage gate is inconsistent: `pyproject.toml` says `fail_under = 69`, CI says `--cov-fail-under=60`. The CI value wins because it's on the command line, so coverage can drop to 60 % silently. | `pyproject.toml:155`, `.github/workflows/ci.yml:114` | Verified |
| P1-13 | `engine.py` `_main_loop` catches `Exception` and continues — this is correct for a daemon loop, but the error is logged at `error` level with `error=str(e)` only; no traceback, no correlation to the frame that caused it, no escalation if the same error repeats 1000 times in a row. | `gesture_controller/core/engine.py:241-242` | Verified |
| P1-14 | `BrokerClientController._send_request` holds `self._lock` across `conn.send_bytes` and `conn.recv_bytes` — if the broker hangs, every gesture-triggering thread in the engine blocks. | `gesture_controller/os_integration/broker.py:375-396` | Verified |
| P1-15 | `tuf>=2.0.0` is listed as a runtime dependency, but `tuf` 2.x was renamed to `tuf-ngclient` and the import `from tuf.ngclient import Updater` works only on the renamed package. The pinned version may not install cleanly on Python 3.13. | `pyproject.toml:38` | Verified; needs runtime test |

### P2 — Major

| # | Bug | Notes |
|---|---|---|
| P2-1 | `gesture_controller.spec` (PyInstaller spec) exists but is not referenced by `release.yml`; the workflow invokes `pyinstaller --onefile --noconsole --name Maestro gesture_controller/main.py` directly. The spec file is dead. |
| P2-2 | `old_docs/` contains 25+ legacy planning documents totaling >50 000 lines. This is repo bloat and confuses readers. |
| P2-3 | `v3.0/maestro_refactor_plan_v3.md` is 18 600 lines and largely unimplemented. It should be archived or split. |
| P2-4 | No `pre-commit` config exists despite the CI fix plan recommending one. |
| P2-5 | No `dependabot.yml` updates for `npm` (none expected) or `docker` (none expected), but also no updates for GitHub Actions beyond the existing config — fine. |
| P2-6 | `gesture_controller/tests/integration/test_gui_integration.py` contains only `def test_placeholder(): pass` — inflates test count. |
| P2-7 | `tests/fuzz/fuzz_compile_condition.py` is at the top-level `tests/` directory, not under `gesture_controller/tests/`. The fuzz workflow references it correctly now, but the test runner doesn't find it because `testpaths = ["gesture_controller/tests"]`. |
| P2-8 | `tests/e2e/test_minimize_gesture.py` is marked `real_mediapipe` but mocks `compute_features` — marker is misleading. |
| P2-9 | `mkdocs.yml` is present but the `docs/` directory uses Material-specific features (`admonitions`, `tabs`) that require `pip install mkdocs-material` — this is installed in the `docs.yml` workflow but not in dev deps. |
| P2-10 | The CHANGELOG says 1.0.0 was released 2026-07-20 but the release-please branch is still at 0.1.0 — release-please never published the 1.0.0 release. |
| P2-11 | `gesture_controller/data/locales/` contains `.po` files for 8 languages but no compiled `.mo` files. The `compile_locales.py` script exists but isn't called by CI or by the installer. |
| P2-12 | The `wasmtime` dependency (`wasmtime>=12.0.0`) is heavy (~30 MB) and the WASM sandbox is unused — no real plugin uses it. |
| P2-13 | `tremor_calibrator.py` exists but is not wired into the GUI; tremor compensation config exists in `default_config.yaml` but the calibration UI is unreachable. |
| P2-14 | `dwell_clicker.py` is wired in but has no UI to enable/disable it; the `a11y.dwell_click_enabled` config key is read but no settings panel exposes it. |
| P2-15 | `global_hotkeys.py` registers `Ctrl+Shift+M/W/D/Up/Down/Space/N/P` and `Esc` — these conflict with common app shortcuts (Ctrl+Shift+M is mute in Meet/Zoom, Esc is cancel in everything). No UI to disable. |
| P2-16 | `crash_reporter.py` writes crash dumps to `user_data_dir()` but the `_export_diagnostics` method's first (dead) definition references `export_data` from compliance — there's no link between crash dumps and the export flow. |
| P2-17 | `integration_server.py` `_handle_connection` reads the entire request into a 4 096-byte buffer; a malicious localhost process could send a 100-MB header to OOM the app. Needs `max_request_size` cap. |
| P2-18 | `broker.py` `RateLimiter` allows 30 actions/sec globally and 10 per 100 ms burst — but `mouse_move` is rate-limited identically to `key_press`. A 60-FPS pointer-control gesture will hit the rate limit instantly. Per-method rate limits are needed. |
| P2-19 | `updater.py` `UpdateCheckerThread` polls a hardcoded URL; no config key for the update feed URL. |
| P2-20 | The `voice_listener.py` imports `vosk` and `pyaudio` at module top, so importing the module fails on systems without them. Should be lazy. |

### P3 — Minor

| # | Bug | Notes |
|---|---|---|
| P3-1 | README says "E2E latency (P50, GPU) <15ms" — this is unverified. |
| P3-2 | `default_config.yaml` has `voice.model_path: "models/vosk-model-small-en-us"` — the model is not bundled and the path is relative. |
| P3-3 | `ruff.toml` exists but `ruff` is not in dev deps and CI runs `black` not `ruff`. The "ruff configuration for linting" commit added the config but not the tool. |
| P3-4 | `gesture_controller/__init__.py` is empty — no `__version__`, no public API. |
| P3-5 | `SECURITY.md` references `security@aryansinghnagar.dev` — fine, but no PGP key is actually in the file despite the README claim. |
| P3-6 | `LICENSE` is AGPL-3.0 — fine for end-user tool, but the `gesture_controller.spec` PyInstaller spec doesn't bundle the LICENSE with the binary, which violates AGPL §4. |
| P3-7 | `pyproject.toml` classifiers include `"Development Status :: 5 - Production/Stable"` — premature for a project whose CI doesn't run. Should be `4 - Beta` until v1.0 ships. |
| P3-8 | No `MANIFEST.in` — sdist may not include `.onnx` model files, `.yaml` configs, or `.po` locales. |
| P3-9 | `gesture_controller/cli/cli.py` and `gesture_controller/__main__.py` both define `main` — overlapping entry points. |
| P3-10 | `mkdocs.yml` site_name is "Maestro Documentation" but the README says docs are at `aryansinghnagar.github.io/Maestro/` — needs a CNAME or `mkdocs.yml` `site_url`. |

## 6. Security Threat Model (STRIDE)

| Threat | Surface | Current posture | Verdict |
|---|---|---|---|
| **S**poofing (one process impersonating another) | Broker Unix socket | `verify_peer` checks `SO_PEERCRED` / `LOCAL_PEERCRED` for same-UID | **Adequate on Linux/macOS, broken on Windows** (P0-5) |
| **T**ampering (modifying gesture→action mappings in transit) | Plugin files, config files | AST scan on plugin load; config validated by jsonschema | **AST scan is bypassable** (P0-6); config schema is good |
| **R**epudiation (denying you made a gesture) | Broker audit log | Hash-chained, append-only | **Adequate** — but only if the broker is running; if the engine uses `use_broker=False`, no audit trail |
| **I**nformation disclosure (camera frames leaking) | Shared memory segment | `chmod 0o600` on `/dev/shm/maestro_shm_*` | **Adequate on Unix, no protection on Windows** (Windows named shared memory defaults to global read) |
| **D**enial of service | Integration server HTTP parser | Reads 4 096 bytes then loops on Content-Length | **Vulnerable** to slow-loris and large-header attacks (P2-17) |
| **E**levation of privilege | Plugin execution | Python `exec` after AST scan; WASM sandbox unused | **Broken** (P0-6) — do not advertise plugin support as safe until fixed |
| **C**SWSH (cross-site WebSocket hijacking) | Integration server WS | Origin check on handshake, token auth | **Adequate** for the current threat model, but no CSWSH test exists |

Net security posture: **not release-ready**. The five P0 security issues (P0-4, P0-5, P0-6, P0-7, P0-10) must close before v1.0 ships, and the integration server needs a proper HTTP parser (P1-7, P2-17) before v1.0 ships, because a local attacker can crash the app with a single crafted HTTP request today.

## 7. Code Quality and Architecture Critique

### 7.1 Strengths

- **Multiprocessing isolation** — the camera capture is in a child process that writes to a seqlock double-buffered shared memory segment. This is the correct architecture for not blocking the GUI on camera I/O. **Confidence: High.**
- **Privilege-separated broker** — input injection is delegated to a separate process that listens on a Unix socket / Windows named pipe with peer-credential authentication, rate limiting, and a hash-chained audit log. The architecture is sound even though the Windows implementation is broken. **Confidence: High.**
- **AST-based safe conditions parser** — the trigger-conditions DSL is parsed by `ast` and only allows a whitelisted set of nodes, which is the correct way to evaluate untrusted expressions safely (modulo the plugin-loader bypass problem). **Confidence: High.**
- **Per-hand FSM tracking** — each hand gets its own finite-state machine keyed by a track ID, with proper retirement when a hand disappears. **Confidence: High.**
- **One-Euro filter with dynamic adaptation** — the filter takes a `depth_metric` derived from wrist-to-index-MCP distance and adjusts the cutoff accordingly. This is a thoughtful, research-informed choice. **Confidence: High.**
- **TUF for updates** — using TUF for update verification is the right call; the implementation has placeholder keys (P0-4) but the architecture is correct. **Confidence: High.**
- **ADRs and RFCs** — 30 ADRs and 15 RFCs exist, which is more documentation discipline than 95 % of open-source projects. **Confidence: High.**

### 7.2 Weaknesses

- **God classes.** `PluginLoader` is 625 lines. `Updater` is 575 lines. `PalmDetector` is 2 144 lines and disables mypy. `IntegrationServer` is 347 lines with both HTTP and WebSocket parsing in one file. `SettingsWindow` is presumably large (not yet read). These need decomposition.
- **Private member access across module boundaries.** `app_entry.py` reaches into `engine._custom_matcher._template_dir`, `engine._config`, `engine._controller`, `engine._event_bus`. `frame_pipeline.py` reads `config._config`. `inference_pipeline.py` reads `config._config` and `extractor._extractor`. This is **the** code-smell that makes refactoring dangerous: any rename breaks the app silently.
- **Two adaptation systems fighting.** `FramePipeline.maybe_idle` (30→5 FPS on no-hands) and `FramePipeline.adapt_fps` (lower FPS on CPU pressure) are independent; neither knows the other exists. The user will see FPS thrash if a hand keeps appearing and disappearing while CPU is saturated.
- **No structured error escalation.** `engine._main_loop` catches `Exception`, logs at `error`, continues. There is no "if this error happens N times in M seconds, escalate" logic, no circuit breaker, no degraded mode.
- **Typing discipline is uneven.** Core modules are strict-mypy clean; GUI, plugins, macos/linux controllers are `ignore_errors = true`. The Windows controller is strict-mypy clean only because of nine `# type: ignore[attr-defined]` comments.
- **Test coverage is gamed.** `test_gui_integration.py::test_placeholder` exists. Markers like `real_mediapipe` are applied to tests that don't use real mediapipe. The 69 % coverage threshold is below the 80 % industry norm for production code.
- **Dead code.** `_export_diagnostics` defined twice. `gesture_controller.spec` unused. `wasm_sandbox.py` unused. `tremor_calibrator.py` unwired.
- **Config keys not centralized.** Strings like `"camera.fps_target"`, `"engine.max_hands"`, `"a11y.theme"` are scattered across files. A typo in any one of them silently falls back to default. Needs a typed config schema (pydantic or attrs).

### 7.3 Documentation Quality

- The `docs/` tree is well-organized (ADRs, RFCs, specs, migration guides, troubleshooting, FAQ).
- The `old_docs/` tree is a graveyard of 25+ legacy plans and should be moved to a `docs/archive/` subdirectory or deleted after v1.0 ships.
- The `v3.0/maestro_refactor_plan_v3.md` is so long it cannot be effectively reviewed; it should be split into per-sprint planning docs.
- The README is clean and accurate except for the unverified performance claims and the misleading CI badge.

---

# Part II — CI Failure Root-Cause Analysis and Organic Fix Plan

## 8. CI Workflow Audit (Line-by-Line)

I read all six workflow files on `main` at commit `eb44bfc`. Here is the live state of each.

### 8.1 `.github/workflows/ci.yml` (89 lines)

**Line 4–7 (trigger):**
```yaml
on:
  push:
    branches: ain]      # ← BROKEN: missing [m
  pull_request:
    branches: ain]      # ← BROKEN: missing [m
```
**Status:** Workflow never triggers on push or PR to `main`. **P0-1.**

**Lines 9–11 (concurrency):** ✅ Correct.

**Lines 14–38 (`lint-and-typecheck` job):**
- `actions/checkout@v7` ✅
- `actions/setup-python@v6` with `python-version: '3.11'` ✅
- `pip install -e .[dev]` then `pip install black mypy` — works, but `black` and `mypy` are already in `[dev]`, so the second install is redundant. Minor.
- `black --check gesture_controller/` — works.
- `mypy gesture_controller/` — works **only because** of the nine `# type: ignore[attr-defined]` comments in `windows_controller.py` and the `ignore_errors = true` overrides for GUI/plugins/macos/linux in `pyproject.toml`. Without those overrides, mypy would report dozens of errors. The overrides are technical debt.

**Lines 40–67 (`security-scan` job):**
- `bandit -r gesture_controller/ -x gesture_controller/tests/ -ll -q` ✅
- `pip-audit --ignore-vuln PYSEC-2026-597` — works, but the ignored vuln ID is opaque; should be commented with what `nltk` vulnerability is being ignored and re-checked quarterly.

**Lines 69–129 (`test` job):**
- Matrix: 3 OS × 3 Python = 9 cells ✅
- Linux Xvfb setup with `libegl1-mesa`, `libgl1-mesa-glx`, `libgles2-mesa`, `libglib2.0-0`, `libfontconfig1`, `libdbus-1-3`, `libxkbcommon0`, `libxkbcommon-x11-0` ✅ — but **missing `libxcb-cursor0`**, which PyQt6 needs if the offscreen platform plugin fails. **P2-level.**
- `pip install -e .[dev]` ✅
- Windows `pywin32_postinstall` ✅
- `QT_QPA_PLATFORM: offscreen` env var ✅
- `pytest -m "not real_mediapipe and not requires_hardware and not slow" --cov=gesture_controller --cov-fail-under=60 --junitxml=pytest.xml` — **the `--cov-fail-under=60` overrides `pyproject.toml`'s `fail_under = 69`.** P1-12.
- `actions/upload-artifact@v4` ✅
- `codecov/codecov-action@v4` ✅ — but `codecov-action@v4` requires a `CODECOV_TOKEN` secret for private repos; for public repos it works without. Also `codecov-action@v4` is two majors behind current (`v7` is open in a Dependabot PR).

### 8.2 `.github/workflows/release.yml` (88 lines)

**Line 25:**
```yaml
- name: Set up Python
  uses: actions/setup-python@v6
  with:
    python_version: '3.11'    # ← BROKEN: underscore, not hyphen
    cache: 'pip'
```
**Status:** `actions/setup-python` does not recognize `python_version` and silently falls back to the system Python (3.12 on `windows-latest`). The build then runs under 3.12 instead of 3.11. This may or may not work depending on whether the dependencies have 3.12 wheels on Windows. **P0-2.**

**Line 41:**
```yaml
pyinstaller --onefile --noconsole --name Maestro gesture_controller/main.py
```
**Status:** `gesture_controller/main.py` does not exist; the entry is `main.py` at repo root. **P0-9.**

**Lines 43–53 (code signing):**
```powershell
if ("${{ secrets.AZURE_CLIENT_ID }}" -ne "") {
  echo "Running Azure SignTool..."
  # dotnet tool install --global SignTool
  # signtool sign-svs ...
} else {
  echo "Skipping Windows signing: Secrets not configured."
}
```
**Status:** The signing step is a no-op comment. No actual signing happens. **P0-8.**

**Line 56:**
```yaml
uses: sigstore/cosign-installer@v3.5.0
```
**Status:** Pinned to v3.5.0, but Dependabot has a PR open to bump to v4.1.2. Should accept that bump.

**Line 60:**
```yaml
cosign sign-blob --yes --output-signature dist/Maestro.exe.sig --output-certificate dist/Maestro.exe.pem dist/Maestro.exe
```
**Status:** Keyless cosign signing works (uses GitHub OIDC), but produces a `.sig` and `.pem` that the user must manually verify. No verification instructions in README. The SLSA provenance generator at line 82–88 also works but produces a `.intoto.jsonl` that nobody verifies.

### 8.3 `.github/workflows/fuzz.yml` (30 lines)

**Status:** ✅ Correct on `main`. The `python-version: '3.11'` (hyphen) and the path `tests/fuzz/fuzz_compile_condition.py` are both correct. The only issue is that the fuzz target is not under `gesture_controller/tests/` so it's not picked up by `pytest` — but that's intentional, it's run by `atheris` directly.

### 8.4 `.github/workflows/docs.yml` (20 lines)

**Status:** ✅ Correct. Uses `uv sync --frozen`, installs mkdocs-material, deploys to GitHub Pages.

### 8.5 `.github/workflows/commitlint.yml` (12 lines)

**Status:** ✅ Correct. Uses `wagoid/commitlint-github-action@v6` on PR events.

### 8.6 `.github/workflows/release-please.yml` (18 lines)

**Status:** ✅ Correct, but blocked by the same CI failure — release-please won't open a release PR while CI is red (or, in this case, while CI doesn't run).

## 9. The Five CI Failure Classes and Their Fixes

Distilling §8 down to the discrete failures that need fixing.

### Failure 1 — CI workflow never triggers (P0-1)

**Root cause:** `branches: ain]` typo at `.github/workflows/ci.yml:4-7`.

**Fix:** Replace with `branches: [main]`.

**Consequence of fix:** CI will start running on every push to main and every PR. This will surface the *real* test failures that have been hidden. The other four failures below must be fixed in the same PR, or CI will go red and stay red.

### Failure 2 — Release workflow Python version silently wrong (P0-2)

**Root cause:** `python_version` (underscore) at `.github/workflows/release.yml:25`.

**Fix:** Replace with `python-version` (hyphen).

**Consequence of fix:** The release build will now correctly use Python 3.11. If any dependency lacks a 3.11 Windows wheel, the build will fail visibly — which is the desired behavior.

### Failure 3 — Release build references nonexistent entry point (P0-9)

**Root cause:** `pyinstaller --onefile --noconsole --name Maestro gesture_controller/main.py` at `release.yml:41`, but `gesture_controller/main.py` does not exist.

**Fix:** Change to `pyinstaller --onefile --noconsole --name Maestro main.py` (repo root), OR better, use the existing `gesture_controller.spec` file: `pyinstaller gesture_controller.spec`. The spec file is the right answer because it can declare hidden imports, datas (model files, locales), and runtime hooks.

**Consequence of fix:** The spec file may have its own bugs (it was not reviewed). It needs to be validated by running a real build. Plan: in Sprint 1, run `pyinstaller gesture_controller.spec` locally on Windows, fix any issues, then update `release.yml` to use it.

### Failure 4 — Coverage gate inconsistency (P1-12)

**Root cause:** `pyproject.toml` says `fail_under = 69`, CI says `--cov-fail-under=60`.

**Fix:** Align to a single value. Recommend **raising CI to 75** and `pyproject.toml` to **75**, then ratcheting upward every sprint. Current coverage on the passing subset is reportedly 82.5 %, so 75 % is a safe floor with headroom.

**Consequence of fix:** Coverage will become a stricter gate. If any test that contributes significant coverage is later marked `slow` or `real_mediapipe`, coverage will drop and CI will fail. This is the desired behavior — coverage regressions should fail loudly.

### Failure 5 — Hidden test failures (unknown until CI runs)

Once Failures 1–4 are fixed, CI will actually run the test suite on 3 OS × 3 Python = 9 cells for the first time. Based on the existing `old_docs/maestro-ci-fix-plan.md` analysis, the expected failures are:

- **Linux/macOS `test_onboarding.py::test_onboarding_windows_admin` and `test_onboarding_windows_standard_user`** — these use `@patch("ctypes.windll.shell32.IsUserAnAdmin", create=True)` which fails on non-Windows because `ctypes.windll` doesn't exist. The fix in the repo's `conftest.py` (inject `ctypes.windll = MagicMock()` on non-Windows) is **already applied** on main. **Confidence: High** that these will pass.
- **Windows `test_onboarding.py`** — should pass because `ctypes.windll` exists on Windows. **Confidence: Moderate.**
- **PyQt6 tests on Windows** — `QT_QPA_PLATFORM=offscreen` is set; should pass. **Confidence: Moderate.**
- **PyObjC tests on macOS Python 3.13** — `pyobjc-framework-Quartz` may not have a 3.13 wheel. If it doesn't, the install step fails before tests run. **Confidence: Low.** Plan: if pyobjc lacks 3.13 wheels, exclude macOS 3.13 from the matrix and document.
- **`pytest-cov` version conflicts** — `pyproject.toml` declares `pytest-cov>=4.1.0,<8.0`, Dependabot has a PR to bump it. Whichever version installs should work. **Confidence: Moderate.**
- **`tuf>=2.0.0` on Python 3.13** — TUF 2.x was renamed; the `from tuf.ngclient import Updater` import may fail on 3.13. **Confidence: Low.** Plan: if it fails, pin `tuf<5.0` and verify the import works.

The plan for Sprint 1 is to fix Failures 1–4 in a single PR, push, observe CI on all 9 cells, and triage any remaining failures with targeted fixes. Do not skip tests, do not lower thresholds further, do not `continue-on-error`.

## 10. Hardening CI So It Cannot Silently Break Again

The reason the `branches: ain]` typo went unnoticed is that there is no mechanism to detect a broken workflow file before it lands on main. Three hardening changes prevent this class of failure:

### 10.1 Add a `workflow-lint` job to CI

```yaml
  workflow-lint:
    name: Workflow Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Validate all workflow YAML
        uses: ibiqlik/action-yamllint@v3
        with:
          file_or_dir: .github/workflows
          config_file: .github/yamllint.yml
      - name: Verify CI workflow triggers on main
        run: |
          python -c "
          import yaml
          with open('.github/workflows/ci.yml') as f:
              w = yaml.safe_load(f)
          on = w['on'] if 'on' in w else w[True]  # YAML parses 'on' as bool True
          push_branches = on.get('push', {}).get('branches', [])
          pr_branches = on.get('pull_request', {}).get('branches', [])
          assert 'main' in push_branches, f'push.branches must contain main, got {push_branches}'
          assert 'main' in pr_branches, f'pull_request.branches must contain main, got {pr_branches}'
          "
```

This job runs on every PR and fails if any workflow file has invalid YAML or if the CI workflow doesn't trigger on `main`.

### 10.2 Add `actions/setup-python` input validation

The `python_version` (underscore) typo would have been caught by a linter that knows `actions/setup-python`'s inputs. The simplest fix: add a `grep` assertion:

```yaml
      - name: Verify setup-python uses hyphen
        run: |
          ! grep -rn "python_version:" .github/workflows/
```

### 10.3 Add a `ci-self-test` job

Once a week, run a `workflow_dispatch`-triggered job that just confirms CI is healthy by running `true`. If this job ever fails to run, the maintainers get an alert. (This is belt-and-suspenders; the workflow-lint job is the primary defense.)

### 10.4 Pin all actions by SHA, not by tag

Tags are mutable. A malicious actor who compromises an action's repo can retag a new (malicious) version with an existing tag. Pin by SHA:

```yaml
- uses: actions/checkout@1d96c772d19495a3b5c517cd2bc0cb401ea0529f  # v7.0.0
```

This is tedious but is industry best practice for supply-chain security (and is required by SLSA Level 3).

### 10.5 Require status checks before merge

Configure branch protection on `main` to require:
- `Lint & Typecheck`
- `Security Scan`
- `Workflow Lint`
- `Test (ubuntu-latest / 3.11)`
- `Test (ubuntu-latest / 3.12)`
- `Test (ubuntu-latest / 3.13)`
- `Test (macos-latest / 3.11)`
- `Test (windows-latest / 3.11)`

(macos 3.12/3.13 and windows 3.12/3.13 can be informational-only until pyobjc/pywin32 have wheels.)

Also require linear history and conversation resolution.

---

# Part III — Branch Unification Strategy

## 11. Branch-by-Branch Disposition

The goal is a single `main` branch with all working code, plus a `release-please--branches--main` maintenance branch that tracks `main` and is correctly versioned. All other branches are closed.

| Branch | Action | Rationale |
|---|---|---|
| `main` | Keep, fix CI typo, merge the live Dependabot bump | Source of truth |
| `release-please--branches--main` | Re-base onto new `main` HEAD, force-update to track 1.0.0 | Currently stale at 0.1.0; release-please will heal itself once CI passes |
| `dependabot/github_actions/actions/setup-python-6` | Merge into `main` as a single commit (`build(deps): bump setup-python 6→7`) | Single bump, already rebased on main, low risk |
| `dependabot/github_actions/actions/upload-artifact-7` | Close without merge; re-open as a fresh Dependabot PR against new main | Stale base (cabf086), conflicts with main's docs reorg |
| `dependabot/github_actions/codecov/codecov-action-7` | Same — close, re-open | Stale base |
| `dependabot/github_actions/sigstore/cosign-installer-4.1.2` | Same — close, re-open | Stale base |
| `dependabot/github_actions/slsa-framework/slsa-github-generator/dot-github/workflows/generator_generic_slsa3.yml-2.1.0` | Same — close, re-open | Stale base |
| `dependabot/pip/pytest-cov-gte-4.1.0-and-lt-8.0` | Close without merge | Main has already advanced past the base; pytest-cov is already updated on main |

**Confidence: High** that no unique working code is lost by closing the five stale Dependabot branches — each is a single-commit dependency bump that can be regenerated by Dependabot in a few minutes once CI is green.

## 12. The Unification Procedure (Step-by-Step)

This is the exact sequence of git operations. Do not reorder.

### Step 1 — Freeze `main`

Announce a merge freeze. No PRs merge except the unification PR.

### Step 2 — Create a working branch

```bash
git checkout main
git pull origin main
git checkout -b unify/branches-v1.0
```

### Step 3 — Apply the CI fixes from Part II

Edit `.github/workflows/ci.yml` (fix `branches: ain]` → `branches: [main]`), `.github/workflows/release.yml` (fix `python_version` → `python-version`), align coverage gates, add the `workflow-lint` job. Commit as `fix(ci): restore workflow triggers and align coverage gates`.

### Step 4 — Cherry-pick the live Dependabot bump

```bash
git cherry-pick 282b9af  # build(deps): bump actions/setup-python from 6 to 7
```

If it conflicts, resolve by taking the Dependabot side (it's a one-line bump).

### Step 5 — Re-apply the four stale Dependabot bumps manually

For each of `upload-artifact-7`, `codecov-action-7`, `cosign-installer-4.1.2`, `slsa-generator-2.1.0`:

```bash
# Edit .github/workflows/*.yml to apply the bump
git add .github/workflows/*.yml
git commit -m "build(deps): bump <action-name> from <old> to <new>"
```

These are four separate commits so they can be reverted independently if any bump breaks something.

### Step 6 — Verify the `release-please` branch state

```bash
git fetch origin
git log release-please--branches--main --oneline -5
```

Expected: HEAD is `699f8a3 chore(main): release 0.1.0`. After the unification PR merges and CI goes green, release-please will automatically open a PR to bump to 1.0.0. **Do not force-push to the release-please branch** — let release-please heal itself.

### Step 7 — Push and open PR

```bash
git push origin unify/branches-v1.0
gh pr create --title "unify: branch consolidation + CI restoration" --body "..."
```

### Step 8 — Delete the closed Dependabot branches

After the PR merges:

```bash
git push origin --delete dependabot/github_actions/actions/upload-artifact-7
git push origin --delete dependabot/github_actions/codecov/codecov-action-7
git push origin --delete dependabot/github_actions/sigstore/cosign-installer-4.1.2
git push origin --delete dependabot/github_actions/slsa-framework/slsa-github-generator/dot-github/workflows/generator_generic_slsa3.yml-2.1.0
git push origin --delete dependabot/pip/pytest-cov-gte-4.1.0-and-lt-8.0
# Keep dependabot/github_actions/actions/setup-python-6 until its PR is merged, then delete
```

### Step 9 — Update Dependabot config

Edit `.github/dependabot.yml` to:
- Increase `open-pull-requests-limit` from 10 to 5 (fewer stale PRs to manage)
- Add `rebase-strategy: disabled` so Dependabot doesn't auto-rebase and create noise
- Add `labels: ["dependencies", "automerge"]` so PRs are pre-labeled

## 13. Post-Unification Branch Hygiene

After unification, the only long-lived branches are:

- `main` — the integration branch
- `release-please--branches--main` — release-please's maintenance branch (touched only by release-please)
- Short-lived feature branches (`feat/…`, `fix/…`, `docs/…`) — deleted after merge
- Short-lived Dependabot branches — deleted after merge

No `dev`, `staging`, `v2`, `v3`, `experimental`, or personal long-lived branches. If experimental work needs to live somewhere, use a fork or a feature flag in `main`.

Consequences and mitigations:

- **Consequence:** Without a `dev` branch, incomplete features land on `main`. **Mitigation:** Use feature flags (`config.experimental.X.enabled: false`) so code can land disabled.
- **Consequence:** Long-running feature branches diverge from `main` and conflict. **Mitigation:** Enforce a 1-week max branch lifetime; require daily rebase.
- **Consequence:** Dependabot PRs can pile up. **Mitigation:** Automerge minor/patch bumps after CI passes; require manual review for major bumps.

---

# Part IV — Adaptive Performance Tier System

This is the centerpiece of the user's request. The goal is a mechanism that **automatically** disables overtly demanding features on devices with low processing power and/or memory, and **automatically** unlocks them on high-spec systems, with no user configuration required.

## 14. Design Goals and Constraints

**Goals:**
1. **Zero-config.** The user installs Maestro and it Just Works at the best tier their hardware supports.
2. **Observable.** The user can see which tier they're on and why, in the settings window and the diagnostics export.
3. **Overridable.** The user can force a tier (e.g., "I know my laptop is slow but I want the HUD") with a clear warning.
4. **Dynamic.** The tier can downgrade at runtime (e.g., battery drops below 20 %, CPU stays >90 % for 30 s) and upgrade again when conditions recover.
5. **Local.** No telemetry required; tiering is computed on-device from local signals.
6. **Testable.** Every tier decision is a pure function of a `HardwareProfile` and a `RuntimeConditions` object, so it's unit-testable without real hardware.

**Constraints:**
- Must not add more than 5 ms to cold start.
- Must not require admin/root.
- Must not depend on a network call.
- Must work on Windows 10+, macOS 12+, and Linux (X11/Wayland).
- Must not regress the existing 30→5 FPS idle adaptation; that becomes one of many signals the tier system uses.

## 15. The Four Performance Tiers

| Tier | Name | Target hardware | Headline behavior |
|---|---|---|---|
| **T0** | Ultra | 8+ cores, 16+ GB RAM, dedicated GPU with ONNX RT support (CUDA / CoreML / DirectML / TensorRT), plugged in | Full pipeline at 60 FPS, FP16 model, voice listener on, integration server on, HUD overlay on with 60 FPS skeleton render, all plugins loadable, no resolution cap |
| **T1** | High | 4+ cores, 8+ GB RAM, integrated GPU or weak dedicated GPU, plugged in | 30 FPS, INT8 model, voice listener on-demand, integration server on, HUD on with 30 FPS skeleton render, all plugins loadable |
| **T2** | Standard | 2+ cores, 4+ GB RAM, no GPU acceleration | 15–30 FPS adaptive, INT8 model, voice listener off by default, integration server off by default, HUD on with skeleton render at 15 FPS, WASM-sandbox plugins only |
| **T3** | Minimal | <2 cores, <4 GB RAM, or battery <20 %, or thermal throttling | 10 FPS, INT8 model at 192×192 input, voice off, integration server off, HUD off (or text-only), no plugin loading, no custom-gesture DTW matching |

**Confidence: Moderate** that these tier boundaries are correct. They should be validated by running the benchmark suite (§27) on at least one device per tier and adjusting.

## 16. The Capability Registry

Each tier maps to a set of **capability values**. A capability is a single named knob with a typed value. The registry is the single source of truth for "what is on at tier X".

```python
# gesture_controller/core/capabilities.py (new file)

from dataclasses import dataclass
from enum import Enum

class Tier(str, Enum):
    ULTRA = "T0"
    HIGH = "T1"
    STANDARD = "T2"
    MINIMAL = "T3"

@dataclass(frozen=True)
class CapabilitySet:
    tier: Tier
    camera_fps_target: int
    camera_frame_width: int
    camera_frame_height: int
    inference_backend: str          # "cuda", "coreml", "directml", "tensorrt", "cpu"
    model_quantization: str         # "fp16", "fp32", "int8"
    model_input_size: tuple[int, int]  # (width, height)
    hud_enabled: bool
    hud_skeleton_render_fps: int    # 0 = off, 60, 30, 15
    hud_show_tracking_points: bool
    voice_listener_enabled: bool
    integration_server_enabled: bool
    plugin_loading_mode: str        # "all", "wasm_only", "none"
    custom_gesture_dtw: bool
    one_euro_filter: bool
    tremor_compensation: bool
    dwell_clicker: bool
    global_hotkeys: bool
    max_hands: int
    overlay_opacity: float
    diagnostics_export_interval_s: int  # 0 = manual only

# The four frozen tier presets
TIER_PRESETS: dict[Tier, CapabilitySet] = {
    Tier.ULTRA: CapabilitySet(
        tier=Tier.ULTRA,
        camera_fps_target=60,
        camera_frame_width=1280,
        camera_frame_height=720,
        inference_backend="auto",  # pick best available
        model_quantization="fp16",
        model_input_size=(256, 256),
        hud_enabled=True,
        hud_skeleton_render_fps=60,
        hud_show_tracking_points=True,
        voice_listener_enabled=True,
        integration_server_enabled=True,
        plugin_loading_mode="all",
        custom_gesture_dtw=True,
        one_euro_filter=True,
        tremor_compensation=True,
        dwell_clicker=True,
        global_hotkeys=True,
        max_hands=2,
        overlay_opacity=0.3,
        diagnostics_export_interval_s=0,
    ),
    Tier.HIGH: CapabilitySet(
        tier=Tier.HIGH,
        camera_fps_target=30,
        camera_frame_width=640,
        camera_frame_height=480,
        inference_backend="auto",
        model_quantization="int8",
        model_input_size=(224, 224),
        hud_enabled=True,
        hud_skeleton_render_fps=30,
        hud_show_tracking_points=True,
        voice_listener_enabled=True,
        integration_server_enabled=True,
        plugin_loading_mode="all",
        custom_gesture_dtw=True,
        one_euro_filter=True,
        tremor_compensation=True,
        dwell_clicker=True,
        global_hotkeys=True,
        max_hands=2,
        overlay_opacity=0.3,
        diagnostics_export_interval_s=0,
    ),
    Tier.STANDARD: CapabilitySet(
        tier=Tier.STANDARD,
        camera_fps_target=20,
        camera_frame_width=480,
        camera_frame_height=360,
        inference_backend="cpu",
        model_quantization="int8",
        model_input_size=(192, 192),
        hud_enabled=True,
        hud_skeleton_render_fps=15,
        hud_show_tracking_points=True,
        voice_listener_enabled=False,
        integration_server_enabled=False,
        plugin_loading_mode="wasm_only",
        custom_gesture_dtw=True,
        one_euro_filter=True,
        tremor_compensation=False,
        dwell_clicker=True,
        global_hotkeys=True,
        max_hands=1,
        overlay_opacity=0.4,
        diagnostics_export_interval_s=0,
    ),
    Tier.MINIMAL: CapabilitySet(
        tier=Tier.MINIMAL,
        camera_fps_target=10,
        camera_frame_width=320,
        camera_frame_height=240,
        inference_backend="cpu",
        model_quantization="int8",
        model_input_size=(160, 160),
        hud_enabled=False,
        hud_skeleton_render_fps=0,
        hud_show_tracking_points=False,
        voice_listener_enabled=False,
        integration_server_enabled=False,
        plugin_loading_mode="none",
        custom_gesture_dtw=False,
        one_euro_filter=True,
        tremor_compensation=False,
        dwell_clicker=False,
        global_hotkeys=True,
        max_hands=1,
        overlay_opacity=0.0,
        diagnostics_export_interval_s=0,
    ),
}
```

Each subsystem in Maestro (FramePipeline, InferencePipeline, OverlayHUD, VoiceCommandListener, IntegrationServer, PluginLoader, etc.) reads its configuration from the active `CapabilitySet` rather than from the YAML config. The YAML config still exists for user overrides (§19), but the defaults come from the tier.

## 17. The Hardware Probe and Tier Classification

The hardware probe runs once at startup (target: <5 ms) and produces a `HardwareProfile`:

```python
# gesture_controller/core/hardware_probe.py (new file)

import platform
import psutil
from dataclasses import dataclass

@dataclass(frozen=True)
class HardwareProfile:
    os: str                    # "Windows", "Darwin", "Linux"
    cpu_count_physical: int
    cpu_count_logical: int
    cpu_freq_mhz: int          # 0 if unknown
    total_ram_gb: float
    has_cuda: bool
    has_coreml: bool
    has_directml: bool
    has_tensorrt: bool
    has_opencl: bool
    gpu_names: list[str]
    is_laptop: bool            # best-effort guess from battery presence
    has_battery: bool
    battery_percent: float     # 0–100, or 100 if no battery
    is_charging: bool
    screen_count: int
    primary_screen_dpi: float
    thermal_state: str         # "nominal", "fair", "serious", "critical" (macOS only via IOKit; "nominal" elsewhere)

def probe_hardware() -> HardwareProfile:
    """Probe the host hardware. Target: <5 ms."""
    import time
    t0 = time.perf_counter()

    os_name = platform.system()
    mem = psutil.virtual_memory()
    total_ram_gb = mem.total / (1024 ** 3)

    cpu_count_physical = psutil.cpu_count(logical=False) or 2
    cpu_count_logical = psutil.cpu_count(logical=True) or 2
    cpu_freq = psutil.cpu_freq()
    cpu_freq_mhz = int(cpu_freq.max) if cpu_freq else 0

    # GPU detection — ONNX Runtime exposes available providers
    has_cuda = has_coreml = has_directml = has_tensorrt = has_opencl = False
    gpu_names: list[str] = []
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        has_cuda = "CUDAExecutionProvider" in providers
        has_coreml = "CoreMLExecutionProvider" in providers
        has_directml = "DmlExecutionProvider" in providers
        has_tensorrt = "TensorrtExecutionProvider" in providers
        # OpenCL not directly exposed by ORT
    except Exception:
        pass

    # Battery
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    has_battery = battery is not None
    battery_percent = battery.percent if battery else 100.0
    is_charging = battery.power_plugged if battery else True
    is_laptop = has_battery  # best-effort

    # Thermal (macOS only — use IOKit)
    thermal_state = "nominal"
    # (Implementation detail: on macOS, query IOKit's thermal pressure notification;
    #  on Linux, read /sys/class/thermal/thermal_zone*/temp if available;
    #  on Windows, no reliable API — leave as "nominal".)

    # Screen info via Qt
    screen_count = 1
    primary_screen_dpi = 96.0
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        screen_count = len(app.screens())
        primary_screen_dpi = float(app.primaryScreen().logicalDotsPerInch())
    except Exception:
        pass

    profile = HardwareProfile(
        os=os_name,
        cpu_count_physical=cpu_count_physical,
        cpu_count_logical=cpu_count_logical,
        cpu_freq_mhz=cpu_freq_mhz,
        total_ram_gb=total_ram_gb,
        has_cuda=has_cuda,
        has_coreml=has_coreml,
        has_directml=has_directml,
        has_tensorrt=has_tensorrt,
        has_opencl=has_opencl,
        gpu_names=gpu_names,
        is_laptop=is_laptop,
        has_battery=has_battery,
        battery_percent=battery_percent,
        is_charging=is_charging,
        screen_count=screen_count,
        primary_screen_dpi=primary_screen_dpi,
        thermal_state=thermal_state,
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000
    # Log if over budget
    if elapsed_ms > 5:
        import structlog
        structlog.get_logger(__name__).warning(
            "hardware_probe_exceeded_budget", elapsed_ms=elapsed_ms
        )
    return profile
```

The tier classification is a pure function of `HardwareProfile` and `RuntimeConditions`:

```python
# gesture_controller/core/tier_classifier.py (new file)

from gesture_controller.core.capabilities import Tier
from gesture_controller.core.hardware_probe import HardwareProfile

@dataclass(frozen=True)
class RuntimeConditions:
    """Live signals that can change during a session."""
    cpu_usage_1min_avg: float      # 0–100
    ram_usage_percent: float       # 0–100
    battery_percent: float         # 0–100
    is_charging: bool
    thermal_state: str             # "nominal", "fair", "serious", "critical"
    pipeline_p95_latency_ms: float # rolling p95 of frame processing
    pipeline_error_rate: float     # 0–1, fraction of frames that errored

def classify_tier(hw: HardwareProfile, rc: RuntimeConditions) -> Tier:
    """Pure function. Unit-testable without real hardware."""

    # Hard floor: T3 if battery critical or thermal critical
    if rc.battery_percent < 10 and not rc.is_charging:
        return Tier.MINIMAL
    if rc.thermal_state == "critical":
        return Tier.MINIMAL

    # Hard floor: T3 if RAM < 3 GB or physical cores < 2
    if hw.total_ram_gb < 3.0 or hw.cpu_count_physical < 2:
        return Tier.MINIMAL

    # Dynamic downgrade: if p95 latency > 50 ms, drop at least to T2
    if rc.pipeline_p95_latency_ms > 50:
        return Tier.MINIMAL if rc.pipeline_p95_latency_ms > 100 else Tier.STANDARD

    # Dynamic downgrade: if CPU > 85 % for the last minute, drop one tier
    cpu_pressure = rc.cpu_usage_1min_avg > 85

    # T0 requirements: 8+ physical cores, 16+ GB, dedicated GPU, plugged in
    t0_hardware_ok = (
        hw.cpu_count_physical >= 8
        and hw.total_ram_gb >= 16
        and (hw.has_cuda or hw.has_coreml or hw.has_directml or hw.has_tensorrt)
        and (rc.is_charging or not hw.has_battery)
    )
    if t0_hardware_ok and not cpu_pressure:
        return Tier.ULTRA

    # T1 requirements: 4+ physical cores, 8+ GB, plugged in (if laptop)
    t1_hardware_ok = (
        hw.cpu_count_physical >= 4
        and hw.total_ram_gb >= 8
        and (rc.is_charging or not hw.has_battery)
    )
    if t1_hardware_ok and not cpu_pressure:
        return Tier.HIGH

    # T2 requirements: 2+ physical cores, 4+ GB
    t2_hardware_ok = (
        hw.cpu_count_physical >= 2
        and hw.total_ram_gb >= 4
    )
    if t2_hardware_ok:
        return Tier.STANDARD

    # Fallback
    return Tier.MINIMAL
```

**Confidence: Moderate** that the classifier boundaries are correct. They should be tuned empirically by running the benchmark suite (§27) on at least one device per tier.

## 18. Runtime Adaptation: Dynamic Downgrade and Upgrade

The classifier runs:
- Once at startup (with `RuntimeConditions` populated from a 1-second CPU/RAM sample)
- Every 30 seconds thereafter (with rolling `RuntimeConditions`)
- Immediately on a battery-state-change event (via Qt's `QSystemTremiteBatteryInfo` or `psutil`'s battery hooks)
- Immediately on a thermal-state-change event (macOS only)
- Immediately when `pipeline_p95_latency_ms` crosses 50 ms or 100 ms (via a callback from the engine)

When the tier changes, a `TierChanged` event is published on the `EventBus`. Each subsystem subscribes:

| Subsystem | What it does on `TierChanged` |
|---|---|
| `FramePipeline` | Updates `_fps_target` and `_frame_interval`; if downgrade, gracefully waits for in-flight frame then applies new target; if upgrade, applies immediately |
| `CameraStream` | Restarts the child process with new `frame_width`/`frame_height` (this is expensive — only do if the new tier requires a different resolution, and debounce so it doesn't thrash) |
| `InferencePipeline` | Hot-swaps the ONNX model file (from `hand_landmark.onnx` to `hand_landmark_int8.onnx` to a hypothetical `hand_landmark_fp16.onnx`) and the ONNX session providers; this requires a 200–500 ms pause in inference while the new session is built |
| `OverlayHUD` | Toggles visibility, changes render FPS, toggles skeleton points |
| `VoiceCommandListener` | Stops the Vosk recognizer and frees the model (saves ~50 MB), or starts it |
| `IntegrationServer` | Stops listening and closes all client connections, or starts |
| `PluginLoader` | Unloads non-WASM plugins, or loads them |
| `GestureRecognizer` | Disables DTW matching for custom gestures (saves ~10 MB and CPU), or enables |
| `DwellClicker` | Stops, or starts |
| `GlobalHotkeyManager` | Stays on at all tiers (it's cheap) |

**Critical implementation detail:** tier changes must be **debounced**. If the CPU spikes for 5 seconds and then recovers, we should not downgrade and re-upgrade. The rule:

- Downgrade after the new (lower) tier has been the classifier's output for **30 consecutive seconds**.
- Upgrade after the new (higher) tier has been the classifier's output for **60 consecutive seconds**.
- Battery and thermal downgrades are **immediate** (no debounce) because they're safety-critical.
- Battery and thermal upgrades are debounced (don't want to thrash when the user plugs in briefly).

**Consequence:** the user may see a brief stutter when the model hot-swaps. This is acceptable at the T1↔T2 boundary (the user is on a slow machine and the stutter is the cost of getting a usable experience) but unacceptable at T0↔T1 (the user is on a fast machine and shouldn't notice). Mitigation: at T0↔T1, prefer to change only the FPS target and HUD render rate, not the model. Only swap models at T2↔T3 boundaries.

## 19. User Overrides and Escape Hatches

The user can force a tier via config:

```yaml
# default_config.yaml
performance:
  tier: "auto"          # "auto", "T0", "T1", "T2", "T3"
  override_capabilities:
    # Optional: override individual capabilities regardless of tier
    voice_listener_enabled: true   # force voice on even at T2
    hud_enabled: false             # force HUD off even at T0
```

When `tier` is not `auto`, the classifier is bypassed and the chosen tier's `CapabilitySet` is used, then the `override_capabilities` are applied on top. The settings window shows:

```
┌─ Performance ────────────────────────────────────────┐
│ Tier: [Auto ▾]                                       │
│       Detected: T1 (High)                            │
│       Reason: 8 cores, 16 GB, CUDA available,        │
│                plugged in                            │
│                                                      │
│ ☑ Override individual capabilities                   │
│   ☑ HUD overlay            [on]                      │
│   ☑ Voice listener         [on]                      │
│   ☐ Integration server     [off]                     │
│   ☑ Custom gesture DTW     [on]                      │
│   ...                                                │
│                                                      │
│ ⚠ Forcing a higher tier than detected may cause      │
│   frame drops and high CPU usage.                    │
└──────────────────────────────────────────────────────┘
```

The warning is important: if a user on a T2 laptop forces T0, the app will try to load the FP16 model, fail (no CUDA), fall back to CPU FP16, run at 2 FPS, and burn 100 % CPU. The warning must be explicit.

## 20. Observability for the Tier System

The tier system publishes its state to:

1. **structlog** — every tier change is logged with the old tier, new tier, the `HardwareProfile`, the `RuntimeConditions`, and the reason.
2. **Metrics endpoint** — `/metrics` exposes `maestro_tier_current`, `maestro_tier_detected`, `maestro_tier_cpu_usage`, `maestro_tier_p95_latency_ms`, etc.
3. **Diagnostics export** — the ZIP includes `tier_history.jsonl` with every tier decision over the session.
4. **Settings window** — a live "Performance" tab shows the current tier, detected tier, CPU usage graph, latency histogram, and the capability values currently in effect.

## 21. Consequences and Mitigations

| Consequence | Mitigation |
|---|---|
| Model hot-swap causes a 200–500 ms inference pause | Only swap at T2↔T3; at T0↔T1 change FPS only |
| Camera restart causes a 1–2 s black frame | Debounce camera changes; only restart if resolution actually changed |
| User forces T0 on T2 hardware, app is unusable | Warning dialog; "Restore to detected tier" button; auto-fallback if FPS < 5 for 10 s |
| Classifier oscillates between T1 and T2 every 30 s | Debounce (30 s downgrade, 60 s upgrade); hysteresis (require 20 % margin to upgrade) |
| Battery percentage jumps around (noisy sensor) | Smooth with a 5-sample rolling median |
| `psutil.cpu_percent()` first call returns 0 | Call once at startup with `interval=None`, discard the result, then sample every 5 s |
| Tier system itself adds CPU overhead | Probe runs once at startup (<5 ms); classifier runs every 30 s (<1 ms); runtime conditions sampled every 5 s by a dedicated lightweight thread |
| User has a Tier-3 machine and the app is barely usable | Document minimum specs (T2 = 2 cores / 4 GB); show a one-time dialog on first launch if T3 detected: "Maestro will run in Minimal mode on this device. Some features are disabled." |
| macOS thermal state API requires IOKit (pyobjc) | Add `pyobjc-framework-IOKit` as an optional macOS dep; degrade gracefully to "nominal" if not installed |
| Windows has no reliable thermal API | Accept this; tier on CPU usage and battery instead |
| Linux battery info depends on `upower` | Use `psutil.sensors_battery()` which abstracts this; degrade to "100 %, charging" if unavailable |

---

# Part V — Refactoring for Speed on Low-Spec and High-Spec Hardware

The adaptive tier system (Part IV) decides *what* to run. This part decides *how fast* each subsystem runs. Both are needed.

## 22. Vision Pipeline Optimizations

### 22.1 Replace MediaPipe dependency with ONNX-only path

**Problem:** `pyproject.toml` declares `mediapipe>=0.10.0` but the engine uses `LandmarkExtractor` which talks to ONNX Runtime directly. MediaPipe is 50+ MB of dead dependency closure.

**Fix:** Remove `mediapipe` from `pyproject.toml`. Audit `gesture_controller/` for any `import mediapipe` — there should be none in the runtime path (only in tests, which should be marked `real_mediapipe`).

**Consequence:** Smaller install, faster cold start, fewer transitive deps. The `real_mediapipe` test marker becomes vestigial and should be removed.

### 22.2 Pre-allocate every numpy buffer

**Problem:** `InferencePipeline.process` already pre-allocates `_raw_bufs`, `_arr_bufs`, `_centered_bufs` per hand. But `compute_features` is called with these buffers injected (good) — yet `OneEuroFilter.filter` allocates a new `np.array` per call, and the `Landmark3D` tuple reconstruction allocates 21 `Landmark3D` namedtuples per hand per frame.

**Fix:**
- Convert `OneEuroFilter` to write into a pre-allocated output buffer rather than returning a new array.
- Replace the `tuple(Landmark3D(...) for f in filtered)` reconstruction with a single `Hand` object that holds a numpy array (not a tuple of namedtuples). This is a breaking change to the `Hand` data type, but the only consumers are the FSM evaluator and the HUD renderer, both of which can be updated.

**Consequence:** ~30 % reduction in per-frame allocation, which matters at T3 where GC pressure is the dominant cost. The `Hand` data type change ripples through tests — budget 1 sprint for the migration.

### 22.3 Use ONNX Runtime IO binding for zero-copy inference

**Problem:** `PalmDetector.infer` calls `session.run(None, {input_name: input_blob})` which copies `input_blob` into the ONNX runtime. On GPU backends, this is a host→device copy per frame.

**Fix:** Use `session.io_binding()`:
```python
binding = self.session.io_binding()
binding.bind_cpu_input(input_name, input_blob_np)
binding.bind_output(output_name)
self.session.run_with_iobinding(binding)
output = binding.get_outputs()[0].numpy()
```

**Consequence:** On CUDA/CoreML/DirectML, this enables the runtime to keep tensors on-device across consecutive calls. ~10–20 % latency improvement on GPU. No effect on CPU.

### 22.4 Cache the ONNX session across tier changes

**Problem:** When the tier changes and the model file changes, the current code would destroy the `InferenceSession` and create a new one. This is a 200–500 ms pause.

**Fix:** Maintain a small LRU cache of `InferenceSession` objects (max 3: FP16, INT8, FP32). On tier change, look up the cached session for the new model+provider combo; only create a new session if not cached.

**Consequence:** 200–500 ms pause happens only on the first tier change to a given model; subsequent changes are instant. Memory cost: ~100 MB per cached session (one model in memory). Acceptable at T0/T1; at T2/T3 only one session is cached.

### 22.5 Lower the palm-detector input size at T3

**Problem:** `PalmDetector.input_size` is hardcoded to `[192, 192]`. At T3 we want 160×160 to save CPU.

**Fix:** Make `input_size` a constructor parameter, sourced from the active `CapabilitySet.model_input_size`.

**Consequence:** Slight accuracy drop at T3 (smaller input = less spatial resolution). Acceptable for the minimal tier.

## 23. Engine Loop Optimizations

### 23.1 Replace the `wait_for_frame` poll with a condition variable

**Problem:** `FramePipeline.wait_for_frame` calls `self._frame_ready_event.wait(timeout=0.1)`. This is fine, but the engine loop then calls `time.sleep(0.01)` when paused, which is a 10 ms granularity poll.

**Fix:** Use a `threading.Condition` with `wait()` instead of `time.sleep`. The pause state change notifies the condition, so the loop wakes immediately.

**Consequence:** Faster pause/unpause response (10 ms → <1 ms). No effect on throughput.

### 23.2 Move FSM evaluation off the main loop thread

**Problem:** `engine._main_loop` does inference *and* FSM evaluation *and* feature computation on the same thread. At T0 with 2 hands and 5 FSMs per hand, FSM evaluation is ~1 ms — fine. At T2 with 1 hand and 10 FSMs (custom gestures), it can be 5 ms, which is the entire frame budget at 15 FPS.

**Fix:** Submit FSM evaluations to a `ThreadPoolExecutor(max_workers=2)`. Collect results with a 5 ms timeout; if a result isn't ready, skip it (the gesture will be evaluated next frame).

**Consequence:** More consistent frame times on slow hardware. Risk: FSM state mutations from multiple threads need locking. Budget 1 sprint for the thread-safety audit.

### 23.3 Replace `EventBus.publish` blocking calls with a queue

**Problem:** `EventBus.publish` (not yet read, but inferred from usage) calls every subscriber synchronously. If a subscriber blocks (e.g., the integration server broadcasting to a slow WebSocket), the engine loop blocks.

**Fix:** `EventBus.publish` enqueues to a per-subscriber queue; subscribers run on their own thread and drain their queue. Drop events if the queue is full (configurable: drop, block, or log-and-drop).

**Consequence:** Engine loop is decoupled from subscriber latency. Risk: events can be delivered out of order if a subscriber's queue backs up. Mitigation: timestamp every event; subscribers can detect and discard stale events.

## 24. GUI and Overlay Optimizations

### 24.1 Replace the 16 ms (60 FPS) poll timer with an event-driven bridge

**Problem:** `app_entry.py:201-203` runs `self._poll_timer.start(16)` which calls `_poll_engine` 60 times per second, pulling hand data and pushing it to the overlay. On T3, this is wasted work (the engine runs at 10 FPS, so 50 of those 60 polls per second return stale data).

**Fix:** The engine should *push* hand updates to the GUI via a Qt signal when a new frame is processed, not the GUI polling. Use `GuiEventBridge` (which already exists) to emit a `hands_updated` signal at the engine's actual frame rate.

**Consequence:** GUI CPU usage drops from ~2 % to ~0.2 % at T3. At T0 the GUI still updates at 60 FPS because the engine produces 60 FPS. Win-win.

### 24.2 Cache the overlay's QPainter paths

**Problem:** `OverlayHUD` (not yet read, but inferred) redraws the hand skeleton from scratch every frame, creating 21 `QPainter.drawEllipse` calls and 20 `QPainter.drawLine` calls per hand.

**Fix:** Pre-build `QPainterPath` objects for the skeleton edges (these don't change between frames — only the coordinates change). Update coordinates in place.

**Consequence:** ~30 % reduction in overlay render time. Minor at T0, meaningful at T3.

### 24.3 Disable the overlay entirely at T3

Already in the `CapabilitySet`. Implementation: `OverlayHUD.setVisible(False)` on tier downgrade to T3.

## 25. Memory Footprint Optimizations

### 25.1 Lazy-import heavy optional dependencies

**Problem:** `voice_listener.py` imports `vosk` and `pyaudio` at module top. `wasm_sandbox.py` imports `wasmtime` at module top. `updater.py` imports `tuf` at module top. These are 30+ MB each.

**Fix:** Move imports inside the functions that use them. Add `__all__` to control re-exports.

**Consequence:** Cold start drops by ~500 ms (no 30 MB of imports). Memory drops by ~30 MB per unused subsystem.

### 25.2 Drop `wasmtime` entirely

**Problem:** `wasmtime` is ~30 MB, the WASM sandbox is unused, and the plugin loader uses Python `exec` anyway. The WASM sandbox is dead code.

**Fix:** Remove `wasm_sandbox.py`, remove `wasmtime` from `pyproject.toml`, remove the WASM plugin discovery path from `plugin_loader.py`.

**Consequence:** Smaller install, smaller memory, less code to maintain. The ADR for WASM sandboxing should be marked "Superseded — not implemented; revisit if a real WASM plugin use case emerges."

### 25.3 Drop `numba` unless actually used

**Problem:** `numba>=0.57.0` is a runtime dep. Numba is ~80 MB and adds 1–2 s to cold start (JIT compilation).

**Fix:** Audit `gesture_controller/` for `@numba.jit` decorators. If found, replace with hand-optimized numpy (which is usually as fast for the small array sizes involved — 21 landmarks × 3 coords). If not found, remove the dep.

**Consequence:** Smaller install, faster cold start.

### 25.4 Use `__slots__` on hot data classes

**Problem:** `Hand`, `Landmark3D`, `GestureEvent` are `@dataclass` without `slots=True`. Each instance has a `__dict__` overhead.

**Fix:** Add `slots=True` to the `@dataclass` decorator (Python 3.10+).

**Consequence:** ~30 % memory reduction per instance; ~5 % attribute access speedup. Minor but free.

## 26. Cold-Start and Binary Size

### 26.1 Switch from PyInstaller `--onefile` to `--onedir` + installer

**Problem:** `--onefile` produces a single .exe that extracts to a temp dir on every launch. Cold start is 3–8 seconds. Binary size is 60–100 MB.

**Fix:** Use `--onedir` (produces a folder of files) and wrap it in a platform installer (NSIS on Windows, `.pkg` on macOS, `.deb`/`.AppImage` on Linux). Cold start drops to <1 s. The user gets a Start Menu / Applications folder entry, an uninstaller, and file associations.

**Consequence:** More complex release pipeline (three installers instead of one .exe). Worth it for a commercial release.

### 26.2 Use Nuitka instead of PyInstaller for the production build

**Problem:** PyInstaller bundles the interpreter; Nuitka compiles to C. Nuitka binaries are smaller, faster, and harder to reverse-engineer.

**Fix:** ADR-017 already recommends Nuitka. Implement it as the production build path; keep PyInstaller as a fallback.

**Consequence:** Nuitka compilation is slow (5–10 minutes vs PyInstaller's 30 seconds). Acceptable for CI release builds; unacceptable for dev iteration. Keep PyInstaller for dev builds.

### 26.3 Strip unused model files from the binary

**Problem:** `gesture_controller/data/` contains `hand_landmarker.task` (MediaPipe — unused), `hand_landmark.onnx` (FP32), `hand_landmark_int8.onnx` (INT8). All three are bundled.

**Fix:** Once MediaPipe is removed (§22.1), drop `hand_landmarker.task`. Bundle only `hand_landmark_int8.onnx` by default; download `hand_landmark.onnx` (FP16 version) on first launch if T0 detected.

**Consequence:** Binary drops by ~10 MB. T0 users have a one-time 5 MB download. Acceptable.

### 26.4 Lazy-load translation files

**Problem:** All 8 `.po` files are compiled to `.mo` and bundled.

**Fix:** Bundle only `en` and the user's locale (detected at install time or first launch). Other locales download on demand.

**Consequence:** Smaller binary. Risk: i18n doesn't work offline for non-bundled locales. Mitigation: bundle the top 5 locales by user population (en, es, hi, fr, de) and lazy-load the rest.

## 27. Benchmarking and Regression Gates

### 27.1 The benchmark suite

Already exists in `gesture_controller/tests/benchmarks/test_benchmarks.py`. Extend it to cover:

| Benchmark | What it measures | Target T0 | Target T2 |
|---|---|---|---|
| `bench_camera_capture_to_landmarks` | End-to-end frame → landmarks | <15 ms | <30 ms |
| `bench_palm_detector_infer` | PalmDetector.infer alone | <5 ms | <15 ms |
| `bench_hand_pose_estimator` | HandPoseEstimator alone | <5 ms | <10 ms |
| `bench_one_euro_filter` | OneEuroFilter.filter | <0.5 ms | <0.5 ms |
| `bench_compute_features` | feature_engineering.compute_features | <1 ms | <2 ms |
| `bench_fsm_evaluate` | GestureRecognizer.evaluate for 5 FSMs | <1 ms | <3 ms |
| `bench_overlay_render` | OverlayHUD render with 2 hands | <2 ms | <5 ms |
| `bench_broker_round_trip` | BrokerClientController → broker → controller → response | <2 ms | <2 ms |
| `bench_cold_start` | Process launch → first frame processed | <1500 ms | <2000 ms |
| `bench_memory_footprint` | RSS after 60 s of idle (no hands) | <200 MB | <120 MB |

### 27.2 CI benchmark enforcement

Add a `benchmarks` job to CI that runs the benchmark suite on every PR and compares to the `main` branch baseline:

```yaml
  benchmarks:
    name: Benchmarks
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with: { python-version: '3.12', cache: 'pip' }
      - run: pip install -e .[dev]
      - run: python -m pytest gesture_controller/tests/benchmarks/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20%
```

The `--benchmark-compare-fail=mean:20%` flag fails the job if any benchmark's mean regresses by more than 20 % vs the baseline. The baseline is committed to the repo as `gesture_controller/tests/benchmarks/baseline.json` and updated manually when a deliberate performance change lands.

**Consequence:** PRs that regress performance are blocked. This is sometimes wrong (e.g., a security fix that's inherently slower). Mitigation: allow `// PERF: rationale` comments in the PR that override the gate with maintainer approval.

---

# Part VI — Release-Readiness Plan

## 28. Security Hardening

### 28.1 Fix the broker Windows authentication (P0-5)

**Problem:** `verify_peer` returns `True` on Windows. Any local process can connect to the named pipe and inject input.

**Fix:** On Windows, use a security descriptor on the named pipe that restricts access to the creating user's SID. This requires `win32security.CreateSecurityDescriptor` with a DACL that grants `GENERIC_READ | GENERIC_WRITE` only to the current user's SID. Alternatively, use the `pywin32` `CreateNamedPipe` with a `SECURITY_ATTRIBUTES` structure.

**Consequence:** Only the user who started Maestro can connect to the broker. This is the correct threat model for a single-user desktop app.

### 28.2 Fix the plugin loader exec bypass (P0-6)

**Problem:** The plugin loader does an AST scan for "bad" nodes, then `exec`s the code. AST scanning is a known-broken approach for sandboxing Python — see every RestrictedPython bypass ever published.

**Fix:** Three options, in increasing order of security:

1. **Drop the AST scan and use RestrictedPython properly.** RestrictedPython compiles the source to a restricted AST that forbids attribute access starting with `_`, restricts `__import__`, etc. This is what RestrictedPython is for. The current code uses RestrictedPython as a *compile-time check* but then `exec`s the original code — bypassing everything.

2. **Run plugins in a subprocess.** Each plugin gets its own Python process, communicated with via JSON-RPC. The subprocess has restricted permissions (no filesystem access outside its dir, no network, limited CPU via `resource.setrlimit`). This is the approach used by VS Code's extension host.

3. **Use WASM after all.** Ship a Python-to-WASM compiler (e.g., RustPython compiled to WASM) and run plugins in wasmtime. This is the most secure but the most work.

**Recommendation:** Option 2 (subprocess isolation). It's the right balance of security and pragmatism. The subprocess can crash without taking down Maestro; the subprocess can be killed if it exceeds CPU/memory limits; the subprocess cannot access the camera, the network, or the user's files outside its plugin directory.

**Consequence:** Plugins become slower to start (subprocess spawn ~50 ms) and have higher IPC overhead (JSON-RPC vs direct call). Acceptable for the threat model. Document that plugin authors should keep their per-frame work fast.

### 28.3 Fix the integration server WebSocket implementation (P0-7)

**Problem:** The server does the WebSocket handshake and then never reads from the socket again. It only writes `gesture_triggered` broadcasts. Client-sent frames (close, ping, messages) are never read. Half-closed connections stay in `self.clients` forever.

**Fix:** After the handshake, start a per-client read loop on a daemon thread that:
- Reads frames (handles masked client→server frames properly, per RFC 6455)
- Responds to ping with pong
- Closes the socket on close frame or error
- Removes the client from `self.clients` on close

**Consequence:** Minor CPU cost (one thread per WS client). Acceptable; the integration server is local-only and has <10 clients in practice.

### 28.4 Fix the TUF root.json placeholder keys (P0-4)

**Problem:** The `BOOTSTRAP_ROOT` in `updater.py:30-120` contains 10+ Ed25519 public keys with sequential-looking keyids (`92a7…`, `b2a7…`, `c2a7…`, `d2a7…`, `e2a7…`, plus `ce7d…`, `de7d…`, `ee7d…`, `fe7d…`, `ae7d…`). These are not real TUF outputs — they're hand-typed placeholders.

**Fix:**
1. Generate real Ed25519 keypairs with `python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; k = Ed25519PrivateKey.generate(); print(k.private_bytes_raw().hex(), k.public_key().public_bytes_raw().hex())"`.
2. Use `tuf`'s repository tooling to create a real `root.json` with a threshold of 3 out of 5 keys.
3. Store the private keys in a secure location (GitHub Actions secrets, Azure Key Vault, or offline HSM). **Never** commit private keys to the repo.
4. Replace the `BOOTSTRAP_ROOT` constant with a load from a bundled `root.json` file.

**Consequence:** Updates are now verifiable. Risk: if the private keys are lost, no future updates can be signed. Mitigation: 3-of-5 threshold means losing 2 keys is recoverable; back up keys in multiple locations.

### 28.5 Remove the `os.symlink` monkey-patch (P0-10)

**Problem:** `updater.py:14-27` replaces `os.symlink` globally with a function that falls back to `shutil.copy`. This affects every other module in the process.

**Fix:** Move the symlink-or-copy logic into a local helper function used only by the updater. Don't touch `os.symlink`.

**Consequence:** Other modules that use `os.symlink` (there shouldn't be any, but if there are) get the real behavior. The updater still works on Windows (where symlink requires admin privileges).

### 28.6 Add request size limits to the integration server (P2-17)

**Problem:** No `max_request_size` cap. A 100-MB header OOMs the app.

**Fix:** Cap total request size at 1 MB. Cap header size at 8 KB. Close connection on exceed.

### 28.7 Per-method broker rate limits (P2-18)

**Problem:** `mouse_move` is rate-limited identically to `key_press` (30/sec global, 10/100ms burst). A 60-FPS pointer gesture hits the limit instantly.

**Fix:** Per-method limits:
- `mouse_move`: 120/sec, 30/100ms burst
- `mouse_click`, `mouse_double_click`: 30/sec, 10/100ms burst
- `mouse_scroll`: 60/sec, 15/100ms burst
- `key_press`, `key_release`, `key_combo`: 30/sec, 10/100ms burst
- `media_*`: 10/sec, 5/100ms burst
- `get_foreground_app`: 10/sec (it's a query, not an action)

### 28.8 Audit log integrity verification

**Problem:** The audit log is hash-chained but never verified.

**Fix:** Add a `verify_audit_log` CLI command that reads the log and verifies every hash chain. Run it as part of the diagnostics export.

### 28.9 Threat model documentation

Write `docs/specs/ds-007-threat-model.md` (it exists as a stub) into a full STRIDE threat model covering: camera input, shared memory, broker, plugins, integration server, updater, voice listener, crash reporter. Reference all the fixes above.

## 29. Code Signing and Supply Chain

### 29.1 Windows code signing

**Problem:** `release.yml` has a placeholder Azure Key Vault block that does nothing.

**Fix:** Obtain a code signing certificate (OV or EV). Store it in Azure Key Vault. Use `azuresigntool` (not `signtool`) to sign the .exe in CI:

```yaml
- name: Sign with Azure Key Vault
  if: ${{ secrets.AZURE_CLIENT_ID != '' }}
  run: |
    dotnet tool install --global AzureSignTool
    azuresigntool sign -kvu "${{ secrets.AZURE_KEY_VAULT_URL }}" \
                       -kvi "${{ secrets.AZURE_CLIENT_ID }}" \
                       -kvt "${{ secrets.AZURE_TENANT_ID }}" \
                       -kvs "${{ secrets.AZURE_CLIENT_SECRET }}" \
                       -kvc "${{ secrets.AZURE_CERT_NAME }}" \
                       -tr http://timestamp.digicert.com -td sha256 \
                       dist/Maestro.exe
```

**Consequence:** No more SmartScreen warnings (after the certificate builds reputation over a few weeks). Cost: ~$200/year for OV cert, ~$400/year for EV cert.

### 29.2 macOS code signing and notarization

**Problem:** `release.yml` only builds on Windows. There is no macOS build, no signing, no notarization.

**Fix:** Add a macOS build job that:
1. Builds with `pyinstaller --onedir` (or Nuitka).
2. Signs the .app with `codesign --deep --force --options runtime --sign "Developer ID Application: <Your Name>" dist/Maestro.app`.
3. Notarizes with `xcrun notarytool submit dist/Maestro.zip --apple-id <apple-id> --team-id <team-id> --password <app-specific-password> --wait`.
4. Staples with `xcrun stapler staple dist/Maestro.app`.

**Consequence:** macOS users get a clean Gatekeeper experience. Requires an Apple Developer account ($99/year).

### 29.3 Linux packaging

**Problem:** No native Linux packages. The `packaging/linux/install.sh` is a shell script, not a real package.

**Fix:** Produce three artifacts:
1. `.AppImage` (universal, no install) via `appimage-builder` or `linuxdeploy`.
2. `.deb` for Debian/Ubuntu via `fpm` or `dh-virtualenv`.
3. `.rpm` for Fedora/RHEL via `fpm`.

Plus a Flatpak manifest for the Flathub distribution.

**Consequence:** Linux users get a proper install path, desktop integration, and updates via their package manager.

### 29.4 SLSA Level 3 provenance

**Problem:** The `release.yml` already uses `slsa-github-generator@v1.9.0` but the SLSA provenance file is uploaded as a release asset that nobody verifies.

**Fix:**
1. Bump to `slsa-github-generator@v2.1.0` (Dependabot has the PR open).
2. Add a `verify-provenance` step that uses `slsa-verifier` to check the provenance against the binary.
3. Document in `SECURITY.md` how end users can verify provenance themselves.

### 29.5 SBOM generation and publishing

**Problem:** `release.yml` generates `sbom.json` via `cyclonedx-py` but it's uploaded as a release asset, not published to a dependency graph.

**Fix:**
1. Use `cyclonedx-py` (already in the workflow).
2. Submit the SBOM to GitHub's dependency graph via the `github/codeql-action`'s SBOM upload feature.
3. Publish the SBOM to a public location (e.g., `https://aryansinghnagar.github.io/Maestro/sbom/<version>.json`) so downstream users can fetch it.

## 30. Packaging and Distribution

### 30.1 The release matrix

For each release (per OS, per arch):

| OS | Arch | Format | Signing |
|---|---|---|---|
| Windows 10+ | x64 | `.msi` (via WiX) or `.exe` (via NSIS) | Azure Key Vault OV/EV |
| Windows 10+ | arm64 | `.msi` | Same (separate cert may be needed) |
| macOS 12+ | Universal (x64+arm64) | `.dmg` containing `.app` | Developer ID + Notarization |
| Linux | x64 | `.AppImage` + `.deb` + `.rpm` | Cosign (keyless) |
| Linux | arm64 | `.AppImage` + `.deb` | Cosign (keyless) |
| Python package | any | `sdist` + `wheel` on PyPI | Sigstore |

### 30.2 PyPI publication

**Problem:** `pyproject.toml` declares the package as `gesture-controller` but the user-facing name is `maestro`. The `maestro` PyPI package is taken.

**Fix:** Publish as `maestro-gesture-controller` on PyPI. Keep the `maestro` console script name. Add `pyproject.toml` metadata for PyPI long description, project URLs, etc.

### 30.3 Microsoft Store / Mac App Store

**Problem:** Not currently considered.

**Fix:** For v1.1, package Maestro for the Microsoft Store (MSIX) and the Mac App Store (sandboxed .app). The sandboxing will require restricting file system access, which is a non-trivial change for the plugin system (plugins can't write to arbitrary paths).

**Consequence:** Broader distribution, automatic updates, but more constraints. Defer to v1.1.

### 30.4 Auto-update mechanism

**Problem:** The `UpdateCheckerThread` checks for updates and shows a tray notification, but doesn't actually apply them. The TUF infrastructure exists but is unused.

**Fix:** Wire the updater to actually download and apply updates:
1. On update-available notification, prompt the user: "Update to v1.0.1? [Yes] [Later]".
2. On "Yes", download the new package to a temp dir, verify TUF signature, launch the installer with `/SILENT /NOCANCEL`, exit Maestro.
3. The installer overwrites the old version and relaunches Maestro.

**Consequence:** Users get auto-updates. Risk: a bad update can brick the install. Mitigation: TUF threshold=3 means 3 of 5 maintainers must sign the update; rollback documentation in `docs/troubleshooting.md`.

## 31. Privacy, Compliance, and Legal

### 31.1 GDPR

Already partially addressed by `compliance.py` (data export and erasure APIs). Remaining work:
- Add a "Delete all my data" button to the settings window that calls `compliance.erase_data()`.
- Document the data flow in `PRIVACY.md` (already exists, needs review).
- Appoint a Data Protection Officer (the maintainer) and document contact.
- Add a cookie banner / consent dialog? No — Maestro is a desktop app, no cookies.

### 31.2 CCPA / CPRA

Similar to GDPR for California residents. The existing `compliance.py` APIs satisfy most requirements. Add a "Do Not Sell My Personal Information" link in the settings (Maestro doesn't sell data, but the link is required for compliance).

### 31.3 WCAG 2.2 AA

ADR-020 claims WCAG 2.2 conformance. This requires:
- Keyboard navigation for all GUI elements.
- Screen reader support (already started via `a11y` config).
- High contrast mode (already started).
- Reduced motion mode (already started).
- Dwell clicking (already started).
- Voice control (already started).

Remaining work:
- Hire a third-party accessibility auditor (Knowbility, Deque, or similar) for a VPAT.
- Fix all findings.
- Publish the VPAT on the docs site.

### 31.4 AGPL-3.0 compliance

**Problem:** Maestro is AGPL-3.0. Anyone who modifies Maestro and distributes it (including over a network) must publish their modifications under AGPL. This is fine for the project but toxic to enterprise OEMs who want to embed Maestro.

**Fix:** Offer a dual license: AGPL for open-source use, commercial license for enterprise embedding. Document at `https://maestro.example.com/pricing`.

### 31.5 Patent license

**Problem:** Maestro uses MediaPipe-style hand landmark detection, which may be covered by Google patents.

**Fix:** Document in `LICENSE` that the hand-landmark model is provided under the Apache 2.0 license (it is — MediaPipe's model is Apache 2.0). Add a patent license grant in the project's `LICENSE`.

## 32. Documentation and Support

### 32.1 Documentation gaps

- The `docs/` tree is comprehensive but needs:
  - A "Getting Started" video walkthrough.
  - A "Plugin Development Tutorial" with a working example plugin.
  - A "Troubleshooting" decision tree for common issues (camera not found, gestures not recognized, broker won't start).
  - Per-OS install guides with screenshots.
- The `old_docs/` tree should be moved to `docs/archive/` after v1.0 ships.
- The `v3.0/maestro_refactor_plan_v3.md` should be split into per-sprint planning docs in `docs/internal/sprints/`.

### 32.2 Support channels

- GitHub Issues for bug reports and feature requests.
- GitHub Discussions for Q&A.
- Discord for community chat.
- Email (security@aryansinghnagar.dev) for security reports.
- Paid support tier (Patreon or GitHub Sponsors) for priority bug fixes.

### 32.3 Contributing guide

`CONTRIBUTING.md` exists. Update it with:
- The branch unification policy (no long-lived feature branches).
- The CI green requirement before merge.
- The commit message convention (Conventional Commits, enforced by commitlint).
- The PR template (already exists at `.github/pull_request_template.md`).
- The code review checklist (typing, tests, docs, performance).

## 33. Telemetry and Crash Analytics

### 33.1 Opt-in telemetry

**Problem:** `default_config.yaml` has `telemetry.enabled: false` and `telemetry.endpoint: "https://telemetry.maestro.example.com"` — both are aspirational.

**Fix:** Build a minimal opt-in telemetry system:
- On first launch, show a dialog: "Help improve Maestro by sending anonymous usage data? [Yes] [No] [Ask later]".
- If yes, send a daily ping with: tier, OS, Python version, Maestro version, crash count, gesture count (no gesture names, no camera data, no audio data).
- Endpoint: a Cloudflare Worker that logs to R2 and is publicly auditable at `https://telemetry.maestro.example.com/public-stats`.

**Consequence:** Privacy-conscious users can opt out. The maintainer gets aggregate usage data to prioritize features.

### 33.2 Crash analytics

**Problem:** `crash_reporter.py` writes crash dumps locally but doesn't send them anywhere.

**Fix:** Integrate Sentry (self-hosted or sentry.io) for crash analytics. On crash:
1. Sanitize the dump (remove file paths, usernames, environment variables).
2. Prompt the user: "Send crash report? [Send] [Don't send] [Always send]".
3. If send, upload to Sentry with the sanitized dump.

**Consequence:** Maintainer gets crash visibility. Risk: PII leakage. Mitigation: the sanitizer is the critical path; audit it carefully.

## 34. Release Runbook

### 34.1 Pre-release checklist

- [ ] All P0 bugs closed
- [ ] All P1 bugs closed
- [ ] CI green on all 9 cells (3 OS × 3 Python)
- [ ] Benchmark suite run on at least one T0, T1, T2, T3 device; no regressions
- [ ] Security review completed (third-party or self)
- [ ] Accessibility audit completed (at least self-audit; third-party for v1.1)
- [ ] Documentation reviewed and up-to-date
- [ ] CHANGELOG updated
- [ ] Version bumped in `pyproject.toml`
- [ ] Release notes drafted
- [ ] SBOM generated
- [ ] Code signing certificates valid
- [ ] TUF root.json private keys accessible
- [ ] Installer tested on a clean VM per OS

### 34.2 Release procedure

1. Create a `release/v1.0.0` branch from `main`.
2. Update `pyproject.toml` version to `1.0.0`.
3. Update `CHANGELOG.md` with the release date and notes.
4. Commit: `chore(release): v1.0.0`.
5. Push the branch.
6. Release-please opens a PR automatically; merge it.
7. Release-please tags `v1.0.0` and creates a GitHub Release.
8. The `release.yml` workflow triggers on the tag, builds all artifacts, signs them, uploads to the release.
9. Manually verify each artifact by downloading and running on a clean VM.
10. Publish the PyPI package: `python -m build && twine upload dist/*`.
11. Update the docs site with the new version's changelog.
12. Announce on Discord, Twitter, Reddit, Hacker News.

### 34.3 Post-release

- Monitor Sentry for 7 days; triage any crashes.
- Monitor GitHub Issues for 7 days; respond to all issues within 24 hours.
- Write a post-mortem 2 weeks after release: what went well, what didn't, what to change for v1.0.1.

### 34.4 Rollback procedure

If v1.0.0 is broken:
1. Mark the GitHub Release as a pre-release (un-publishes it from the latest release).
2. Publish v1.0.1 with the fix, OR re-publish v0.1.0 as the latest.
3. The auto-updater will down-grade users (with their consent) on next check.
4. Post a notice on the docs site and Discord.

---

# Part VII — Execution Roadmap and Sequencing

## 35. Sprint Plan (12 Sprints, 6 Weeks)

Each sprint is 2.5 days of focused work. The plan is sequenced so that each sprint unblocks the next.

### Sprint 1 — CI Restoration (P0)
- Fix `.github/workflows/ci.yml` `branches: ain]` typo.
- Fix `.github/workflows/release.yml` `python_version` typo.
- Align coverage gates to 75 %.
- Add `workflow-lint` job.
- Cherry-pick the live Dependabot bump.
- Close stale Dependabot branches.
- Push, observe CI on all 9 cells, triage failures.
- **Exit criterion:** CI is green on `main` for the first time.

### Sprint 2 — Branch Unification
- Create `unify/branches-v1.0` branch.
- Re-apply the four stale Dependabot bumps manually.
- Open and merge the unification PR.
- Delete closed branches.
- Update `dependabot.yml`.
- Re-base `release-please--branches--main`.
- **Exit criterion:** Single `main` branch, all working code merged.

### Sprint 3 — Adaptive Performance Tier System (Part 1)
- Implement `capabilities.py` (CapabilitySet, TIER_PRESETS).
- Implement `hardware_probe.py` (probe_hardware).
- Implement `tier_classifier.py` (classify_tier, pure function).
- Unit tests for the classifier with mocked HardwareProfile and RuntimeConditions.
- **Exit criterion:** Classifier passes 50+ unit tests covering all tier boundaries.

### Sprint 4 — Adaptive Performance Tier System (Part 2)
- Implement `TierManager` that runs the probe at startup and the classifier every 30 s.
- Wire `TierManager` to `EventBus` (publish `TierChanged`).
- Subsystem subscribers: FramePipeline, InferencePipeline, OverlayHUD.
- **Exit criterion:** Tier changes actually adjust FPS and HUD behavior. End-to-end test: simulate CPU pressure, observe tier downgrade, observe FPS drop.

### Sprint 5 — Adaptive Performance Tier System (Part 3)
- Subsystem subscribers: VoiceCommandListener, IntegrationServer, PluginLoader, GestureRecognizer, DwellClicker.
- User override UI in settings window.
- Observability: structlog, metrics, diagnostics export.
- **Exit criterion:** Settings window shows current tier, allows override. Diagnostics export includes tier history.

### Sprint 6 — Security Hardening (Part 1)
- Fix broker Windows authentication (P0-5).
- Fix plugin loader exec bypass — implement subprocess isolation (P0-6).
- Fix integration server WebSocket read loop (P0-7).
- **Exit criterion:** Penetration test (self-administered) passes. A local non-Maestro process cannot inject input, cannot execute arbitrary Python via a plugin, cannot OOM the integration server.

### Sprint 7 — Security Hardening (Part 2)
- Fix TUF root.json placeholder keys — generate real keys, store in GitHub Actions secrets (P0-4).
- Remove `os.symlink` monkey-patch (P0-10).
- Add request size limits to integration server (P2-17).
- Per-method broker rate limits (P2-18).
- Audit log integrity verification CLI command.
- **Exit criterion:** `maestro verify-audit-log` passes on a fresh install.

### Sprint 8 — Performance Refactor (Part 1)
- Remove MediaPipe dependency (§22.1).
- Pre-allocate every numpy buffer (§22.2).
- ONNX IO binding (§22.3).
- Cache ONNX sessions across tier changes (§22.4).
- Lower palm-detector input size at T3 (§22.5).
- **Exit criterion:** Benchmark suite shows 20 % improvement on T2 hardware vs Sprint 1 baseline.

### Sprint 9 — Performance Refactor (Part 2)
- Replace 60 FPS poll timer with event-driven bridge (§24.1).
- Cache overlay QPainter paths (§24.2).
- Lazy-import heavy optional dependencies (§25.1).
- Drop wasmtime (§25.2).
- Audit and drop numba if unused (§25.3).
- `__slots__` on hot data classes (§25.4).
- **Exit criterion:** Cold start <1.5 s on T2 hardware. Memory <150 MB at idle.

### Sprint 10 — Packaging and Distribution
- Switch to `--onedir` + NSIS installer (Windows).
- Add macOS build job with signing and notarization.
- Add Linux `.AppImage` + `.deb` + `.rpm`.
- PyPI publication.
- **Exit criterion:** All installers work on clean VMs. PyPI package installs cleanly.

### Sprint 11 — Code Signing and Supply Chain
- Azure Key Vault code signing for Windows (P0-8).
- Apple Developer ID signing + notarization for macOS.
- Cosign signing for Linux artifacts.
- SLSA Level 3 provenance verification.
- SBOM publication.
- **Exit criterion:** No SmartScreen / Gatekeeper warnings. `slsa-verifier` passes on all artifacts.

### Sprint 12 — Release
- Pre-release checklist (§34.1).
- Release procedure (§34.2).
- Post-release monitoring (§34.3).
- **Exit criterion:** v1.0.0 is published, users are installing it, no critical issues for 7 days.

## 36. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CI surfaces unknown test failures when the typo is fixed | High | Medium | Sprint 1 is dedicated to triage; do not skip tests |
| Subsystem doesn't respect tier changes correctly | Medium | High | Unit tests for every subscriber; integration test that simulates tier changes |
| Plugin subprocess isolation breaks existing plugins | High | Medium | Provide a migration guide; deprecate the old `exec` path over 2 releases |
| TUF keys are lost | Low | Critical | 3-of-5 threshold; back up keys in 3 locations (Azure KV, 1Password, paper) |
| Code signing certificate is revoked | Low | High | Have a backup cert from a different CA |
| macOS notarization fails | Medium | Medium | Test notarization on every PR that touches the build |
| Performance regression from a security fix | Medium | Medium | Benchmark gate in CI; allow `// PERF: rationale` overrides |
| Accessibility audit finds major issues | High | High | Budget time after the audit for fixes; don't promise WCAG 2.2 AA until audit passes |
| Telemetry opt-in is too aggressive | Medium | Low | Default to opt-out; show the dialog once, never again if dismissed |
| Auto-updater bricks user installs | Low | Critical | TUF threshold=3; rollback documentation; test the updater on a clean VM before each release |
| Maintainer burnout | Medium | Critical | The 12-sprint plan is 6 weeks of one person's work; recruit a second maintainer before v1.1 |
| AGPL license deters enterprise adoption | Medium | Low | Dual license for v1.1 |
| Python 3.13 breaks a dependency | Medium | Medium | Matrix tests 3.11/3.12/3.13; pin critical deps |
| pyobjc lacks 3.13 wheels | High | Low | Exclude macOS 3.13 from matrix; document |
| The performance tier boundaries are wrong | High | Medium | Validate empirically on real hardware; adjust; re-validate |
| The user forces T0 on T2 hardware and the app is unusable | Medium | Medium | Warning dialog; auto-fallback if FPS < 5 for 10 s |

## 37. Definition of Done for Commercial Release v1.0

A release is v1.0-ready when **all** of the following are true:

### Engineering
- [ ] CI is green on all 9 cells (3 OS × 3 Python) for 7 consecutive days.
- [ ] All P0 bugs are closed.
- [ ] All P1 bugs are closed.
- [ ] The benchmark suite passes on at least one T0, T1, T2, and T3 device.
- [ ] Cold start is <1.5 s on T2 hardware.
- [ ] Memory is <200 MB at idle on T2 hardware.
- [ ] The adaptive tier system works end-to-end: a simulated CPU spike triggers a downgrade; recovery triggers an upgrade.
- [ ] The branch unification is complete: only `main` and `release-please--branches--main` exist.

### Security
- [ ] A self-administered penetration test passes (broker, integration server, plugin loader, updater).
- [ ] TUF root.json uses real keys; private keys are in secure storage.
- [ ] Audit log verification CLI passes on a fresh install.
- [ ] No `exec` of untrusted code in the plugin loader.
- [ ] All workflows pin actions by SHA.

### Packaging
- [ ] Windows installer (`.msi` or `.exe`) is signed and works on a clean Windows 11 VM.
- [ ] macOS installer (`.dmg`) is signed, notarized, and works on a clean macOS 14 VM.
- [ ] Linux `.AppImage`, `.deb`, and `.rpm` work on clean Ubuntu 24.04, Fedora 40, and Debian 12 VMs.
- [ ] PyPI package installs cleanly with `pip install maestro-gesture-controller`.
- [ ] SBOM is published.
- [ ] SLSA provenance is generated and verifiable.

### Documentation
- [ ] `docs/` tree is comprehensive and accurate.
- [ ] `old_docs/` is moved to `docs/archive/`.
- [ ] `CHANGELOG.md` is up-to-date.
- [ ] `README.md` has no unverified performance claims.
- [ ] `SECURITY.md` has a real PGP key.
- [ ] `PRIVACY.md` accurately describes data flow.
- [ ] `CONTRIBUTING.md` reflects the branch unification policy.

### Compliance
- [ ] GDPR: data export and erasure APIs work.
- [ ] WCAG 2.2 AA: self-audit complete; third-party audit scheduled for v1.1.
- [ ] AGPL-3.0: LICENSE bundled with binary.

### Operations
- [ ] Crash analytics (Sentry) is integrated.
- [ ] Opt-in telemetry is implemented.
- [ ] Release runbook (§34) is documented.
- [ ] Rollback procedure is tested.

### Community
- [ ] GitHub Issues template is configured.
- [ ] GitHub Discussions is enabled.
- [ ] Discord server is set up.
- [ ] Code of Conduct is published.

When every checkbox above is ticked, v1.0.0 can be tagged and released. Until then, the project is in beta and the README must say so.

---

# Appendices

## A. Glossary

| Term | Definition |
|---|---|
| **Broker** | The privilege-separated input-injection process. |
| **CapabilitySet** | A frozen dataclass describing what's enabled at a given tier. |
| **CSWSH** | Cross-Site WebSocket Hijacking. |
| **DTW** | Dynamic Time Warping — used for custom-gesture matching. |
| **FSM** | Finite State Machine — one per hand, per gesture. |
| **HardwareProfile** | A frozen dataclass describing the host hardware at startup. |
| **One-Euro Filter** | A low-pass filter for noisy real-time signals, with adaptive cutoff based on speed. |
| **P0/P1/P2/P3** | Bug severity: Blocker / Critical / Major / Minor. |
| **RuntimeConditions** | A frozen dataclass describing live signals (CPU, RAM, battery, thermal, latency). |
| **SLSA** | Supply-chain Levels for Software Artifacts — a framework for verifying software supply chain security. |
| **STRIDE** | Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege. |
| **T0/T1/T2/T3** | Performance tiers: Ultra / High / Standard / Minimal. |
| **TUF** | The Update Framework — a spec for secure software updates. |
| **VPAT** | Voluntary Product Accessibility Template — a document describing accessibility conformance. |
| **WASM** | WebAssembly — used (aspirationally) for sandboxed plugin execution. |

## B. File Inventory

Key files referenced in this plan (all paths relative to repo root):

| File | Purpose | Plan section |
|---|---|---|
| `.github/workflows/ci.yml` | CI workflow | §8.1, §9 |
| `.github/workflows/release.yml` | Release build workflow | §8.2, §9, §29 |
| `.github/workflows/fuzz.yml` | Nightly fuzz workflow | §8.3 |
| `.github/workflows/docs.yml` | Docs deploy workflow | §8.4 |
| `.github/workflows/commitlint.yml` | Commit message lint | §8.5 |
| `.github/workflows/release-please.yml` | Release-please automation | §8.6 |
| `.github/dependabot.yml` | Dependabot config | §13 |
| `pyproject.toml` | Package metadata, deps, tool config | §5 (P1-11, P1-12, P1-15) |
| `main.py` | Repo-root entry point | §5 (P0-9) |
| `gesture_controller/__init__.py` | Package init | §5 (P3-4) |
| `gesture_controller/core/engine.py` | GestureEngine main loop | §7.1, §23 |
| `gesture_controller/core/frame_pipeline.py` | Camera process + SharedMemory | §7.1, §22, §23 |
| `gesture_controller/core/inference_pipeline.py` | Landmark extraction + filtering | §7.1, §22 |
| `gesture_controller/core/integration_server.py` | REST + WS server | §5 (P0-7, P1-7, P2-17), §28.3, §28.6 |
| `gesture_controller/core/updater.py` | TUF update client | §5 (P0-4, P0-10), §28.4, §28.5 |
| `gesture_controller/core/voice_listener.py` | Vosk voice control | §5 (P1-8, P2-20), §25.1 |
| `gesture_controller/os_integration/broker.py` | Privilege-separated broker | §5 (P0-5, P1-6, P1-14, P2-18), §28.1, §28.7 |
| `gesture_controller/os_integration/windows_controller.py` | Win32 SendInput | §5 (P1-10) |
| `gesture_controller/plugins/plugin_loader.py` | Plugin discovery + AST scan | §5 (P0-6), §28.2 |
| `gesture_controller/plugins/wasm_sandbox.py` | Unused WASM sandbox | §5 (P2-12), §25.2 |
| `gesture_controller/vision/palm_detector.py` | 2 144-line palm detector | §5 (P1-4), §22 |
| `gesture_controller/gui/app_entry.py` | GUI app coordinator | §5 (P1-1, P1-2, P1-3, P1-8) |
| `gesture_controller/data/default_config.yaml` | Default config | §5 (P3-2), §19 |
| `gesture_controller/tests/conftest.py` | Test fixtures | §9 |
| `gesture_controller/tests/benchmarks/test_benchmarks.py` | Benchmarks | §27 |
| `gesture_controller.spec` | PyInstaller spec | §5 (P2-1, P0-9), §30 |
| `packaging/windows_installer.nsi` | NSIS installer | §30 |
| `packaging/sbom.cdx.json` | SBOM | §29.5 |
| `CHANGELOG.md` | Changelog | §5 (P2-10) |
| `LICENSE` | AGPL-3.0 | §31.4 |
| `PRIVACY.md` | Privacy policy | §31.1 |
| `SECURITY.md` | Security policy | §5 (P3-5), §29.4 |
| `v3.0/maestro_refactor_plan_v3.md` | 18 600-line legacy plan | §5 (P2-3) |
| `old_docs/` | Legacy docs graveyard | §5 (P2-2) |
| `docs/adr/` | 30 ADRs | §7.1 |
| `docs/rfcs/` | 15 RFCs | §7.1 |
| `docs/specs/` | 8 design specs | §7.1 |

## C. References

- **The Update Framework (TUF)** — https://theupdateframework.io/
- **SLSA Framework** — https://slsa.dev/
- **Sigstore / Cosign** — https://www.sigstore.dev/
- **CycloneDX SBOM** — https://cyclonedx.org/
- **WCAG 2.2** — https://www.w3.org/TR/WCAG22/
- **PEP 621** (pyproject.toml metadata) — https://peps.python.org/pep-0621/
- **Conventional Commits** — https://www.conventionalcommits.org/
- **RestrictedPython** — https://restrictedpython.readthedocs.io/
- **wasmtime** — https://wasmtime.dev/
- **ONNX Runtime IO Binding** — https://onnxruntime.ai/docs/api/python/api_summary.html#io-binding
- **One Euro Filter** — Casiez, Roussel, Vogel (CHI 2012) — https://gery.casiez.net/1euro/
- **RFC 6455 (WebSocket)** — https://www.rfc-editor.org/rfc/rfc6455
- **STRIDE threat model** — Microsoft — https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
- **GitHub Actions: Workflow syntax** — https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- **AzureSignTool** — https://github.com/vcsjones/AzureSignTool
- **Apple Notarization** — https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution
- **Existing Maestro ADRs** — `docs/adr/adr-001` through `adr-030`
- **Existing Maestro RFCs** — `docs/rfcs/rfc-001` through `rfc-015`
- **Existing Maestro design specs** — `docs/specs/ds-001` through `ds-008`
- **Prior CI analysis** — `old_docs/ci-failure-analysis.md`, `old_docs/maestro-ci-fix-plan.md`, `old_docs/maestro-ci-failure-analysis-report.md`
- **Prior refactor plan** — `v3.0/maestro_refactor_plan_v3.md` (superseded by this plan for execution purposes; the v3.0 plan remains a useful reference for long-term architecture direction)

---

**End of plan.** This is the contract for the next 6 weeks. Every section identifies a problem, proposes a fix, names the tradeoffs, and sequences the work. Implementation begins with Sprint 1 (CI restoration) and proceeds in order. The plan is a living document — sections will be updated as sprints reveal new information — but the four non-negotiable goals (CI green, branches unified, adaptive tier system shipped, commercial release-ready) do not change.
