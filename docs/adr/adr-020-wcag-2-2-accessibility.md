---
title: "ADR-020: WCAG 2.2 Accessibility Commitment"
---

### ADR-020: WCAG 2.2 Accessibility Commitment

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Maestro is a gesture-based accessibility tool, but its own GUI is not accessible. No `setAccessibleName()` calls, no keyboard navigation, no screen reader support.

**Decision:** Commit to WCAG 2.2 Level AA compliance. Audit every widget for accessible names. Ensure keyboard equivalence for every gesture action. Detect and follow system theme (dark/light/high-contrast). Implement tremor compensation with calibration wizard.

**Consequences:**
- Positive: Usable by users with visual impairments (screen readers); motor impairments (tremor compensation); the product is an accessibility tool — it must be accessible itself.
- Negative: Significant engineering effort (~2 sprints); ongoing compliance testing per release.

**Compliance matrix:** See §56.

---