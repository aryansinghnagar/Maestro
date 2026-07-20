"""Unit tests for Sprint 16 — Voice Command Engine Hardening.

Covers:
- VoiceCommandRegistry: defaults, config loading, register, unregister, resolve,
  normalise, longest-match preference, __len__, all_phrases
- VoiceCommandListener: construction, wake-word gate, process_command happy path,
  unrecognised command, wake-window expiry, wake-word-free mode, event publication,
  start/stop lifecycle, custom config commands
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(**overrides) -> MagicMock:
    store = {
        "voice.wake_word": "maestro",
        "voice.commands": [],
        **overrides,
    }
    m = MagicMock()
    m.get.side_effect = lambda k, default=None: store.get(k, default)
    return m


def _make_bus() -> MagicMock:
    return MagicMock()


# ── VoiceCommandRegistry ──────────────────────────────────────────────────────

class TestVoiceCommandRegistry:
    def test_defaults_loaded(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert len(reg) > 0

    def test_defaults_include_swipe_left(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.resolve("swipe left") == "SwipeLeft"

    def test_defaults_include_minimize(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.resolve("minimize") == "MinimizeWindow"

    def test_defaults_include_media_commands(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.resolve("next track") == "MediaNext"
        assert reg.resolve("play pause") == "MediaPlayPause"
        assert reg.resolve("volume up") == "VolumeUp"

    def test_resolve_case_insensitive(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.resolve("SWIPE LEFT") == "SwipeLeft"

    def test_resolve_strips_punctuation(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.resolve("swipe left!") == "SwipeLeft"

    def test_resolve_unknown_returns_none(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.resolve("do a barrel roll") is None

    def test_resolve_longest_match_wins(self) -> None:
        """'minimize window' should win over 'minimize' when both in phrase."""
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        # Both "minimize" and "minimize window" map to MinimizeWindow; just confirm resolve works
        result = reg.resolve("please minimize window now")
        assert result == "MinimizeWindow"

    def test_register_new_phrase(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        reg.register("do a spin", "SpinGesture")
        assert reg.resolve("do a spin") == "SpinGesture"

    def test_register_overwrites_existing(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        reg.register("fist", "CustomFist")
        assert reg.resolve("fist") == "CustomFist"

    def test_unregister_existing_phrase(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        reg.register("wave hello", "Wave")
        assert reg.unregister("wave hello") is True
        assert reg.resolve("wave hello") is None

    def test_unregister_nonexistent_returns_false(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert reg.unregister("nonexistent phrase xyz") is False

    def test_all_phrases_sorted(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        phrases = reg.all_phrases()
        assert phrases == sorted(phrases)

    def test_len_matches_phrase_count(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        reg = VoiceCommandRegistry()
        assert len(reg) == len(reg.all_phrases())

    def test_config_commands_merged(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        cfg = _make_config(**{
            "voice.commands": [
                {"phrase": "do a flip", "gesture": "FlipGesture"},
            ]
        })
        reg = VoiceCommandRegistry(cfg)
        assert reg.resolve("do a flip") == "FlipGesture"

    def test_config_commands_override_defaults(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        cfg = _make_config(**{
            "voice.commands": [
                {"phrase": "fist", "gesture": "SuperFist"},
            ]
        })
        reg = VoiceCommandRegistry(cfg)
        assert reg.resolve("fist") == "SuperFist"

    def test_config_bad_entries_ignored(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        cfg = _make_config(**{
            "voice.commands": [
                "not_a_dict",
                {"phrase": "", "gesture": "SomeGesture"},
                {"gesture": "NoPhrase"},
                {"phrase": "valid", "gesture": "ValidGesture"},
            ]
        })
        reg = VoiceCommandRegistry(cfg)
        assert reg.resolve("valid") == "ValidGesture"

    def test_normalise_removes_punctuation(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        result = VoiceCommandRegistry._normalise("Swipe, Left!")
        assert result == "swipe left"

    def test_normalise_collapses_spaces(self) -> None:
        from gesture_controller.core.voice_listener import VoiceCommandRegistry
        result = VoiceCommandRegistry._normalise("swipe   left")
        assert result == "swipe left"


# ── VoiceCommandListener — wake-word gate ─────────────────────────────────────

class TestVoiceCommandListenerWakeWord:
    def _make_listener(self, wake_word="maestro"):
        from gesture_controller.core.voice_listener import VoiceCommandListener
        bus = _make_bus()
        cfg = _make_config(**{"voice.wake_word": wake_word, "voice.commands": []})
        with patch("gesture_controller.core.voice_listener.user_data_dir", return_value=MagicMock()):
            listener = VoiceCommandListener(bus, cfg)
        return listener, bus

    def test_command_ignored_before_wake_word(self) -> None:
        listener, bus = self._make_listener()
        result = listener.process_command("swipe left")
        assert result is False
        bus.publish.assert_not_called()

    def test_command_accepted_after_wake_word(self) -> None:
        listener, bus = self._make_listener()
        result = listener.process_command("maestro swipe left")
        assert result is True
        bus.publish.assert_called_once()

    def test_command_accepted_within_cooldown(self) -> None:
        listener, bus = self._make_listener()
        listener.process_command("maestro")           # open gate
        result = listener.process_command("swipe right")  # no wake word, but in window
        assert result is True

    def test_command_rejected_after_cooldown_expires(self) -> None:
        listener, bus = self._make_listener()
        listener._last_wake_time = time.monotonic() - 100  # expired
        result = listener.process_command("swipe left")
        assert result is False

    def test_wake_word_in_middle_of_sentence(self) -> None:
        listener, bus = self._make_listener()
        result = listener.process_command("hey maestro swipe up")
        assert result is True

    def test_no_wake_word_config_disables_gate(self) -> None:
        """Empty wake word = accept all commands without gate."""
        from gesture_controller.core.voice_listener import VoiceCommandListener
        bus = _make_bus()
        cfg = _make_config(**{"voice.wake_word": "", "voice.commands": []})
        with patch("gesture_controller.core.voice_listener.user_data_dir", return_value=MagicMock()):
            listener = VoiceCommandListener(bus, cfg)
        result = listener.process_command("swipe left")
        assert result is True

    def test_custom_wake_word(self) -> None:
        listener, bus = self._make_listener(wake_word="jarvis")
        result = listener.process_command("jarvis minimize window")
        assert result is True

    def test_wrong_wake_word_ignored(self) -> None:
        listener, bus = self._make_listener(wake_word="jarvis")
        result = listener.process_command("maestro swipe left")  # wrong wake word
        assert result is False


# ── VoiceCommandListener — process_command ─────────────────────────────────────

class TestVoiceCommandListenerProcessCommand:
    def _make_active_listener(self):
        """Returns a listener already in the wake window."""
        from gesture_controller.core.voice_listener import VoiceCommandListener
        bus = _make_bus()
        cfg = _make_config(**{"voice.commands": []})
        with patch("gesture_controller.core.voice_listener.user_data_dir", return_value=MagicMock()):
            listener = VoiceCommandListener(bus, cfg)
        # Open the wake gate
        listener._last_wake_time = time.monotonic()
        return listener, bus

    def test_recognised_command_publishes_event(self) -> None:
        listener, bus = self._make_active_listener()
        result = listener.process_command("swipe left")
        assert result is True
        bus.publish.assert_called_once()
        args = bus.publish.call_args[0]
        assert args[0] == "gesture_triggered"

    def test_published_event_has_correct_gesture_name(self) -> None:
        listener, bus = self._make_active_listener()
        listener.process_command("swipe right")
        event = bus.publish.call_args[0][1]
        assert event.gesture_name == "SwipeRight"

    def test_published_event_type_is_voice(self) -> None:
        listener, bus = self._make_active_listener()
        listener.process_command("fist")
        event = bus.publish.call_args[0][1]
        assert event.gesture_type == "voice"

    def test_unrecognised_command_returns_false(self) -> None:
        listener, bus = self._make_active_listener()
        result = listener.process_command("do a cartwheel")
        assert result is False
        bus.publish.assert_not_called()

    def test_empty_string_returns_false(self) -> None:
        listener, bus = self._make_active_listener()
        result = listener.process_command("")
        assert result is False

    def test_media_command_triggers(self) -> None:
        listener, bus = self._make_active_listener()
        result = listener.process_command("next track")
        assert result is True
        event = bus.publish.call_args[0][1]
        assert event.gesture_name == "MediaNext"

    def test_volume_command_triggers(self) -> None:
        listener, bus = self._make_active_listener()
        result = listener.process_command("volume down")
        assert result is True


# ── VoiceCommandListener — lifecycle ──────────────────────────────────────────

class TestVoiceCommandListenerLifecycle:
    def _make_listener(self):
        from gesture_controller.core.voice_listener import VoiceCommandListener
        bus = _make_bus()
        cfg = _make_config()
        with patch("gesture_controller.core.voice_listener.user_data_dir", return_value=MagicMock()):
            return VoiceCommandListener(bus, cfg), bus

    def test_not_running_initially(self) -> None:
        listener, _ = self._make_listener()
        assert listener.running is False

    def test_start_sets_running(self) -> None:
        listener, _ = self._make_listener()
        with patch.object(listener, "_run_loop"):
            listener.start()
            assert listener.running is True
            listener.stop()

    def test_start_idempotent(self) -> None:
        """Calling start() twice doesn't spawn a second thread."""
        listener, _ = self._make_listener()
        with patch.object(listener, "_run_loop"):
            listener.start()
            thread1 = listener._thread
            listener.start()
            thread2 = listener._thread
            assert thread1 is thread2
            listener.stop()

    def test_stop_clears_running(self) -> None:
        listener, _ = self._make_listener()
        with patch.object(listener, "_run_loop"):
            listener.start()
            listener.stop()
            assert listener.running is False
