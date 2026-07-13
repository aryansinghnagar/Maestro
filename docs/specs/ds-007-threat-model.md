---
title: "DS-007: Threat Model Spec"
---

## DS-007: Threat Model Spec

### 102.1 STRIDE per asset

See §5.2 for the STRIDE matrix.

### 102.2 Attack surfaces

1. **Camera frames (A1)** — SHM with chmod 0600; future: memfd_create
2. **Hand landmarks (A2)** — in-process only
3. **OS input injection (A3)** — broker process with auth
4. **Configuration file (A4)** — user-writable; future: signed
5. **Plugin code (A5)** — WASM sandbox for untrusted
6. **Update channel (A6)** — TUF with threshold=3
7. **REST/WS API (A7)** — random token + Origin validation
8. **Audit logs (A8)** — append-only, user-readable

### 102.3 Top 10 threats (mitigations)

See §5.3.

### 102.4 LINDDUN privacy analysis

See §5.4.

### 102.5 Incident response

See §55.

### 102.6 Security review process

For each PR touching security-sensitive code (`broker.py`, `updater.py`, `integration_server.py`, `plugin_loader.py`):

1. **Automated:** bandit + pip-audit + custom security linter
2. **Manual:** reviewer with security expertise required
3. **Threat model update:** if new attack surface, update DS-007
4. **Test:** adversarial test cases (fuzz, sandbox escape attempts)

### 102.7 Penetration testing

Annual external pentest:
- 2-day engagement
- Focus on: plugin sandbox, broker auth, update channel, REST API
- Findings tracked in private security issues
- Critical findings fixed before next release

### 102.8 Bug bounty (future)

When Maestro has revenue, consider bug bounty program:
- HackerOne or Bugcrowd
- Payouts: $100 (low) to $5000 (critical)
- Scope: Maestro application, plugins, marketplace

---