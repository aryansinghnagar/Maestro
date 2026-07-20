import pytest
import secrets
import socket
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from gesture_controller.core.integration_server import get_or_create_api_token, IntegrationServer
from gesture_controller.os_integration.broker import verify_peer
from gesture_controller.plugins.plugin_loader import PluginLoader, PluginLoadError


def test_api_token_generation_and_chmod(tmp_path, monkeypatch):
    """Test api token generation, persistence, and restricted permissions."""
    token_file = tmp_path / "api_token"
    monkeypatch.setattr("gesture_controller.core.paths.api_token_path", lambda: token_file)

    tok1 = get_or_create_api_token()
    assert len(tok1) >= 32
    assert token_file.exists()

    tok2 = get_or_create_api_token()
    assert tok1 == tok2

    # Check file permissions on non-Windows platforms
    import platform

    if platform.system() != "Windows":
        mode = token_file.stat().st_mode & 0o777
        assert mode == 0o600


def test_broker_verify_peer_same_uid():
    """Verify that socket connection from same UID succeeds."""
    import platform

    if platform.system() == "Windows":
        pytest.skip("Socket credential verification not applicable on Windows")

    s1, s2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        assert verify_peer(s2) is True
    finally:
        s1.close()
        s2.close()


def test_ast_sandbox_blocked_builtins(tmp_path):
    """Verify that plugin loader AST scanner blocks eval, exec, and __import__."""
    loader = PluginLoader(MagicMock())

    # Test eval block
    bad_code_eval = "x = eval('1+1')"
    p = tmp_path / "bad_eval.py"
    p.write_text(bad_code_eval, encoding="utf-8")
    with pytest.raises(PluginLoadError, match="Use of blocked security-critical identifier"):
        loader._scan_ast_for_unsafe_code(p, [])

    # Test exec block
    bad_code_exec = "exec('import os')"
    p = tmp_path / "bad_exec.py"
    p.write_text(bad_code_exec, encoding="utf-8")
    with pytest.raises(PluginLoadError, match="Use of blocked security-critical identifier"):
        loader._scan_ast_for_unsafe_code(p, [])

    # Test __import__ block
    bad_code_import = "x = __import__('os')"
    p = tmp_path / "bad_import.py"
    p.write_text(bad_code_import, encoding="utf-8")
    with pytest.raises(PluginLoadError, match="Use of blocked security-critical identifier"):
        loader._scan_ast_for_unsafe_code(p, [])


def test_ast_sandbox_blocked_from_imports(tmp_path):
    """Verify that plugin loader AST scanner blocks ImportFrom bypasses."""
    loader = PluginLoader(MagicMock())

    # Test from subprocess import Popen
    bad_code = "from subprocess import Popen"
    p = tmp_path / "bad_sub.py"
    p.write_text(bad_code, encoding="utf-8")
    with pytest.raises(PluginLoadError, match="Unauthorized import from"):
        loader._scan_ast_for_unsafe_code(p, [])

    # Test from builtins import eval
    bad_code_builtin = "from builtins import eval"
    p = tmp_path / "bad_builtin.py"
    p.write_text(bad_code_builtin, encoding="utf-8")
    with pytest.raises(PluginLoadError, match="Unauthorized import from"):
        loader._scan_ast_for_unsafe_code(p, [])


def test_ast_sandbox_blocked_attribute_access(tmp_path):
    """Verify that plugin loader AST scanner blocks attribute access to blocked attributes."""
    loader = PluginLoader(MagicMock())

    # Test accessing __builtins__.__import__
    bad_code = "getattr(x, '__import__')"
    p = tmp_path / "bad_attr.py"
    p.write_text(bad_code, encoding="utf-8")
    with pytest.raises(PluginLoadError, match="Use of blocked security-critical identifier"):
        loader._scan_ast_for_unsafe_code(p, [])
