---
title: "ADR-029: Observability Pillars"
---

### ADR-029: Observability Pillars

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Need structured approach to logs, metrics, and traces for debugging production issues.

**Decision:** Three pillars of observability:
1. **Logs** — Structured event logs (structlog). Always on (file + stdout).
2. **Metrics** — Aggregate numbers (OpenTelemetry). Opt-in (telemetry config).
3. **Traces** — Request-scoped spans (OpenTelemetry). Opt-in, debug builds only.

**Logs:**
- File: `~/.config/gesture_controller/logs/maestro.log` (rotating)
- Audit: `~/.config/gesture_controller/logs/audit.log` (append-only, 30-day retention)
- Crash: `~/.config/gesture_controller/logs/crash-<timestamp>.txt`

**Metrics:**
- `maestro.frames.processed` (counter)
- `maestro.gestures.triggered` (counter, tagged by gesture name)
- `maestro.latency.e2e` (histogram, ms)
- `maestro.backend.active` (gauge, tagged by backend name)

**Traces:**
- Span per frame: `frame_pipeline.read` → `inference_pipeline.process` → `gesture_recognizer.evaluate`
- Span per gesture: `event_bus.publish` → `action_dispatcher.dispatch` → `broker.inject`

**Consequences:**
- Positive: Debugging production issues; performance regression detection.
- Negative: Performance overhead when enabled; storage for logs.

**Implementation:** See §45.