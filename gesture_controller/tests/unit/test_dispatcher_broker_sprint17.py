"""Sprint 17 — ActionDispatcher & RateLimiter deep-coverage tests.

Targets:
  gesture_controller/os_integration/action_dispatcher.py  (was 69%)
  gesture_controller/os_integration/broker.py             (was 62%)

New branches exercised:
ActionDispatcher:
  - _execute with malformed action string (no colon separator)
  - _execute_os with unknown OS action
  - _execute_media with unknown Media action
  - _execute_scroll with invalid (non-integer) delta
  - _resolve_action with auto_detect_app=False
  - _resolve_action with _default profile fallback
  - _resolve_action with no matching profile and no _default
  - _classify_app for all 6 app categories + unknown
  - MouseClick routing
  - SwitchWindow and ShowDesktop OS actions
  - Media Next / Previous / VolumeUp / VolumeDown
  - set_active_gesture context manager in _on_gesture

RateLimiter:
  - Global window resets after 1 second
  - Burst window resets after 0.1 second
  - Per-gesture window resets after 1 second
  - None gesture_id skips per-gesture tracking
  - Multiple different gestures independent per-gesture limits

AuditLogger:
  - Resumes hash chain from existing log
  - Thread-safe concurrent writes
  - Multiple events produce correct chain of length N
"""
from __future__ import annotations

import json
import time
import hashlib
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from gesture_controller.os_integration.action_dispatcher import ActionDispatcher
from gesture_controller.models.data_types import GestureEvent
from gesture_controller.core.event_bus import EventBus
from gesture_controller.os_integration.broker import RateLimiter, AuditLogger


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_event(gesture="TestGesture", action="OS:MinimizeActiveWindow") -> GestureEvent:
    return GestureEvent(
        gesture_name=gesture,
        gesture_type="dynamic",
        action=action,
        confidence=1.0,
        hand="Right",
        timestamp=0.0,
    )


def _make_dispatcher(action_map: dict | None = None, auto_detect: bool = True):
    """Build an ActionDispatcher with a mocked controller and optional profile map."""
    controller = MagicMock()
    controller.get_foreground_app.return_value = "unknown.exe"
    config = MagicMock()
    config.get.side_effect = lambda k, default=None: {
        "profiles.auto_detect_app": auto_detect,
        "profiles": {"auto_detect_app": auto_detect},
    }.get(k, default)
    bus = EventBus()
    with patch.object(
        ActionDispatcher, "_load_profiles", return_value=action_map or {}
    ):
        dispatcher = ActionDispatcher(controller, config, bus)
    return dispatcher, controller, bus


