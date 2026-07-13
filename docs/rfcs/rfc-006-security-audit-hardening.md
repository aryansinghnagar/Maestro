---
title: "RFC-006: Security Audit and Hardening"
---

### RFC-006: Security Audit and Hardening

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 8)

#### Problem
6 P2+ security issues: hardcoded auth token, unauthenticated broker socket, TUF threshold=1, Google speech recognition, `exec` in plugin loader, WebSocket CSWSH.

#### Proposed Solution

| Issue | Fix | Effort | Section |
|---|---|---|---|
| S1: Hardcoded token | `secrets.token_urlsafe(32)` on first run, `chmod 0600` | S | §46 |
| S2: Broker socket auth | `SO_PEERCRED` / `getpeereid` / pipe ACL | M | §47 |
| S3: TUF threshold | `threshold=3` with 5 keys | M | §48 |
| S4: Voice Google API | Replace with Vosk (offline) | M | §49 |
| S5: exec in plugins | WASM sandbox (wasmtime) | L | §50 |
| S6: Plugin sandbox bypass | Block `from X import Y` in AST scan | S | §51 |
| S7: os.system shell | `subprocess.run(["open", url], timeout=2.0)` | S | §52 |
| S8: WebSocket CSWSH | Validate `Origin` header | S | §53 |

#### Threat Model
See DS-007 (§102) for full STRIDE threat model.

#### Verification
- Bandit scan: 0 high/critical findings
- Manual pentest: hire external consultant for 2-day engagement
- Fuzz testing: extend atheris targets
- Code review: security-focused review of all changes

#### Tests
- `test_integration_server_auth.py` — token auth
- `test_broker_auth.py` — peer credential verification
- `test_updater.py` — TUF threshold
- `test_voice_listener.py` — no network calls
- `test_plugin_sandbox.py` — adversarial code
- `test_websocket_cswsh.py` — Origin validation

---