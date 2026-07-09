import json
import urllib.request
import urllib.error
import time
import pytest

from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.integration_server import IntegrationServer
from gesture_controller.models.data_types import GestureEvent


def test_integration_server_endpoints() -> None:
    bus = EventBus()
    # Instantiate server on alternate port
    server = IntegrationServer(bus, host="127.0.0.1", port=8766, token="secret")
    server.start()
    
    # Wait for server thread to spawn
    time.sleep(0.5)
    
    # Test 1: GET /api/status with valid token
    try:
        url = "http://127.0.0.1:8766/api/status?token=secret"
        with urllib.request.urlopen(url, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("status") == "running"
    except Exception as e:
        server.stop()
        pytest.fail(f"HTTP GET status failed: {e}")

    # Test 2: GET /api/status with invalid token (should raise HTTPError 401)
    url_bad = "http://127.0.0.1:8766/api/status?token=wrong"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url_bad, timeout=1.0)
    assert exc_info.value.code == 401

    # Test 3: POST /api/trigger
    url_trigger = "http://127.0.0.1:8766/api/trigger?token=secret"
    payload = json.dumps({"gesture": "SwipeLeft"}).encode("utf-8")
    req = urllib.request.Request(
        url_trigger,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    triggered_gestures = []
    def on_trigger(event: GestureEvent) -> None:
        triggered_gestures.append(event.gesture_name)
    bus.subscribe("gesture_triggered", on_trigger)
    
    try:
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("status") == "ok"
    except Exception as e:
        server.stop()
        pytest.fail(f"HTTP POST trigger failed: {e}")
        
    # Wait for event bus propagation
    time.sleep(0.1)
    assert "SwipeLeft" in triggered_gestures

    # Test 4: POST /api/state to pause/resume
    url_state = "http://127.0.0.1:8766/api/state?token=secret"
    payload_state = json.dumps({"paused": True}).encode("utf-8")
    req_state = urllib.request.Request(
        url_state,
        data=payload_state,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    pause_events = []
    def on_pause(paused: bool) -> None:
        pause_events.append(paused)
    bus.subscribe("engine_pause_requested", on_pause)
    
    try:
        with urllib.request.urlopen(req_state, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("paused") is True
    except Exception as e:
        server.stop()
        pytest.fail(f"HTTP POST state failed: {e}")
        
    time.sleep(0.1)
    assert True in pause_events

    server.stop()
