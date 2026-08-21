"""Audit-remediation tests for the Maestro broker and updater.

These tests verify the audit fixes documented in ``AUDIT_REMEDIATION.md``:

- MAE-SEC-001: ``verify_peer`` fail-closes on Windows instead of fail-opening.
- MAE-SEC-008: ``apply_update`` rejects zip-slip / path-traversal members.
- MAE-SEC-006: ``run_applescript`` rejects ``do shell script`` patterns.
- MAE-SEC-002: ``_is_placeholder_root`` detects synthetic Ed25519 keys.
- MAE-SEC-003: ``os.symlink`` is no longer monkey-patched globally.
- MAE-SEC-004: WebSocket ``"null"`` Origin is no longer allowed.
- MAE-SEC-005: CLI sends token via ``Authorization: Bearer`` header.
"""

import json
import os
import platform
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# --- MAE-SEC-001 ----------------------------------------------------------


def test_verify_peer_fail_closed_on_windows_exception(monkeypatch):
    """Audit fix MAE-SEC-001: Windows verify_peer returns False on exception.

    Previously it returned True (fail-open), allowing any local Windows
    process to connect to the named pipe and inject arbitrary input.
    """
    if platform.system() != "Windows":
        pytest.skip("Windows-specific test")

    from gesture_controller.os_integration.broker import verify_peer

    # Mock win32security.OpenProcessToken to raise OSError (simulating a
    # pywin32 install without post-install step, or a race where the
    # client process has exited).
    fake_conn = MagicMock()
    fake_conn.fileno.return_value = 0

    with patch.dict(sys.modules, {"win32security": MagicMock(), "win32api": MagicMock()}):
        import win32security  # type: ignore[import-untyped]

        win32security.OpenProcessToken.side_effect = OSError("simulated failure")
        result = verify_peer(fake_conn)

    assert result is False, (
        "verify_peer must fail CLOSED on Windows when OpenProcessToken raises. "
        "Previously it returned True (fail-open), which was MAE-SEC-001."
    )


def test_verify_peer_fail_closed_on_non_windows():
    """Audit fix MAE-SEC-001: confirm the non-Windows path already fail-closes.

    This is a regression guard — the non-Windows path was already correct
    in the original code, and we want to keep it that way.
    """
    if platform.system() == "Windows":
        pytest.skip("Non-Windows-specific test")

    from gesture_controller.os_integration.broker import verify_peer

    # Pass a non-socket object that will raise during fileno()/fromfd()
    fake_conn = MagicMock()
    fake_conn.fileno.side_effect = OSError("simulated failure")

    result = verify_peer(fake_conn)
    assert result is False


# --- MAE-SEC-002 ----------------------------------------------------------


def test_is_placeholder_root_detects_synthetic_keys():
    """Audit fix MAE-SEC-002: placeholder Ed25519 keys are detected."""
    from gesture_controller.core.updater import _is_placeholder_root, BOOTSTRAP_ROOT

    # The shipped BOOTSTRAP_ROOT must be flagged as placeholder.
    assert _is_placeholder_root(BOOTSTRAP_ROOT) is True, (
        "BOOTSTRAP_ROOT must be detected as placeholder (its keyids share "
        "a 30-byte suffix). If this assertion fails, either the keys were "
        "rotated to real keys (good — remove the placeholder check) or "
        "the detection heuristic is broken."
    )


def test_is_placeholder_root_passes_real_keys():
    """Audit fix MAE-SEC-002: real Ed25519 keys are not flagged."""
    from gesture_controller.core.updater import _is_placeholder_root

    # Five distinct, non-colliding-suffix keyids — clearly not placeholder.
    real_root = {
        "signed": {
            "roles": {
                "root": {
                    "keyids": [
                        "aa1111111111111111111111111111111111111111111111111111111111111a",
                        "bb2222222222222222222222222222222222222222222222222222222222222b",
                        "cc3333333333333333333333333333333333333333333333333333333333333c",
                        "dd4444444444444444444444444444444444444444444444444444444444444d",
                        "ee5555555555555555555555555555555555555555555555555555555555555e",
                    ]
                }
            }
        }
    }
    assert _is_placeholder_root(real_root) is False


# --- MAE-SEC-003 ----------------------------------------------------------


