"""Cross-platform regression test for Windows ``verify_peer`` (MAE-V2-INFO-003).

Audit fix C5: previously ``test_verify_peer_fail_closed_on_windows_exception``
in ``test_audit_remediation.py`` skipped on non-Windows platforms, which meant
the Windows fail-closed path (audit fix MAE-SEC-001) was never actually
exercised in CI on Linux/macOS runners. This file mocks the Windows-only
imports (``win32security``, ``win32api``, ``ctypes.windll``) so the Windows
code path runs on every CI runner, then asserts that ``verify_peer``
returns ``False`` when ``win32security.OpenProcessToken`` raises ``OSError``.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_verify_peer_windows_fail_closed_on_openprocess_token_oserror():
    """MAE-SEC-001 regression: Windows ``verify_peer`` returns False on OSError.

    Previously the Windows path returned ``True`` if any exception was raised
    during the SID lookup — i.e., it fail-opened. That allowed any local
    Windows process to connect to the named pipe and inject arbitrary input
    whenever pywin32 was not importable or any of the win32security calls
    raised. The fix (MAE-SEC-001) fail-closes by returning ``False``.

    This test runs on every platform (Linux/macOS CI included) by mocking
    ``platform.system`` to return ``"Windows"`` and stubbing the Windows-only
    modules.
    """
    # Stub the Windows-only modules BEFORE we import verify_peer's body.
    # The verify_peer function does its imports lazily (inside the if-branch),
    # so we patch sys.modules and platform.system together.
    fake_win32security = MagicMock()
    fake_win32api = MagicMock()

    # The fail-closed path under test: OpenProcessToken raises OSError
    # (simulating a pywin32 install without the post-install step, or a
    # race where the client process has exited between accept() and the
    # OpenProcessToken call).
    fake_win32security.OpenProcessToken.side_effect = OSError("simulated failure")

    fake_conn = MagicMock()
    fake_conn.fileno.return_value = 0

    with (
        patch.dict(
            sys.modules,
            {
                "win32security": fake_win32security,
                "win32api": fake_win32api,
            },
        ),
        patch("platform.system", return_value="Windows"),
    ):
        # Re-import verify_peer lazily so it picks up the patched platform.
        from gesture_controller.os_integration.broker import verify_peer

        result = verify_peer(fake_conn)

    assert result is False, (
        "verify_peer must fail CLOSED on Windows when OpenProcessToken raises "
        "OSError. Previously it returned True (fail-open), which was "
        "MAE-SEC-001 — any local Windows process could connect to the named "
        "pipe and inject arbitrary input whenever pywin32 was unavailable."
    )

    # Sanity check: OpenProcessToken must actually have been invoked so we
    # know we exercised the Windows code path (rather than accidentally
    # falling through to the Unix branch).
    fake_win32security.OpenProcessToken.assert_called()


def test_verify_peer_windows_fail_closed_on_importerror():
    """MAE-SEC-001 regression: Windows path returns False when pywin32 missing.

    A common Windows deployment failure mode is that pywin32 is installed
    but the post-install step (``python Scripts/pywin32_postinstall.py``)
    was skipped, leaving ``win32security`` importable but unusable. This
    test simulates the more severe case where ``win32security`` itself
    cannot be imported — the broker must still fail closed.
    """
    fake_conn = MagicMock()
    fake_conn.fileno.return_value = 0

    # Simulate ImportError on the win32security import by removing it from
    # sys.modules and ensuring the real import fails.
    with (
        patch.dict(sys.modules, {"win32security": None, "win32api": None}),
        patch("platform.system", return_value="Windows"),
    ):
        from gesture_controller.os_integration.broker import verify_peer

        result = verify_peer(fake_conn)

    assert result is False, (
        "verify_peer must fail CLOSED on Windows when win32security cannot "
        "be imported. Returning True in this state would have fail-opened "
        "the broker to any local process — MAE-SEC-001."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
