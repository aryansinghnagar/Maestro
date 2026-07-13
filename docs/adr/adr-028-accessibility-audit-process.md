---
title: "ADR-028: Accessibility Audit Process"
---

### ADR-028: Accessibility Audit Process

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Accessibility is not a one-time achievement; it requires ongoing audits.

**Decision:**
- **Pre-release audit:** Before each minor release, run:
  - Automated: axe-core, WAVE, Lighthouse
  - Manual: NVDA (Windows), VoiceOver (macOS), Orca (Linux)
  - Keyboard-only testing
  - High contrast testing
- **Annual external audit:** Hire external accessibility consultant for 1-day audit
- **User feedback:** Track accessibility issues in GitHub Issues with `accessibility` label
- **WCAG version:** Track WCAG 2.2 AA (upgrade to WCAG 3.0 when finalized)

**Consequences:**
- Positive: Ongoing compliance; user trust.
- Negative: Time investment per release.

**Implementation:** See §56, §62.