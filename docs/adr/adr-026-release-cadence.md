---
title: "ADR-026: Release Cadence"
---

### ADR-026: Release Cadence

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Need predictable release schedule for users and maintainers.

**Decision:**
- **Minor release** (0.x.0): Monthly
- **Patch release** (0.x.y): As needed for critical bugs
- **Major release** (x.0.0): Yearly (first major: 1.0.0 after v0.3)
- **Pre-release** (0.x.y-rc.z): 1 week before minor release

**Schedule:**
- Sprint 12 (S12) ends → release 0.2.0
- Sprint 18 (3 months later) → release 0.3.0
- Sprint 24 (6 months later) → release 1.0.0

**Consequences:**
- Positive: Predictable; users can plan upgrades; maintainers can plan work.
- Negative: Pressure to ship on schedule may compromise quality.