# ═══════════════════════════════════════════════════════════════════════════════
# ActionDispatcher — _execute branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionDispatcherExecute:

    def test_malformed_action_no_colon_skips_execution(self) -> None:
        """_execute with no ':' separator logs error and performs no controller call."""
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("BAD_FORMAT_NO_COLON")
        controller.minimize_active_window.assert_not_called()
        controller.key_combo.assert_not_called()

    def test_unknown_action_type_skips_execution(self) -> None:
        """_execute with unrecognised type logs error and performs no controller call."""
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Widget:FlyAway")
        controller.minimize_active_window.assert_not_called()

    def test_execute_os_minimize(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("OS:MinimizeActiveWindow")
        controller.minimize_active_window.assert_called_once()

    def test_execute_os_switch_window(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("OS:SwitchWindow")
        controller.switch_window.assert_called_once()

    def test_execute_os_show_desktop(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("OS:ShowDesktop")
        controller.show_desktop.assert_called_once()

    def test_execute_os_unknown_action(self) -> None:
        """Unknown OS action name should not call any controller method."""
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("OS:InvisibilityCloak")
        controller.minimize_active_window.assert_not_called()
        controller.switch_window.assert_not_called()
        controller.show_desktop.assert_not_called()

    def test_execute_mouse_click_left(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("MouseClick:left")
        controller.mouse_click.assert_called_once_with(button="left")

    def test_execute_mouse_click_right(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("MouseClick:right")
        controller.mouse_click.assert_called_once_with(button="right")

    def test_execute_scroll_positive(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("MouseScroll:5")
        controller.mouse_scroll.assert_called_once_with(delta_y=5)

    def test_execute_scroll_negative(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("MouseScroll:-3")
        controller.mouse_scroll.assert_called_once_with(delta_y=-3)

    def test_execute_scroll_invalid_delta(self) -> None:
        """Non-integer scroll delta logs error, no controller call."""
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("MouseScroll:fast")
        controller.mouse_scroll.assert_not_called()

    def test_execute_media_play_pause(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Media:PlayPause")
        controller.media_play_pause.assert_called_once()

    def test_execute_media_next(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Media:Next")
        controller.media_next.assert_called_once()

    def test_execute_media_previous(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Media:Previous")
        controller.media_previous.assert_called_once()

    def test_execute_media_volume_up(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Media:VolumeUp")
        controller.media_volume_up.assert_called_once()

    def test_execute_media_volume_down(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Media:VolumeDown")
        controller.media_volume_down.assert_called_once()

    def test_execute_media_unknown(self) -> None:
        """Unknown media action should not call any controller method."""
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("Media:Rewind")
        controller.media_play_pause.assert_not_called()
        controller.media_next.assert_not_called()

    def test_execute_keypress_multi_modifier(self) -> None:
        dispatcher, controller, _ = _make_dispatcher()
        dispatcher._execute("KeyPress:Ctrl+Alt+Delete")
        controller.key_combo.assert_called_once_with(["ctrl", "alt", "delete"])


# ═══════════════════════════════════════════════════════════════════════════════
# ActionDispatcher — _resolve_action branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionDispatcherResolveAction:

    def test_auto_detect_off_returns_event_action(self) -> None:
        """When auto_detect_app=False, the raw event.action is used unchanged."""
        dispatcher, controller, bus = _make_dispatcher(auto_detect=False)
        controller.get_foreground_app.return_value = "chrome.exe"
        event = _make_event(gesture="SwipeLeft", action="KeyPress:ArrowLeft")
        bus.publish("gesture_triggered", event)
        time.sleep(0.05)
        # normalize_key("ArrowLeft") → "left" per keycodes.py
        controller.key_combo.assert_called_once_with(["left"])

    def test_default_profile_fallback(self) -> None:
        """With no per-app profile, falls back to _default profile."""
        profiles = {
            "_default": {"SwipeLeft": "KeyPress:Alt+Left"},
        }
        dispatcher, controller, bus = _make_dispatcher(action_map=profiles)
        controller.get_foreground_app.return_value = "notepad.exe"
        event = _make_event(gesture="SwipeLeft", action="KeyPress:ArrowLeft")
        bus.publish("gesture_triggered", event)
        time.sleep(0.05)
        controller.key_combo.assert_called_once_with(["alt", "left"])
        assert event.app_profile == "_default"

    def test_per_app_profile_overrides_default(self) -> None:
        """Per-app profile takes precedence over _default."""
        profiles = {
            "vlc.exe": {"SwipeRight": "Media:Next"},
            "_default": {"SwipeRight": "KeyPress:ArrowRight"},
        }
        dispatcher, controller, bus = _make_dispatcher(action_map=profiles)
        controller.get_foreground_app.return_value = "vlc.exe"
        event = _make_event(gesture="SwipeRight", action="KeyPress:ArrowRight")
        bus.publish("gesture_triggered", event)
        time.sleep(0.05)
        controller.media_next.assert_called_once()
        assert event.app_profile == "vlc.exe"

    def test_no_profile_match_uses_event_action(self) -> None:
        """When no profile matches and no _default, raw event.action is used."""
        profiles: dict = {}
        dispatcher, controller, bus = _make_dispatcher(action_map=profiles)
        controller.get_foreground_app.return_value = "unknown.exe"
        event = _make_event(gesture="Fist", action="OS:MinimizeActiveWindow")
        bus.publish("gesture_triggered", event)
        time.sleep(0.05)
        controller.minimize_active_window.assert_called_once()

    def test_gesture_not_in_per_app_profile_falls_to_default(self) -> None:
        """Gesture not in per-app profile correctly falls to _default."""
        profiles = {
            "chrome.exe": {"SwipeLeft": "KeyPress:Ctrl+Shift+Tab"},
            "_default": {"SwipeUp": "OS:ShowDesktop"},
        }
        dispatcher, controller, bus = _make_dispatcher(action_map=profiles)
        controller.get_foreground_app.return_value = "chrome.exe"
        event = _make_event(gesture="SwipeUp", action="OS:ShowDesktop")
        bus.publish("gesture_triggered", event)
        time.sleep(0.05)
        controller.show_desktop.assert_called_once()
        assert event.app_profile == "_default"


# ═══════════════════════════════════════════════════════════════════════════════
# ActionDispatcher — _classify_app
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyApp:

    @pytest.fixture(autouse=True)
    def dispatcher(self):
        d, _, _ = _make_dispatcher()
        self._d = d

    def _classify(self, name: str) -> str:
        return self._d._classify_app(name)

    def test_empty_string_returns_unknown(self) -> None:
        assert self._classify("") == "unknown"

    def test_browser_chrome(self) -> None:
        assert self._classify("chrome.exe") == "browser"

    def test_browser_firefox(self) -> None:
        assert self._classify("firefox") == "browser"

    def test_browser_edge(self) -> None:
        assert self._classify("msedge.exe") == "browser"

    def test_editor_vscode(self) -> None:
        assert self._classify("code.exe") == "editor"

    def test_editor_notepad(self) -> None:
        assert self._classify("notepad.exe") == "editor"

    def test_media_vlc(self) -> None:
        assert self._classify("vlc.exe") == "media"

    def test_media_spotify(self) -> None:
        assert self._classify("spotify.exe") == "media"

    def test_communication_slack(self) -> None:
        assert self._classify("slack.exe") == "communication"

    def test_communication_discord(self) -> None:
        assert self._classify("discord.exe") == "communication"

    def test_communication_teams(self) -> None:
        assert self._classify("teams.exe") == "communication"

    def test_game_steam(self) -> None:
        assert self._classify("steam.exe") == "game"

    def test_system_explorer(self) -> None:
        assert self._classify("explorer.exe") == "system"

    def test_system_powershell(self) -> None:
        assert self._classify("powershell.exe") == "system"

    def test_system_terminal(self) -> None:
        assert self._classify("terminal") == "system"

    def test_unknown_app(self) -> None:
        assert self._classify("myprivateapp.exe") == "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimiter — additional branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimiterAdditional:

    def test_global_window_resets_after_one_second(self) -> None:
        """After 1s the global window clears and allows new actions."""
        limiter = RateLimiter()
        t = 100.0

        def mono():
            return t

        with patch("time.monotonic", mono):
            for _ in range(30):
                t += 0.015
                limiter.check_and_record(None)
            assert limiter.check_and_record(None) is False

        # Advance > 1 second
        t += 1.1
        with patch("time.monotonic", mono):
            assert limiter.check_and_record(None) is True

    def test_burst_window_resets_after_100ms(self) -> None:
        """After 100ms the burst window clears."""
        limiter = RateLimiter()
        t = 100.0

        def mono():
            return t

        with patch("time.monotonic", mono):
            for _ in range(10):
                limiter.check_and_record(None)
            assert limiter.check_and_record(None) is False

        t += 0.11
        with patch("time.monotonic", mono):
            assert limiter.check_and_record(None) is True

    def test_per_gesture_window_resets_after_one_second(self) -> None:
        """Per-gesture window resets after 1 second."""
        limiter = RateLimiter()
        t = 100.0

        def mono():
            return t

        with patch("time.monotonic", mono):
            for _ in range(5):
                t += 0.015
                limiter.check_and_record("wave")
            assert limiter.check_and_record("wave") is False

        t += 1.1
        with patch("time.monotonic", mono):
            assert limiter.check_and_record("wave") is True

    def test_none_gesture_id_skips_per_gesture_tracking(self) -> None:
        """gesture_id=None bypasses per-gesture history entirely."""
        limiter = RateLimiter()
        t = 100.0

        def mono():
            return t

        with patch("time.monotonic", mono):
            for _ in range(10):
                t += 0.015
                result = limiter.check_and_record(None)
        assert limiter.gesture_history == {}

    def test_independent_per_gesture_limits(self) -> None:
        """Different gesture IDs have independent 5/s limits."""
        limiter = RateLimiter()
        t = 100.0

        def mono():
            return t

        with patch("time.monotonic", mono):
            for _ in range(5):
                t += 0.015
                limiter.check_and_record("gesture_A")
            # A is now at limit, B should still pass
            assert limiter.check_and_record("gesture_A") is False
            assert limiter.check_and_record("gesture_B") is True


# ═══════════════════════════════════════════════════════════════════════════════
# AuditLogger — additional branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLoggerAdditional:

    def test_log_chain_length(self, tmp_path) -> None:
        """N log() calls produce exactly N lines."""
        al = AuditLogger(tmp_path / "audit.log")
        for i in range(5):
            al.log("event", {"i": i})
        lines = (tmp_path / "audit.log").read_text().splitlines()
        assert len(lines) == 5

    def test_resumes_hash_chain_from_existing_log(self, tmp_path) -> None:
        """New AuditLogger opens an existing log and resumes hash chain correctly."""
        log_path = tmp_path / "audit.log"
        al1 = AuditLogger(log_path)
        al1.log("first", {"v": 1})
        last_hash_after_first = al1.last_hash

        # Re-open — should read the last hash from disk
        al2 = AuditLogger(log_path)
        assert al2.last_hash == last_hash_after_first

        al2.log("second", {"v": 2})
        lines = log_path.read_text().splitlines()
        entry2 = json.loads(lines[1])
        assert entry2["prev_hash"] == last_hash_after_first

    def test_concurrent_writes_dont_corrupt_log(self, tmp_path) -> None:
        """Many concurrent threads writing to the same AuditLogger produce valid JSON lines."""
        log_path = tmp_path / "concurrent_audit.log"
        al = AuditLogger(log_path)
        threads = [
            threading.Thread(target=al.log, args=(f"event_{i}", {"i": i}))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = log_path.read_text().splitlines()
        assert len(lines) == 20
        for line in lines:
            entry = json.loads(line)  # must be valid JSON
            assert "hash" in entry
            assert "prev_hash" in entry

    def test_each_entry_hash_covers_content(self, tmp_path) -> None:
        """Verify SHA-256 hash of each entry matches the stored 'hash' field."""
        log_path = tmp_path / "hash_check.log"
        al = AuditLogger(log_path)
        al.log("alpha", {"x": 1})
        al.log("beta", {"x": 2})

        lines = log_path.read_text().splitlines()
        for line in lines:
            entry = json.loads(line)
            stored_hash = entry.pop("hash")
            recomputed = hashlib.sha256(
                json.dumps(entry, sort_keys=True).encode("utf-8")
            ).hexdigest()
            assert stored_hash == recomputed
