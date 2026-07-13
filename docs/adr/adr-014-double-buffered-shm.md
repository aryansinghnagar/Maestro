---
title: "ADR-014: Double-Buffered SharedMemory"
---

### ADR-014: Double-Buffered SharedMemory

**Date:** 2026-07-09
**Status:** Accepted (implemented in commit `2a5991c`)
**Context:** Single-slot SharedMemory has ~0.3% torn-frame probability at 30 FPS when camera writes while engine reads.

**Decision:** Use seqlock-style double-buffered SharedMemory: two frame slots + atomic sequence counter. Writer: increment seq to odd before write, even after. Reader: check seq before/after copy, retry if changed.

**Consequences:**
- Positive: Zero torn frames; non-blocking writer; ~100µs overhead per frame.
- Negative: 2× SHM size (1.84MB vs 921KB); slightly more complex read path.
- Supersedes: ADR-009's "single-slot SharedMemory" claim.

**Implementation:**
- `vision/double_buffer.py` — seqlock implementation
- Header (64 bytes cache-line aligned) + 2× frame size