---
title: "ADR-012: Hand-ID Tracking via Wrist Position Matching"
---

### ADR-012: Hand-ID Tracking via Wrist Position Matching

**Date:** 2026-07-09
**Status:** Accepted (implemented in commit `2a5991c`)
**Context:** MediaPipe returns hands in arbitrary order between frames. Per-handedness filter keying (`"Left"`/`"Right"`) corrupts OneEuroFilter state, FSM state, and DTW buffer when handedness flips or hands cross.

**Decision:** Implement `HandTracker` using greedy nearest-neighbor wrist-position matching with max-distance threshold (0.25 normalized units). Assign persistent integer track IDs. Key filters, FSMs, and DTW buffers by track ID.

**Consequences:**
- Positive: Correct multi-hand tracking; no corruption on hand swap or handedness flip.
- Negative: O(N×M) matching (fine for ≤2 hands); track IDs are not reused (monotonically increasing).

**Implementation:**
```python
class HandTracker:
    def update(self, hands: list[Hand], frame_number: int) -> list[tuple[Hand, int]]:
        # Greedy nearest-neighbor matching
        # Returns list of (hand, track_id) tuples
```

**Future:** Consider SORT (Kalman + Hungarian) for v0.3 if tracking issues arise.