def test_os_symlink_not_monkey_patched():
    """Audit fix MAE-SEC-003: ``os.symlink`` is the original stdlib function.

    Previously the updater module monkey-patched ``os.symlink`` globally
    on import, which affected every other module in the same process.
    """
    import gesture_controller.core.updater as updater_module

    # Importing the updater module must NOT replace os.symlink.
    # The original os.symlink should still be in place (or None on
    # platforms that don't support symlinks).
    original = getattr(os, "symlink", None)
    assert original is not None or platform.system() == "Windows"

    # The updater module should expose secure_symlink as a regular function
    # that the caller invokes explicitly, rather than mutating os.symlink.
    assert hasattr(updater_module, "secure_symlink")
    assert callable(updater_module.secure_symlink)


# --- MAE-SEC-004 ----------------------------------------------------------


def test_websocket_null_origin_not_allowed():
    """Audit fix MAE-SEC-004: WebSocket ``"null"`` Origin is rejected.

    Previously ``"null"`` was in the allowed_origins set, which is sent
    by sandboxed iframes, ``file://`` pages, and privacy tools — opening
    a CSWSH (cross-site WebSocket hijacking) vector.
    """
    # We can't easily spin up the full IntegrationServer in a unit test,
    # but we can verify the allowed_origins set directly by inspecting
    # the source. This is a regression guard.
    source = Path("gesture_controller/core/integration_server.py").read_text(encoding="utf-8")
    if platform.system() == "Windows":
        source = source.replace("\\", "/")
    # The literal string '"null"' as an allowed origin must not appear
    # in the WebSocket handshake code path.
    assert '"null"' not in source, (
        "WebSocket allowed_origins must not contain 'null' — "
        "it is a CSWSH vector (audit fix MAE-SEC-004)."
    )


# --- MAE-SEC-005 ----------------------------------------------------------


def test_cli_uses_authorization_header_not_query_param():
    """Audit fix MAE-SEC-005: CLI sends token via Authorization header.

    Previously the token was transmitted as ``?token=...`` in the URL,
    leaking via shell history, process listings, and browser Referer.
    """
    source = Path("gesture_controller/cli/cli.py").read_text(encoding="utf-8")
    # The _make_api_request function should NOT embed the token in the URL.
    # We check that the URL line does not contain ``?token=``.
    for line in source.splitlines():
        if 'url = f"http://127.0.0.1:8765' in line:
            assert "?token=" not in line, (
                "CLI must not embed the API token in the URL query string "
                "(audit fix MAE-SEC-005)."
            )
    # And the Authorization header must be set.
    assert "Authorization" in source or "Bearer" in source, (
        "CLI must send the token via the Authorization: Bearer header " "(audit fix MAE-SEC-005)."
    )


# --- MAE-SEC-006 ----------------------------------------------------------


def test_applescript_bridge_rejects_do_shell_script():
    """Audit fix MAE-SEC-006: ``do shell script`` is blocked.

    Previously ``run_applescript`` was an unguarded subprocess wrapper
    that could execute arbitrary bash via ``do shell script "..."``.
    """
    from gesture_controller.os_integration.applescript_bridge import (
        AppleScriptSecurityError,
        _validate_applescript,
    )

    with pytest.raises(AppleScriptSecurityError, match="forbidden pattern"):
        _validate_applescript('do shell script "rm -rf /"')

    # Variations must also be caught.
    with pytest.raises(AppleScriptSecurityError):
        _validate_applescript('do Shell Script "echo pwned"')

    with pytest.raises(AppleScriptSecurityError):
        _validate_applescript("POSIX path of (path to home folder)")


def test_applescript_bridge_rejects_oversized_script():
    """Audit fix MAE-SEC-006: scripts longer than 8 KiB are rejected."""
    from gesture_controller.os_integration.applescript_bridge import (
        AppleScriptSecurityError,
        _validate_applescript,
        MAX_APPLESCRIPT_LENGTH,
    )

    big_script = "x" * (MAX_APPLESCRIPT_LENGTH + 1)
    with pytest.raises(AppleScriptSecurityError, match="maximum length"):
        _validate_applescript(big_script)


def test_applescript_bridge_accepts_safe_script():
    """Audit fix MAE-SEC-006: legitimate AppleScript still passes."""
    from gesture_controller.os_integration.applescript_bridge import _validate_applescript

    # A simple "get the current volume" script should pass.
    _validate_applescript("get volume settings")
    _validate_applescript('tell application "Finder" to count windows')


