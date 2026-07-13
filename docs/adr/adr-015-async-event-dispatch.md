---
title: "ADR-015: Async Event Dispatch"
---

### ADR-015: Async Event Dispatch

**Date:** 2026-07-09
**Status:** Accepted (implemented)
**Context:** Synchronous `gesture_triggered` dispatch blocked the engine thread for up to 250ms per gesture (subprocess calls for foreground-app detection), dropping 7 frames at 30 FPS.

**Decision:** Move `gesture_triggered` from `SYNC_EVENTS` to async dispatch. The ActionDispatcher runs on the EventBus worker thread. Only `raw_landmarks` remains sync (for ultra-low-latency overlay updates).

**Consequences:**
- Positive: Engine thread never blocks on OS action execution; zero dropped frames from dispatch.
- Negative: Gesture-to-action latency increases by ~5ms (queue serialization); test timing requires `sleep()`.
- Supersedes: ADR-006's "synchronous for latency-critical" claim (only raw_landmarks is sync now).