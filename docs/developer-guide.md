# Maestro Developer Guide

This guide covers everything required to set up a local development environment, build from source, run test suites, profile execution bottlenecks, and contribute to **Maestro**.

---

## 1. Repository Layout

```
Maestro/
├── .github/                 # GitHub Actions workflows (CI, docs, fuzzing, release)
├── docs/                    # MkDocs documentation site source
├── gesture_controller/      # Main Python source package
│   ├── cli/                 # CLI entry points and verification scripts
│   ├── core/                # EventBus, config manager, FSM, tier manager, updater
│   ├── data/                # Custom gesture templates and internal schemas
│   ├── gui/                 # PyQt6 system tray, settings, HUD overlay, wizards
│   ├── models/              # DTW matcher, hand normalization, topology graph
│   ├── os_integration/      # Native input controllers (Win32, Quartz, uinput, broker)
│   ├── plugins/             # Pluggy hooks, RestrictedPython loader, WASM sandbox
│   ├── tests/               # Multi-tiered test suite
│   │   ├── benchmarks/      # Latency & throughput performance tests
│   │   ├── e2e/             # End-to-end user journey tests
│   │   ├── fuzz/            # Property fuzzers (Atheris, Hypothesis)
│   │   ├── integration/     # Inter-subsystem interaction tests
│   │   ├── replay/          # Deterministic landmark sequence fixtures
│   │   └── unit/            # Isolated unit test suites
│   └── vision/              # ONNX Runtime, double buffer SHM, OneEuroFilter
├── packaging/               # InnoSetup/NSIS, systemd service, udev rules
├── scripts/                 # Maintenance, quantization, and profiling tools
├── mkdocs.yml               # MkDocs documentation configuration
└── pyproject.toml           # Build system, dependencies, and tool settings
```

---

## 2. Local Environment Setup

We recommend using [uv](https://docs.astral.sh/uv/) for instant virtual environment creation and dependency locking:

```bash
# 1. Clone the repository
git clone https://github.com/aryansinghnagar/Maestro.git
cd Maestro

# 2. Sync all dependencies into the virtual environment
uv sync

# 3. Install git pre-commit hooks
uv run pre-commit install

# 4. Verify test suite execution
uv run pytest gesture_controller/tests
```

---

## 3. Code Standards & Static Analysis

Maestro enforces strict static analysis across all contributions:

### Formatters & Linters

- **Ruff**: Enforces PEP 8 styling, import ordering, and common bug prevention:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **Mypy (Strict Mode)**: Static type safety across all source modules:
  ```bash
  uv run mypy gesture_controller
  ```
- **Bandit & Security Scanners**:
  ```bash
  uv run bandit -r gesture_controller/ -x gesture_controller/tests/ -ll
  ```
- **Biome (JavaScript / Docs tests)**:
  ```bash
  npm run lint:js
  npm test
  ```

---

## 4. Test Suite Execution

Maestro uses `pytest` with a multi-layered testing taxonomy:

### Running All Tests
```bash
uv run pytest gesture_controller/tests
```

### Running Specific Test Suites
- **Unit Tests**:
  ```bash
  uv run pytest gesture_controller/tests/unit
  ```
- **Integration Tests**:
  ```bash
  uv run pytest gesture_controller/tests/integration
  ```
- **Replay Regression Tests**:
  ```bash
  uv run pytest gesture_controller/tests/replay
  ```
- **Performance Benchmarks**:
  ```bash
  uv run pytest gesture_controller/tests/benchmarks --benchmark-only
  ```

---

## 5. Profiling & Performance Diagnostics

### Daemon Profiling
Start and stop a runtime profiling session on a running Maestro instance:
```bash
# Start profiling
maestro profile-start

# Stop profiling and output cumulative stats
maestro profile-stop --output profile.pstats
```

### Frame Latency Benchmark
Run the standalone latency profiler:
```bash
uv run python scripts/profile_latency.py
```

### Model Quantization
Quantize the ONNX palm detector and landmark models to INT8:
```bash
uv run python scripts/quantize_model.py
```

---

## 6. Local Documentation Server

Preview the documentation site with live reloading:

```bash
uv run mkdocs serve
```

Then navigate to `http://localhost:8000` in your web browser.

