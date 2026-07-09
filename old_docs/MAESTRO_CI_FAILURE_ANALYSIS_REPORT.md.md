# CI Failure Analysis Report

**Document Date:** July 8, 2026  
**Repository:** aryansinghnagar/Maestro  
**Project:** Gesture-based Controller for PC's  
**Language:** Python (99.1%)  

---

## Executive Summary

This report provides a comprehensive analysis of all failed CI/CD tests in the Maestro repository. The analysis identifies **one primary root cause** affecting **100% of failed runs**: **MyPy type checking failures** in the Windows controller module due to missing type stubs for the `ctypes.windll` attribute.

**Current Status:**
- Total workflow runs analyzed: 30+
- Failed CI runs: 12
- Failed release-please runs: 8
- Success rate: 33%
- **Critical blocker:** Windows-specific type checking issue preventing main branch deployments

---

## Detailed Failure Analysis

### PRIMARY ISSUE: MyPy Type Checking - Missing windll Attribute Stubs

**Severity:** 🔴 CRITICAL  
**Impact:** All CI runs on main branch  
**Affected Component:** `gesture_controller/os_integration/windows_controller.py`  
**Error Count:** 9 instances across multiple commits

---

#### Problem Description

**Root Cause:**
The `ctypes` module in Python's standard library has incomplete type stubs for platform-specific functionality. When MyPy runs with `strict = true` mode (enabled in `pyproject.toml` line 84), it performs full type checking on all code, including Windows-specific APIs accessed via `ctypes.windll`.

The `ctypes.windll` attribute is a dynamic proxy object that doesn't have proper type annotations in the Python typeshed. This causes MyPy to report:
```
Module has no attribute "windll"  [attr-defined]
```

**Why It Occurs:**
- `ctypes` is a built-in module with dynamic attribute creation via `__getattr__`
- `windll` is created at runtime for Windows systems
- Type stubs (`.pyi` files) for `ctypes` don't include this dynamic attribute
- Linux/macOS CI runners can't validate Windows-specific code at runtime, only through type checking
- The code runs in strict mode without proper Windows platform guards

**Error Locations:**
```
Line 190:  ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))
Line 197:  ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))
Line 268:  ctypes.windll.user32.SetCursorPos(x, y)
Line 280:  hwnd = ctypes.windll.user32.GetForegroundWindow()
Line 284:  length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
Line 288:  ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
Line 292:  ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
Line 302:  hwnd = ctypes.windll.user32.GetForegroundWindow()
Line 304:  ctypes.windll.user32.ShowWindow(hwnd, 6)
```

**Affected Commits:**
1. `3da7a4051b640977161e6afff27ff3c19d26a44a` - "docs: archive legacy design docs" (Run 28855935046)
2. `d57cfa1306dcb02133f109a47e2729418a6f243f` - "build(deps-dev): update pytest-cov" (Run 28855069558)
3. `5476df91c7c3e1b182dadb4889e02308e1469390` - "feat: implement compile-time RestrictedPython plugin" (Run 28854940258)
4. `eaa9a934c7b3d4b0eb3c2f8efb98b4d77d40264b` - "feat: integrate strict static type checking" (Run 28853001378)
5. `edb123f71c46d27fbb2dcf0d342ef2d6ab5414ac` - "build(deps): bump actions/checkout from 4 to 7" (Run 28805032527)
6. `13fb50787a5f6088414344961e8b8c8573d7c18f` - "build(deps): bump actions/setup-python from 5 to 6" (Run 28805031727)
7. `9da18d6bbacd0356c08181af498d5a33d4197d4f` - "feat: complete Sprints 7-9" (Run 28804905372)
8. `7eac7834da58db8058bc31f4b9ec74af24fe0597` - "chore: implement CI greening" (Run 28782410616)

---

#### Detailed Solution: Type-Safe Windows API Wrapping

**Recommended Approach:** Create a typed wrapper module for Windows API calls using proper type annotations and `TYPE_CHECKING` guards.

**Step 1: Create Windows API Stubs File**

Create `gesture_controller/os_integration/windows_api_stubs.py`:

