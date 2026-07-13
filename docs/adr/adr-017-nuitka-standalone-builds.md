---
title: "ADR-017: Nuitka Standalone Builds"
---

### ADR-017: Nuitka Standalone Builds

**Date:** 2026-07-09
**Status:** Proposed
**Context:** PyInstaller `--onefile` produces ~80MB binaries with `.pyc` files that are trivially decompilable. Binary size matters for distribution.

**Decision:** Adopt Nuitka `--standalone --onefile --enable-plugin=anti-bloat --lto=yes` as primary distribution. Keep PyInstaller as fallback.

**Consequences:**
- Positive: ~25-35MB binaries; compiled C code (harder to reverse-engineer); genuine speedup on Python-heavy paths; anti-bloat plugin removes unused stdlib.
- Negative: Longer build times (~5min); less ecosystem maturity than PyInstaller; potential PyQt6 plugin issues.

**Build command:** See §31.2