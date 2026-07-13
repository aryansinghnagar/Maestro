---
title: "RFC-013: Model Versioning"
---

### RFC-013: Model Versioning

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 6)

#### Problem
As ML models evolve (hand_landmarker v1 → v2, gaze tracker added), we need a model versioning strategy that doesn't break old Maestro installs.

#### Proposed Solution

- Each model has a semantic version (e.g., `hand_landmark-0.1.0.onnx`)
- Model registry (§78.1) tracks versions, SHA-256 hashes, min Maestro version
- Maestro downloads models on first run (not bundled with binary)
- Model updates via TUF (same channel as app updates)
- Backward compatibility: Maestro can use older models (with deprecation warning)
- Forward compatibility: Maestro refuses to load models requiring newer Maestro

#### Model Manifest

```json
{
  "models": [
    {
      "name": "hand_landmark",
      "version": "0.1.0",
      "sha256": "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
      "size_bytes": 7234567,
      "min_maestro_version": "0.2.0",
      "url": "https://models.maestro.example.com/hand_landmark-0.1.0.onnx"
    },
    {
      "name": "hand_landmark",
      "version": "0.1.0-int8",
      "sha256": "a1b2c3d4e5f6...",
      "size_bytes": 2100000,
      "min_maestro_version": "0.2.0",
      "url": "https://models.maestro.example.com/hand_landmark-0.1.0-int8.onnx"
    }
  ]
}
```

#### Download Flow

1. Maestro starts
2. Check `~/.config/gesture_controller/models/` for required models
3. For each missing model, download via TUF (verified)
4. Verify SHA-256
5. Load model

#### Cache Invalidation

- If model file is corrupted (SHA-256 mismatch), re-download
- If model version is older than registry's latest, offer to update
- User can manually clear cache: `maestro models clear-cache`

#### Tests
- `test_model_versioning.py` — version parsing, compatibility checks
- `test_model_download.py` — TUF verification, SHA-256 validation

---