```python
"""Type stubs and typed wrappers for Windows API calls via ctypes."""

from typing import TYPE_CHECKING, Any, Optional
import ctypes
from ctypes import wintypes

# Only import windll on Windows to avoid import errors on other platforms
if TYPE_CHECKING:
    # For type checking only - provides type information without runtime errors
    class User32API:
        """Typed interface to user32.dll Windows API functions."""
        def SendInput(self, nInputs: int, pInputs: Any, cbSize: int) -> int: ...
        def SetCursorPos(self, x: int, y: int) -> bool: ...
        def GetForegroundWindow(self) -> Optional[int]: ...
        def GetWindowTextLengthW(self, hWnd: int) -> int: ...
        def GetWindowTextW(self, hWnd: int, lpString: Any, nMaxCount: int) -> int: ...
        def GetWindowThreadProcessId(self, hWnd: int, lpdwProcessId: Any) -> int: ...
        def ShowWindow(self, hWnd: int, nCmdShow: int) -> bool: ...

    user32: User32API

else:
    # Runtime: safely access ctypes.windll with proper error handling
    import platform
    
    if platform.system() == "Windows":
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback if windll is not available
            user32 = None  # type: ignore
    else:
        user32 = None  # type: ignore
```

**Step 2: Update windows_controller.py**

Update the imports and function calls:

```python
# At the top of windows_controller.py
import platform
import structlog
import ctypes
from ctypes import wintypes
from typing import Any, Optional

from gesture_controller.os_integration.base_controller import BaseController
from gesture_controller.os_integration.windows_api_stubs import user32

logger = structlog.get_logger(__name__)

# ... rest of code ...

def send_key_event(vk_code: int, is_up: bool = False) -> None:
    """Send keyboard event using native Win32 API."""
    if vk_code == 0 or user32 is None:
        return
    
    flags = 0x0002 if is_up else 0  # KEYEVENTF_KEYUP = 0x0002
    ki = KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    union = INPUT_UNION(ki=ki)
    input_struct = INPUT(type=1, u=union)  # INPUT_KEYBOARD = 1
    
    try:
        user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))
    except (AttributeError, OSError) as e:
        logger.error("Failed to send key event", error=str(e))

def send_mouse_event(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> None:
    """Send mouse event using native Win32 API."""
    if user32 is None:
        return
    
    mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0, dwExtraInfo=0)
    union = INPUT_UNION(mi=mi)
    input_struct = INPUT(type=0, u=union)  # INPUT_MOUSE = 0
    
    try:
        user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))
    except (AttributeError, OSError) as e:
        logger.error("Failed to send mouse event", error=str(e))

def get_foreground_app(self) -> str:
    """Query foreground window and return its process executable name."""
    if user32 is None:
        return ""
    
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
        
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        import psutil
        try:
            return str(psutil.Process(pid.value).name().lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            return str(title.lower())
    except (AttributeError, OSError) as e:
        logger.error("Failed to get foreground app", error=str(e))
        return ""

def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
    """Move mouse to position."""
    if user32 is None:
        return
    
    try:
        if absolute:
            user32.SetCursorPos(x, y)
        else:
            send_mouse_event(0x0001, x, y)  # MOUSEEVENTF_MOVE
    except (AttributeError, OSError) as e:
        logger.error("Failed to move mouse", error=str(e))

def minimize_active_window(self) -> None:
    """Minimize the active window."""
    if user32 is None:
        return
    
    try:
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
    except (AttributeError, OSError) as e:
        logger.error("Failed to minimize window", error=str(e))
```

**Step 3: Update MyPy Configuration**

Modify `pyproject.toml` to add Windows module overrides:

```toml
[[tool.mypy.overrides]]
module = [
    "gesture_controller.os_integration.windows_controller",
]
# Allow this module to use type: ignore comments for platform-specific code
allow_untyped_calls = true
```

Or alternatively, use inline type ignore comments:

```python
user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))  # type: ignore[attr-defined]
```

---

#### Why Current Fix Attempts Failed

**Issue 1: Platform Detection Missing**
- The code doesn't check if `windll` is available before accessing it
- Running on Linux/macOS CI means `windll` doesn't exist at all
- Type checker runs regardless of platform

