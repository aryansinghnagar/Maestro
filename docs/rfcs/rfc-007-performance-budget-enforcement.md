---
title: "RFC-007: Performance Budget Enforcement"
---

### RFC-007: Performance Budget Enforcement

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 7)

#### Problem
No automated enforcement of latency budgets. Performance regressions are discovered manually.

#### Proposed Solution

Add a CI benchmark job that runs `scripts/profile_latency.py` and fails if any component exceeds its budget.

#### Budgets

| Component | Budget (P50) | Budget (P95) | Budget (P99) |
|---|---|---|---|
| `OneEuroFilter.filter()` | 10µs | 20µs | 30µs |
| `compute_features()` | 50µs | 100µs | 150µs |
| `GestureFSMManager.evaluate()` | 20µs | 40µs | 60µs |
| `CustomGestureMatcher.match()` | 1µs | 5µs | 10µs |
| `np.array` allocation | 2µs | 5µs | 10µs |
| `HandTracker.update()` | 5µs | 10µs | 20µs |
| `LandmarkExtractor.detect_hands()` (GPU) | 8ms | 15ms | 25ms |
| `LandmarkExtractor.detect_hands()` (CPU) | 15ms | 25ms | 40ms |
| `FramePipeline.read()` | 50µs | 100µs | 200µs |
| `ActionDispatcher.dispatch()` | 100µs | 200µs | 500µs |
| **Python hot-path total** | **83µs** | **150µs** | **250µs** |
| **E2E total (GPU)** | **<15ms** | **<25ms** | **<40ms** |

#### CI Integration

```yaml
- run: uv run python scripts/profile_latency.py --check-budgets
```

If any budget is exceeded, CI fails.

#### Budget Revision Process
1. Open issue with `performance-budget` label
2. Justify the revision
3. Get maintainer approval
4. Update BUDGETS in `scripts/profile_latency.py`
5. Update ADR-007
6. Commit with `perf(budget): revise ...`

#### Tests
- `test_benchmarks.py` — pytest-benchmark
- `scripts/profile_latency.py` — comprehensive budget check

---