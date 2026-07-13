---
title: "ADR-013: Privilege-Separated Input Broker"
---

### ADR-013: Privilege-Separated Input Broker

**Date:** 2026-07-09
**Status:** Accepted (implemented in commit `2a5991c`)
**Context:** The engine process has both camera access AND input injection access AND runs plugin code. A compromised plugin can read camera frames AND inject keystrokes from the same process.

**Decision:** Run input injection in a separate broker process. The main app communicates via Unix socket / named pipe. The broker has rate limiting, audit logging, and a kill switch. Broker socket authenticated via `SO_PEERCRED` (Linux) / `getpeereid` (macOS) / named pipe ACL (Windows).

**Consequences:**
- Positive: Compromised plugin cannot directly inject input; rate limiting prevents runaway gestures; audit trail.
- Negative: IPC latency (~0.5ms per action); broker process lifecycle management complexity.

**Implementation:**
- `os_integration/broker/server.py` — runs in broker process
- `os_integration/broker/client.py` — runs in engine process
- `os_integration/broker/auth.py` — cross-platform peer credential verification