**Issue 2: No TYPE_CHECKING Guard**
- Without `TYPE_CHECKING` guards, type information and runtime behavior aren't properly separated
- The type checker sees the same code as runtime, causing conflicts

**Issue 3: Strict Mode Too Aggressive**
- `strict = true` in MyPy disallows any untyped or partially typed code
- Windows-specific modules with incomplete stubs fail

**Issue 4: Version Changes in Dependencies**
- Dependabot PRs updating `actions/checkout` (v4→v7) and `actions/setup-python` (v5→v6) don't directly cause failures
- However, they trigger the same underlying issue: the CI workflow always runs MyPy on all code

---

### SECONDARY ISSUES: Release-Please Workflow Failures

**Severity:** 🟡 MEDIUM  
**Impact:** Blocking automated version releases  
**Workflow File:** `.github/workflows/release-please.yml`

**Root Cause:**
The `release-please` workflow runs **after** the CI workflow. Since CI is failing due to the MyPy errors, the entire workflow run is marked as failed, preventing release-please from executing.

**Evidence:**
All 8 release-please failures occur on commits that also have failed CI runs:
- Run 28855935046 (CI) → 28855935039 (release-please) ✗
- Run 28854940258 (CI) → 28854940205 (release-please) ✗
- Run 28853001378 (CI) → 28853001414 (release-please) ✗

**Solution:**
Fix the CI failures first. Once MyPy errors are resolved, release-please will automatically succeed.

---

### TERTIARY ISSUES: Dependabot Pull Request Failures

**Severity:** 🟡 MEDIUM  
**Impact:** Blocking dependency updates  
**Affected PRs:**
- PR #1: `actions/checkout` v4 → v7
- PR #2: `actions/setup-python` v5 → v6
- PR #3: `pytest-cov` v4.1.0 → v7.1.0

**Root Cause:**
Each Dependabot PR triggers the CI workflow. Since the CI workflow has the MyPy error, all Dependabot PRs fail their checks regardless of whether the dependency change itself is valid.

**Why This is a Problem:**
1. **False negatives:** The PRs aren't failing because of the dependency update; they're failing because of pre-existing code issues
2. **Blocked updates:** Important security and feature updates can't be merged
3. **Technical debt:** Over time, outdated dependencies accumulate

**Solution:**
Fix the underlying CI issue. Once MyPy passes, all Dependabot PRs will pass their checks.

---

## Implementation Roadmap

### Phase 1: Immediate Fix (30 minutes)

**Option A: Quick Workaround (Recommended for immediate relief)**

Add type ignore comments to all problematic lines in `windows_controller.py`:

```python
# Line 190
ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))  # type: ignore[attr-defined]

# Line 197
ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))  # type: ignore[attr-defined]

# Lines 268, 280, 284, 288, 292, 302, 304 - apply similar pattern
```

**Pros:**
- Immediate fix
- Minimal code changes
- Doesn't require new files

**Cons:**
- Less type-safe
- Comments scattered throughout code
- Makes code less maintainable

---

**Option B: Proper Solution (Recommended for long-term)**

Implement the Windows API stubs wrapper as described in "Detailed Solution" section above.

**Pros:**
- Type-safe
- Platform-aware
- Maintainable
- Follows Python best practices
- Enables future cross-platform improvements

**Cons:**
- Requires more code changes
- Creates new module dependency
- Slightly more complex

---

### Phase 2: Validation

1. Create branch: `fix/windows-api-type-checking`
2. Implement chosen solution
3. Run local tests:
   ```bash
   mypy gesture_controller/
   pytest gesture_controller/tests/ -m "not requires_hardware"
   ```
4. Verify on different platforms (via CI)
5. Create pull request with detailed explanation

### Phase 3: Follow-up Actions

After CI is green:
1. Review and merge all Dependabot PRs
2. Verify release-please workflow executes successfully
3. Update CI documentation with type-checking strategy
4. Consider relaxing strict mode for non-core modules (optional)

---

## Root Cause Analysis Summary

