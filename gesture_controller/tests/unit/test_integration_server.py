import json
import urllib.request
import urllib.error
import time
import pytest

from gesture_controller.core.event_bus import EventBus
from gesture_controller.core.integration_server import IntegrationServer
from gesture_controller.models.data_types import GestureEvent


def _auth_headers(token: str) -> dict[str, str]:
    """Return request headers carrying the API token via Authorization: Bearer.

    Audit fix MAE-V2-OSS-001: tests must use the Authorization header rather
    than the deprecated ``?token=`` query parameter (which leaks via shell
    history, process listings, and proxy logs).
    """
    return {"Authorization": f"Bearer {token}"}


def test_integration_server_endpoints() -> None:
    bus = EventBus()
    # Instantiate server on alternate port
    server = IntegrationServer(bus, host="127.0.0.1", port=8766, token="secret")
    server.start()

    # Wait for server thread to spawn
    time.sleep(0.5)

    # Test 1: GET /api/status with valid token (Authorization: Bearer)
    try:
        url = "http://127.0.0.1:8766/api/status"
        req = urllib.request.Request(url, headers=_auth_headers("secret"), method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("status") == "running"
    except Exception as e:
        server.stop()
        pytest.fail(f"HTTP GET status failed: {e}")

    # Test 2: GET /api/status with invalid token (should raise HTTPError 401)
    url_bad = "http://127.0.0.1:8766/api/status"
    req_bad = urllib.request.Request(url_bad, headers=_auth_headers("wrong"), method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_bad, timeout=1.0)
    assert exc_info.value.code == 401

    # Test 3: POST /api/trigger
    url_trigger = "http://127.0.0.1:8766/api/trigger"
    payload = json.dumps({"gesture": "SwipeLeft"}).encode("utf-8")
    headers = _auth_headers("secret")
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url_trigger, data=payload, headers=headers, method="POST")

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
    url_state = "http://127.0.0.1:8766/api/state"
    payload_state = json.dumps({"paused": True}).encode("utf-8")
    headers_state = _auth_headers("secret")
    headers_state["Content-Type"] = "application/json"
    req_state = urllib.request.Request(
        url_state, data=payload_state, headers=headers_state, method="POST"
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
