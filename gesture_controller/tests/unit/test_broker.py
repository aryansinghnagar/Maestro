import os
import sys
import json
import time
import shutil
import tempfile
import hashlib
import platform
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from gesture_controller.os_integration.broker import (
    RateLimiter,
    AuditLogger,
    InjectionBrokerServer,
    BrokerClientController,
    get_broker_address,
    get_broker_family,
)


def test_rate_limiter_global() -> None:
    limiter = RateLimiter()
    current_time = 100.0
    
    def mock_time() -> float:
        nonlocal current_time
        return current_time

    with patch("time.monotonic", mock_time):
        # We advance time by 15ms per call to bypass burst rate limit (10 actions in 100ms)
        # but 30 actions in 450ms is still within 1 second global window.
        for _ in range(30):
            assert limiter.check_and_record(None) is True
            current_time += 0.015
        assert limiter.check_and_record(None) is False


def test_rate_limiter_burst() -> None:
    limiter = RateLimiter()
    current_time = 100.0
    
    def mock_time() -> float:
        nonlocal current_time
        return current_time

    with patch("time.monotonic", mock_time):
        # 10 actions in 100ms burst window. We do 10 calls in the same instant.
        for _ in range(10):
            assert limiter.check_and_record(None) is True
        assert limiter.check_and_record(None) is False


def test_rate_limiter_per_gesture() -> None:
    limiter = RateLimiter()
    current_time = 100.0
    
    def mock_time() -> float:
        nonlocal current_time
        return current_time

    with patch("time.monotonic", mock_time):
        # 5 actions/sec limit per-gesture.
        for _ in range(5):
            assert limiter.check_and_record("gesture_1") is True
            current_time += 0.015
        assert limiter.check_and_record("gesture_1") is False
        assert limiter.check_and_record("gesture_2") is True


def test_audit_logger_tamper_evident() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    log_path = temp_dir / "audit.log"
    
    logger = AuditLogger(log_path)
    logger.log("test_event_1", {"data": "val1"})
    logger.log("test_event_2", {"data": "val2"})
    logger.log("test_event_3", {"data": "val3"})

    # Parse and verify the hash chain
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    assert len(lines) == 3
    
    prev_hash = "0" * 64
    for line in lines:
        entry = json.loads(line)
        assert entry["prev_hash"] == prev_hash
        
        # Verify hash matches SHA256 of entry without the "hash" field itself
        chk_entry = entry.copy()
        h = chk_entry.pop("hash")
        entry_json = json.dumps(chk_entry, sort_keys=True)
        expected_hash = hashlib.sha256(entry_json.encode("utf-8")).hexdigest()
        assert h == expected_hash
        prev_hash = h
        
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_broker_address() -> str:  # type: ignore[misc]
    if platform.system() == "Windows":
        yield r'\\.\pipe\test_maestro_broker_pipe_' + str(int(time.time()))
    else:
        temp_dir = tempfile.mkdtemp()
        address = os.path.join(temp_dir, "test_broker.sock")
        yield address
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def test_broker_server_client_flow(temp_broker_address: str) -> None:
    # 1. Start the server in a background thread
    server = InjectionBrokerServer(address=temp_broker_address)
    
    # Mock the underlying controller methods
    mock_ctrl = MagicMock()
    server.controller = mock_ctrl
    
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    
    # Wait for listener to initialize
    time.sleep(0.2)
    
    try:
        # Patch address and family function responses
        with (
            patch("gesture_controller.os_integration.broker.get_broker_address", return_value=temp_broker_address),
            patch("gesture_controller.os_integration.broker.get_broker_family", return_value=server.family)
        ):
            client = BrokerClientController()
            
            # 2. Test input action routing
            client.key_press("a", modifiers=["ctrl"])
            # Wait for IPC roundtrip
            time.sleep(0.05)
            mock_ctrl.key_press.assert_called_once_with("a", modifiers=["ctrl"])
            
            # 3. Test active gesture tracking context
            client.set_active_gesture("SwipeLeft")
            client.key_release("b")
            time.sleep(0.05)
            mock_ctrl.key_release.assert_called_once_with("b")
            
            # 4. Test Esc x 3 kill switch
            assert server.kill_switch_active is False
            client.key_press("escape")
            client.key_press("escape")
            client.key_press("escape")
            time.sleep(0.05)
            assert server.kill_switch_active is True
            
            # 5. Verify action is blocked when kill switch is active
            mock_ctrl.key_press.reset_mock()
            client.key_press("c")
            time.sleep(0.05)
            mock_ctrl.key_press.assert_not_called()
            
    finally:
        server.stop()
