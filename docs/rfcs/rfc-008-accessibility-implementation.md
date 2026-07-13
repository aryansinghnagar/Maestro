---
title: "RFC-008: Accessibility Implementation Plan"
---

### RFC-008: Accessibility Implementation Plan

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 9)

#### Problem
Maestro is an accessibility tool whose own GUI is not accessible. No screen reader support, no keyboard navigation, no high-contrast mode.

#### Proposed Solution

**Phase 1: QAccessible audit (Sprint 9 Week 1)**
- Run NVDA (Windows), VoiceOver (macOS), Orca (Linux) against every dialog
- Add `setAccessibleName()` and `setAccessibleDescription()` to every interactive widget
- Ensure `QAccessibleEvent` is fired on gesture state changes

**Phase 2: Keyboard navigation (Sprint 9 Week 1)**
- Every gesture action must have a keyboard equivalent (§58.1)
- Set `focusPolicy`, `setTabOrder()` on all widgets
- Style visible focus indicators (§58.4)
- Register global hotkeys via platform-specific APIs

**Phase 3: Motor accessibility (Sprint 9 Week 2)**
- Fix `OneEuroFilter.reset()` to clear tremor history (§59.1)
- Make tremor parameters configurable
- Add "Tremor Calibration" wizard (record 30s → fit spectrum → set params)
- Implement dwell-clicking (cursor held within radius for N ms → click)

**Phase 4: Visual accessibility (Sprint 9 Week 2)**
- Detect system theme via `QGuiApplication.styleHints().colorScheme()`
- Ship dark/light/high-contrast QSS themes (§61)
- Use Okabe-Ito color-blind-safe palette for overlay
- Honor "reduced motion" preference

**Phase 5: Voice control (Sprint 8, parallel)**
- Replace Google speech with Vosk (offline, §49)
- Wake word + command vocabulary
- Voice settings in Accessibility tab

#### Compliance Target
WCAG 2.2 Level AA. See §56 for compliance matrix.

#### Verification
- Automated: axe-core, WAVE (limited for Qt apps)
- Manual: NVDA, VoiceOver, Orca testing
- External audit: hire accessibility consultant for 1-day audit
- User feedback: track accessibility issues in GitHub

#### Tests
- Manual test matrix: 5 tasks × 3 screen readers = 15 tests
- Keyboard-only test: complete all gestures via keyboard
- High contrast test: verify all UI readable in high contrast mode
- Reduced motion test: verify no animations when enabled

---