# Contributing to Maestro

Thank you for your interest in contributing! This document covers everything you need to get started.

## Code of Conduct

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Setup

### Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (package manager)
- Git
- A webcam (for testing gesture recognition)

### Initial setup

```bash
git clone https://github.com/aryansinghnagar/Maestro.git
cd Maestro
uv sync --frozen          # Install all deps
uv run pre-commit install # Install git hooks
uv run pytest             # Verify tests pass
```

### Platform-specific setup

**Linux:**
```bash
sudo usermod -aG input $USER  # For uinput
# Log out and back in
sudo apt install python3-dev libegl1 libgl1  # For OpenCV
```

**macOS:**
```bash
brew install python@3.11
xcode-select --install
```

**Windows:**
```powershell
# Install Visual Studio Build Tools (for compiling C extensions)
choco install visualstudio2022buildtools --params "--add Microsoft.VisualStudio.Workload.PythonTools"
```

## Development Workflow

### 1. Pick an issue

Browse [open issues](https://github.com/aryansinghnagar/Maestro/issues). Look for labels:
- `good first issue` — small, self-contained, good for newcomers
- `help wanted` — we'd appreciate community help
- `bug` — confirmed bugs
- `enhancement` — new features

If you want to work on something not in issues, open a discussion first.

### 2. Create a branch

```bash
git checkout -b feat/<scope>-<short-desc> main
# or
git checkout -b fix/gh-<issue>-<short-desc> main
```

### 3. Make changes

Follow our coding standards:

- **Style:** Ruff (auto-formats on commit via pre-commit)
- **Types:** mypy (progressive strict)
- **Tests:** pytest (aim for >80% coverage on changed lines)
- **Commits:** Conventional Commits (see below)

### 4. Commit

We use [Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Examples:
```
feat(vision): add TensorRT execution provider for NVIDIA GPUs
fix(os): define logger in linux_controller to prevent NameError crash
docs(api): update plugin SDK reference
refactor(core): extract FramePipeline from GestureEngine
```

### 5. Push and open a PR

```bash
git push origin feat/<scope>-<short-desc>
gh pr create --fill
```

PRs require:
- 1 approval
- All CI checks passing
- Linear history (rebase, don't merge)
- Conversation resolution

### 6. Review and merge

Address review feedback by pushing new commits (don't force-push after review). Once approved, a maintainer will squash-merge your PR.

## Coding Standards

### Python style

- PEP 8 (enforced by Ruff)
- PEP 585 (use `list[int]` not `List[int]`)
- Type hints required on all new code
- Docstrings on all public functions (Google style)
- Max line length: 100 (enforced by Ruff)

### Testing

- Test files in `tests/unit/`, `tests/integration/`, `tests/e2e/`
- Test functions: `test_<thing>_<condition>()`
- Use `pytest` fixtures for setup
- Property-based tests for algorithms (`hypothesis`)
- Mock external dependencies (`pytest-mock`)
- No real hardware in CI (`@pytest.mark.requires_hardware`)

### Architecture

- Follow the ADRs in `docs/adr/`
- New architectural decisions require an ADR
- New components require a Protocol in `core/protocols.py`
- No god classes (>300 LOC, >10 responsibilities)
- No circular imports

### Security

- No `exec()` or `eval()` in production code
- No `os.system()` — use `subprocess.run()` with `shell=False`
- No hardcoded secrets — use `secrets.token_urlsafe()`
- All `subprocess.run` calls must have `timeout=`
- All user input must be validated
- All file paths must be sanitized

### Accessibility

- All interactive widgets must have `setAccessibleName()`
- All gestures must have keyboard equivalents
- All colors must meet WCAG 2.2 AA contrast (4.5:1 text, 3:1 UI)
- Test with NVDA (Windows), VoiceOver (macOS), Orca (Linux) before merging GUI changes

## Reporting Bugs

Open a [GitHub Issue](https://github.com/aryansinghnagar/Maestro/issues/new?template=bug_report.md). Include:
- Maestro version (`maestro --version`)
- OS and version
- Python version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Logs (from `~/.config/gesture_controller/logs/maestro.log`)

## Reporting Security Vulnerabilities

**Do NOT open a public issue.** Email `security@aryansinghnagar.dev` with details. See [SECURITY.md](SECURITY.md) for our PGP key and disclosure policy.

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0-or-later](LICENSE).
