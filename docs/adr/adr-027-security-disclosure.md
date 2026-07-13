---
title: "ADR-027: Security Disclosure"
---

### ADR-027: Security Disclosure

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Need clear policy for receiving and disclosing security vulnerabilities.

**Decision:**
- Report vulnerabilities to `security@aryansinghnagar.dev` (PGP encrypted)
- Acknowledge within 24 hours
- Initial assessment within 72 hours
- Fix timeline:
  - Critical: 7 days
  - High: 30 days
  - Medium: 90 days
- Public disclosure after fix released, or 90 days (whichever is first)
- Credit reporters in release notes (anonymous if requested)
- No monetary rewards (no bug bounty program)

**Consequences:**
- Positive: Clear expectations; coordinated disclosure.
- Negative: 90-day deadline may be tight for complex fixes.

**Implementation:** See §55 (incident response playbook).