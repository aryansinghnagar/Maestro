---
title: "RFC-012: i18n Pipeline"
---

### RFC-012: i18n Pipeline

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 10)

#### Problem
Maestro's GUI is English-only. For global adoption, we need i18n with community translations.

#### Proposed Solution

- Python's `gettext` for non-GUI strings
- Qt's `QTranslator` + `tr()` for GUI strings
- Crowdin for community translations
- Support RTL languages (Arabic, Hebrew, Persian, Urdu)
- Ship with English (100%) + community translations (variable %)

#### Pipeline

```
Source code (English)
       ↓
pybabel extract (CI)
       ↓
messages.pot (committed)
       ↓
Crowdin (auto-sync)
       ↓
Community translators
       ↓
.po files (auto-PR)
       ↓
CI compiles .mo files
       ↓
Nuitka bundles .mo files
       ↓
Runtime: load .mo based on user locale
```

#### Supported Languages (initial)

| Language | Code | Native name |
|---|---|---|
| English | en_US | English |
| Spanish | es_ES | Español |
| French | fr_FR | Français |
| German | de_DE | Deutsch |
| Chinese (Simplified) | zh_CN | 简体中文 |
| Japanese | ja_JP | 日本語 |
| Arabic | ar_SA | العربية (RTL) |
| Hindi | hi_IN | हिन्दी |

#### RTL Support

Qt's `setLayoutDirection(Qt.RightToLeft)` for Arabic/Hebrew/Persian/Urdu.

#### Tests
- `test_i18n.py` — verify translations load
- `test_rtl.py` — verify RTL layout doesn't break UI

---