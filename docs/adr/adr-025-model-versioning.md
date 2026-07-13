---
title: "ADR-025: Model Versioning"
---

### ADR-025: Model Versioning

**Date:** 2026-07-09
**Status:** Proposed
**Context:** As ML models evolve (hand_landmarker v1 → v2, gaze tracker added), we need a model versioning strategy that doesn't break old Maestro installs.

**Decision:**
- Each model has a semantic version (e.g., `hand_landmark-0.1.0.onnx`)
- Model registry (§78.1) tracks versions, SHA-256 hashes, min Maestro version
- Maestro downloads models on first run (not bundled with binary)
- Model updates via TUF (same channel as app updates)
- Backward compatibility: Maestro can use older models (with deprecation warning)
- Forward compatibility: Maestro refuses to load models requiring newer Maestro

**Consequences:**
- Positive: Smaller binary; independent model updates; verifiable integrity.
- Negative: First-run download (~7MB); requires network on first run.