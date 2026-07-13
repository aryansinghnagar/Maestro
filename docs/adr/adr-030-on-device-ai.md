---
title: "ADR-030: On-Device AI"
---

### ADR-030: On-Device AI

**Date:** 2026-07-09
**Status:** Proposed
**Context:** As ML capabilities grow (gaze tracking, gesture transformer), we need to decide: cloud AI or on-device AI?

**Decision:** **On-device AI only.** No cloud AI, ever. This is a non-negotiable privacy commitment.

**Rationale:**
- Maestro processes biometric data (hand landmarks, face, voice)
- Cloud AI would require shipping this data to servers
- Even with encryption, this violates ADR-009 (privacy by design)
- On-device AI is fast enough (ONNX Runtime GPU)
- On-device AI is cheap enough (no cloud compute costs)

**Implementation:**
- All inference via ONNX Runtime (local)
- All speech via Vosk (local)
- All gaze via MediaPipe Face Mesh (local)
- Future transformer gestures: small model (TCN, distilled Transformer) running locally

**Trade-offs:**
- Smaller models than cloud (less accurate)
- No learning from user data (no personalization via fine-tuning)
- Hardware requirements (need GPU for some models)

**Consequences:**
- Positive: Ironclad privacy; no cloud costs; works offline.
- Negative: Model accuracy bounded by local hardware; no personalized improvements.

---