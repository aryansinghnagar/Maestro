---
title: "ADR-023: Telemetry Opt-In"
---

### ADR-023: Telemetry Opt-In

**Date:** 2026-07-09
**Status:** Proposed
**Context:** To improve Maestro, we need usage data (which features are used, which are broken). But Maestro is privacy-by-design; telemetry must be opt-in and minimal.

**Decision:**
- Telemetry is **disabled by default**
- Opt-in via `telemetry.enabled: true`
- Data collected: Maestro version, OS, Python version, inference backend used, aggregate gesture count, crash reports (anonymized)
- Data NOT collected: camera frames, hand landmarks, voice audio, gesture names, app names, URLs, file paths, user identifiers
- Telemetry endpoint: `https://telemetry.maestro.example.com` (OTLP)
- Users can see exactly what's sent: `maestro telemetry preview`

**Consequences:**
- Positive: Privacy-respecting; informed opt-in.
- Negative: Low opt-in rate may limit usefulness.

**Implementation:** See §45.5 (TelemetryManager).