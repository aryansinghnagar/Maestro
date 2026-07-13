---
title: "RFC-014: Accessibility Audit Process"
---

### RFC-014: Accessibility Audit Process

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 9+)

#### Problem
Accessibility is not a one-time achievement; it requires ongoing audits.

#### Proposed Solution

**Pre-release audit (each minor release):**
1. Automated checks:
   - axe-core scan (where applicable)
   - Custom script: verify every widget has `accessibleName`
2. Manual checks (3 platforms):
   - NVDA on Windows
   - VoiceOver on macOS
   - Orca on Linux
3. Keyboard-only testing: complete all tasks via keyboard
4. High contrast testing: verify all UI readable
5. Reduced motion testing: verify no animations

**Annual external audit:**
- Hire external accessibility consultant
- 1-day audit per platform (3 days total)
- Track findings in GitHub Issues
- Fix critical findings before next release

**User feedback:**
- Track accessibility issues in GitHub Issues with `accessibility` label
- Respond within 72 hours
- Fix critical issues in next patch release

**WCAG version tracking:**
- Currently: WCAG 2.2 AA
- Future: WCAG 3.0 when finalized (estimated 2027+)

#### Audit Checklist

For each release:
- [ ] Run `maestro a11y audit` (automated)
- [ ] NVDA test pass
- [ ] VoiceOver test pass
- [ ] Orca test pass
- [ ] Keyboard-only test pass
- [ ] High contrast test pass
- [ ] Reduced motion test pass
- [ ] No new WCAG 2.2 AA violations
- [ ] All `accessibility` issues resolved or scheduled

#### Tests
- `test_a11y_audit.py` — automated checks
- Manual test matrix: documented in `docs/accessibility.md`

---