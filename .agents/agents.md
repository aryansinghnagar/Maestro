# Repository Instructions & Guidelines for AI Coding Agents

This directory and rule file define the mandatory coding, architecture, and quality standards for all AI agents working on **Maestro** (dual Python and JavaScript/TypeScript stack).

---

## 1. Core Principles & Hygiene

1. **Dual-Stack Rigor**:
   - **Python Ecosystem**: Enforce Python 3.11+ type annotations, strict `mypy` compliance (0 errors allowed), `black` formatting, and `bandit` security scanning.
   - **JavaScript / Node.js Ecosystem**: Enforce ES2022+ standards, strict typing/JSDoc, Biome/Prettier formatting, and Vitest/Jest unit testing.

2. **Algorithmic Efficiency & Zero-Allocation Loops**:
   - The computer vision pipeline runs at up to 60 FPS (<16.6ms per frame budget).
   - Real-time loops (One-Euro filter, landmark extraction, state machine transitions) must avoid transient object allocations or unbuffered memory copies.
   - Micro-benchmarks (`pytest-benchmark`) must maintain latency thresholds (<15µs for One-Euro filter iteration, <25µs for FSM evaluation).

3. **Strict Test Coverage**:
   - Maintain >80% test coverage across both Python (`pytest --cov=gesture_controller`) and JS test suites.
   - Never suppress or delete existing unit, integration, or replay tests.
   - Every bug fix or new feature must include corresponding test cases.

4. **Security & Sandboxing**:
   - Custom gesture condition expressions must be parsed via restricted AST evaluation (`gesture_controller/core/expression_evaluator.py`). Never use raw `eval()` or `exec()`.
   - Native OS input injection must use isolated privilege brokers (`broker.py`) for Windows UIPI compliance and non-blocking Quartz/uinput events.

5. **CI/CD Alignment**:
   - All GitHub Actions workflows (`ci.yml`, `docs.yml`, `dependabot.yml`) must pass cleanly on all pull requests and pushes to `main`.
   - Dependabot updates for both `npm` and `pip` ecosystems must be maintained and verified daily.
