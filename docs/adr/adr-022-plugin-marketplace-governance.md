---
title: "ADR-022: Plugin Marketplace Governance"
---

### ADR-022: Plugin Marketplace Governance

**Date:** 2026-07-09
**Status:** Proposed
**Context:** A community plugin marketplace (§70) needs governance: who can publish, how are plugins reviewed, how are malicious plugins removed.

**Decision:**
- Anyone can publish plugins to PyPI with `maestro-*` prefix
- Maestro CLI lists plugins from a curated `marketplace.json` (review required)
- Review process: static analysis, manifest validation, license check, permissions review, manual review
- Plugins signed with Sigstore (keyless, OIDC)
- Malicious plugin removal: yank from PyPI, remove from marketplace.json, notify users via in-app alert

**Consequences:**
- Positive: Open ecosystem with safety rails.
- Negative: Review burden on maintainers; potential for abuse if review is slow.