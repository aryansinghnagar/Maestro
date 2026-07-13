---
title: "ADR-024: i18n with gettext"
---

### ADR-024: i18n with gettext

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Maestro's GUI is English-only. For global adoption, we need i18n.

**Decision:**
- Use Python's `gettext` for non-GUI strings
- Use Qt's `QTranslator` + `tr()` for GUI strings
- Use [Crowdin](https://crowdin.com/) for community translations
- Support RTL languages (Arabic, Hebrew, Persian, Urdu)
- Ship with English (100%) + community translations (variable %)

**Consequences:**
- Positive: Global accessibility; community contribution path.
- Negative: Translation maintenance burden; RTL layout testing.

**Implementation:** See §72.