| Issue | Root Cause | Scope | Impact | Solution |
|-------|-----------|-------|--------|----------|
| MyPy `windll` errors | Missing type stubs for `ctypes.windll` on non-Windows | 9 error instances | 100% CI failure rate | Type wrapper or ignore comments |
| Release-please failures | Depends on CI success | 8 workflow runs | No releases published | Fix CI |
| Dependabot PR failures | Triggered CI inherits MyPy errors | 3+ PRs | Blocked updates | Fix CI |
| Platform-specific testing | CI runs on Linux, can't validate Windows code at runtime | Windows module | False negatives | Proper type stubs |

---

## Preventive Measures

### 1. Add Windows-Specific Type Checking
Update CI workflow to skip Windows module type checking on non-Windows runners:

```yaml
- name: Run Mypy Type Checking
  run: |
    mypy gesture_controller/ \
      --exclude="gesture_controller/os_integration/windows_controller.py" \
      --ignore-missing-imports
    # Only type-check windows module on Windows runner
    if [[ "${{ runner.os }}" == "Windows" ]]; then
      mypy gesture_controller/os_integration/windows_controller.py
    fi
```

### 2. Enhanced CI Documentation
Document the type-checking strategy for platform-specific modules in `CONTRIBUTING.md`.

### 3. Pre-commit Hooks
Add local pre-commit hooks to catch type errors before pushing:

```bash
pip install pre-commit mypy
```

### 4. Separate Platform Test Matrix
Consider separating platform-specific tests more clearly.

---

## Success Criteria

Once implemented, verify:
- ✅ All MyPy checks pass on main branch
- ✅ All GitHub Actions workflows complete successfully
- ✅ Dependabot PRs show passing CI checks
- ✅ Release-please workflow executes and creates releases
- ✅ Code coverage remains above 60% (current threshold in CI)
- ✅ No new MyPy errors introduced in future commits

---

## Timeline

| Task | Estimated Time | Priority |
|------|---------------|---------| 
| Quick fix (type ignore comments) | 30 min | P0 |
| Proper fix (stubs module) | 2-3 hours | P0 |
| Update CI workflow | 1 hour | P1 |
| Documentation updates | 1 hour | P2 |
| Preventive measures implementation | 2 hours | P2 |

---

## Appendix: Additional Context

### Current CI Configuration

**File:** `.github/workflows/ci.yml`  
**Lint & Typecheck Job:**
- Runs on: `ubuntu-latest`
- Python: `3.11`
- Type checker: `mypy` with `strict = true`
- Command: `mypy gesture_controller/`

**Test Matrix:**
- OS: `ubuntu-latest`, `macos-latest`, `windows-latest`
- Python: `3.11`, `3.12`, `3.13`

**Type Checking Configuration**

**File:** `pyproject.toml` (lines 81-120)

```toml
[tool.mypy]
python_version = "3.11"
exclude = "gesture_controller/tests/"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
no_implicit_reexport = true
strict_equality = true
strict_optional = true

[[tool.mypy.overrides]]
module = [
    "mediapipe.*",
    "cv2.*",
    "numba.*",
    "jsonschema.*",
    "Quartz.*",
    "AppKit.*",
    "evdev.*",
    "psutil.*",
    "watchdog.*",
    "AVFoundation.*",
    "ApplicationServices.*",
]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = [
    "gesture_controller.gui.*",
    "gesture_controller.os_integration.macos_controller",
    "gesture_controller.os_integration.linux_controller",
    "gesture_controller.plugins.*",
]
ignore_errors = true
```

**Key Observation:** There's already a pattern of module-level overrides for platform-specific modules! The fix should follow this existing pattern.

---

## References

- [MyPy Documentation: Platform-Specific Type Checking](https://mypy.readthedocs.io/en/stable/common_issues.html#issues-with-platform-specific-imports)
- [PEP 484: Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [ctypes Documentation](https://docs.python.org/3/library/ctypes.html)
- [Python Typeshed: ctypes stubs](https://github.com/python/typeshed/blob/main/stdlib/ctypes/__init__.pyi)

---

**Report Generated:** July 8, 2026  
**Next Review Date:** After fixes are implemented  
**Owner:** CI/CD Infrastructure Team
