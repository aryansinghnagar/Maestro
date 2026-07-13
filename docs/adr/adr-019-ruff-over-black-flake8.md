---
title: "ADR-019: Ruff over Black + Flake8"
---

### ADR-019: Ruff over Black + Flake8

**Date:** 2026-07-09
**Status:** Proposed
**Context:** Black (formatter) + flake8 (linter) + isort (import sorting) = 3 tools, 3 configs, slow CI. Ruff (Astral, Rust-based) replaces all three at 100× speed.

**Decision:** Adopt `ruff check` (linting) + `ruff format` (formatting). Drop `black`, `flake8`, `isort` from dev deps and CI.

**Consequences:**
- Positive: 100× faster; single tool; single config in `pyproject.toml`; broader rule set.
- Negative: Minor formatting differences from Black (99% compatible).