# --- MAE-SEC-008 ----------------------------------------------------------


def test_apply_update_rejects_zip_slip(tmp_path):
    """Audit fix MAE-SEC-008: zip-slip / path-traversal members are rejected.

    Previously ``extractall()`` was called directly, allowing a malicious
    archive to write outside the extraction directory.
    """
    from gesture_controller.core.updater import apply_update

    # Build a malicious zip with a path-traversal member.
    zip_path = tmp_path / "evil.zip"
    extract_dir = tmp_path / "extract"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../../etc/cron.d/evil", "payload")

    # The apply_update call must refuse to extract and return False.
    result = apply_update(zip_path, extract_dir=extract_dir)
    assert result is False, "apply_update must reject zip-slip members (audit fix MAE-SEC-008)."

    # The traversal target must not have been written.
    cron_evil = tmp_path.parent.parent / "etc" / "cron.d" / "evil"
    assert (
        not cron_evil.exists()
    ), "Path-traversal member must not have been written outside extract_dir."


def test_apply_update_rejects_absolute_path(tmp_path):
    """Audit fix MAE-SEC-008: absolute-path members are rejected."""
    from gesture_controller.core.updater import apply_update

    zip_path = tmp_path / "evil.zip"
    extract_dir = tmp_path / "extract"

    with zipfile.ZipFile(zip_path, "w") as zf:
        # Absolute path member.
        zf.writestr("/etc/cron.d/evil", "payload")

    result = apply_update(zip_path, extract_dir=extract_dir)
    assert result is False


def test_apply_update_accepts_safe_zip(tmp_path):
    """Audit fix MAE-SEC-008: legitimate archives still extract successfully."""
    from gesture_controller.core.updater import apply_update

    zip_path = tmp_path / "good.zip"
    extract_dir = tmp_path / "extract"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("README.txt", "hello")
        zf.writestr("subdir/file.txt", "world")

    result = apply_update(zip_path, extract_dir=extract_dir)
    assert result is True
    assert (extract_dir / "README.txt").read_text() == "hello"
    assert (extract_dir / "subdir" / "file.txt").read_text() == "world"


# --- MAE-SEC-009 / MAE-SEC-010 --------------------------------------------


def test_ci_does_not_mask_pip_audit():
    """Audit fix MAE-SEC-009: ``|| true`` removed from pip-audit step."""
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    # The pip-audit step must not be masked with ``|| true``.
    # Find the "Run Pip-Audit" step and verify the line below does not mask.
    assert "pip-audit --strict" in ci, "pip-audit should run with --strict (audit fix MAE-SEC-009)."
    assert (
        "pip-audit || true" not in ci
    ), "pip-audit must NOT be masked with || true (audit fix MAE-SEC-009)."


def test_ci_does_not_mask_pytest():
    """Audit fix MAE-SEC-010: ``|| true`` removed from pytest step."""
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    # The pytest step must not be masked with ``|| true``.
    pytest_line = next(
        (line for line in ci.splitlines() if "python -m pytest" in line and "-m " in line),
        None,
    )
    assert pytest_line is not None
    assert (
        "|| true" not in pytest_line
    ), "pytest must NOT be masked with || true (audit fix MAE-SEC-010)."


# --- MAE-SEC-017 ----------------------------------------------------------


def test_vosk_download_refuses_unverified(tmp_path, monkeypatch, capsys):
    """Audit fix MAE-SEC-017: production download-voice-model refuses unverified.

    Since the maintainer has not yet pinned the real SHA-256 of the upstream
    Vosk model, the production command must refuse to download rather than
    silently accept an unverified model.
    """
    # The CLI handler reads VOSK_MODEL_SHA256 which is currently "".
    # We don't actually want to spawn a network download — just verify
    # that the command refuses before any network call.
    import argparse
    from gesture_controller.cli.cli import main

    monkeypatch.setattr(sys, "argv", ["maestro", "download-voice-model"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    # The command must exit non-zero (we use sys.exit(1)).
    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "SHA-256" in captured.err or "SHA-256" in captured.out, (
        "The 'not pinned' error message must mention SHA-256 " "(audit fix MAE-SEC-017)."
    )
