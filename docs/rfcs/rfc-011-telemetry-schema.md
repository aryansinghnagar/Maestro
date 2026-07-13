---
title: "RFC-011: Telemetry Schema"
---

### RFC-011: Telemetry Schema

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 11)

#### Problem
Need to define exactly what telemetry data is collected, in what format, and how it's transmitted.

#### Proposed Solution

**OTLP (OpenTelemetry Protocol)** to `https://telemetry.maestro.example.com`.

**Metrics:**

| Metric | Type | Tags | Description |
|---|---|---|---|
| `maestro.frames.processed` | counter | backend | Number of frames processed |
| `maestro.gestures.triggered` | counter | gesture, backend | Number of gestures triggered |
| `maestro.latency.e2e_ms` | histogram | backend | E2E latency in ms |
| `maestro.latency.inference_ms` | histogram | backend | Inference latency in ms |
| `maestro.backend.active` | gauge | backend | Currently active backend (1=active, 0=inactive) |
| `maestro.plugins.loaded` | gauge | | Number of plugins loaded |
| `maestro.errors.count` | counter | component | Number of errors |
| `maestro.session.duration_s` | histogram | | Session duration in seconds |

**NOT collected (privacy-critical):**
- Camera frames
- Hand landmarks
- Voice audio
- Gesture names (only aggregate count, not per-gesture)
- App names
- URLs
- File paths
- User identifiers (no user ID, no machine ID, no IP)
- Geolocation

**Privacy review:** Telemetry schema is reviewed quarterly. Any addition requires ADR update.

**Opt-out:** `telemetry.enabled: false` (default). Users can preview what's sent: `maestro telemetry preview`.

#### Tests
- `test_telemetry.py` — verify only allowed metrics are sent
- Network monitor test: no telemetry network calls when disabled

---