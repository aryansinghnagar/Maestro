---
title: "ADR-018: uv Package Manager"
---

### ADR-018: uv Package Manager

**Date:** 2026-07-09
**Status:** Proposed
**Context:** `pip` + `venv` + `pip-tools` is slow (10-60s install times in CI) and `requirements.txt` drifts from `pyproject.toml`.

**Decision:** Replace with `uv` (Rust-based, 10-100× faster). Use `uv.lock` for reproducible installs. Delete `requirements.txt` and `requirements-dev.txt`.

**Consequences:**
- Positive: 10-100× faster installs; single source of truth (`pyproject.toml`); `uv.lock` for reproducibility.
- Negative: New tool dependency; team must learn `uv` commands.