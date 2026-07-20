"""Voice Command Listener — Sprint 16 (hardened).

Key improvements over the original:
- ``VoiceCommandRegistry``: phrase→gesture mapping loaded from ConfigManager;
  ships with built-in defaults and merges user-defined entries from
  ``voice.commands`` config key.
- Wake-word gate: configurable word (default ``"maestro"``); recognition only
  fires once the wake word is detected (cooldown prevents re-triggering).
- ``process_command()`` delegates fully to the registry — no hardcoded dict.
- All I/O (Vosk, PyAudio) is kept in ``_run_loop``; ``process_command`` is
  pure-function testable.
"""
from __future__ import annotations

import re
import time
import json
import threading
import structlog
from typing import Any, Optional

from gesture_controller.core.event_bus import EventBus
from gesture_controller.models.data_types import GestureEvent
from gesture_controller.core.paths import user_data_dir

logger = structlog.get_logger(__name__)

# ── Default built-in phrase→gesture map ──────────────────────────────────────

_DEFAULT_PHRASES: dict[str, str] = {
    "swipe left": "SwipeLeft",
    "swipeleft": "SwipeLeft",
    "go left": "SwipeLeft",
    "swipe right": "SwipeRight",
    "swiperight": "SwipeRight",
    "go right": "SwipeRight",
    "swipe up": "SwipeUp",
    "swipeup": "SwipeUp",
    "scroll up": "SwipeUp",
    "swipe down": "SwipeDown",
    "swipedown": "SwipeDown",
    "scroll down": "SwipeDown",
    "fist": "Fist",
    "hold fist": "HoldFist",
    "minimize": "MinimizeWindow",
    "minimize window": "MinimizeWindow",
    "copy": "CustomCopy",
    "paste": "CustomPaste",
    "select all": "CustomSelectAll",
    "next track": "MediaNext",
    "previous track": "MediaPrevious",
    "play pause": "MediaPlayPause",
    "volume up": "VolumeUp",
    "volume down": "VolumeDown",
    "show desktop": "ShowDesktop",
}

# Cooldown after a wake-word activation during which more commands are accepted
_WAKE_COOLDOWN_SECONDS: float = 5.0


# ── Registry ──────────────────────────────────────────────────────────────────

class VoiceCommandRegistry:
    """Holds phrase→gesture mappings and resolves spoken text to gesture names.

    The registry merges built-in defaults with user-defined entries from
    ``voice.commands`` in the ConfigManager (a list of
    ``{"phrase": "...", "gesture": "..."}`` dicts).

    Matching is case-insensitive and strips punctuation.
    """

    def __init__(self, config: Any = None) -> None:
        self._map: dict[str, str] = dict(_DEFAULT_PHRASES)
        if config is not None:
            self._load_from_config(config)

    # ── Config loading ────────────────────────────────────────────────────────

    def _load_from_config(self, config: Any) -> None:
        """Merge user-defined voice commands from config."""
        user_cmds = config.get("voice.commands", [])
        if not isinstance(user_cmds, list):
            return
        for entry in user_cmds:
            if not isinstance(entry, dict):
                continue
            phrase = str(entry.get("phrase", "")).strip().lower()
            gesture = str(entry.get("gesture", "")).strip()
            if phrase and gesture:
                self._map[phrase] = gesture
                logger.debug("Loaded user voice command", phrase=phrase, gesture=gesture)

    # ── Mutation ──────────────────────────────────────────────────────────────

    def register(self, phrase: str, gesture: str) -> None:
        """Add or overwrite a phrase→gesture mapping at runtime."""
        self._map[phrase.strip().lower()] = gesture

    def unregister(self, phrase: str) -> bool:
        """Remove a mapping. Returns True if it existed."""
        return self._map.pop(phrase.strip().lower(), None) is not None

    # ── Resolution ────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(text: str) -> str:
        """Lower-case and strip punctuation for fuzzy matching."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
        text = re.sub(r"\s+", " ", text)
        return text

    def resolve(self, text: str) -> Optional[str]:
        """Return the gesture name for *text*, or ``None`` if unrecognised.

        Matching is performed in order from longest phrase to shortest to
        prefer more specific matches (e.g. ``"swipe left"`` before ``"left"``).
        """
        normalised = self._normalise(text)
        for phrase in sorted(self._map, key=len, reverse=True):
            if phrase in normalised:
                return self._map[phrase]
        return None

    def all_phrases(self) -> list[str]:
        """Return all registered phrases sorted alphabetically."""
        return sorted(self._map.keys())

    def __len__(self) -> int:
        return len(self._map)


# ── Voice listener ────────────────────────────────────────────────────────────

class VoiceCommandListener:
    """Listens for voice commands and maps them to Maestro gesture triggers.

    Uses Vosk (offline) when available; falls back to a mock no-op loop.
    Supports a configurable wake-word gate so the listener only acts after
    the user says the wake word.
    """

    def __init__(self, event_bus: EventBus, config: Any = None) -> None:
        self.event_bus = event_bus
        self._config = config
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # Wake-word gate
        wake_word = "maestro"
        if config is not None:
            wake_word = str(config.get("voice.wake_word", "maestro")).lower().strip()
        self._wake_word: str = wake_word
        self._wake_word_required: bool = bool(wake_word)
        self._last_wake_time: float = 0.0

        # Command registry
        self._registry = VoiceCommandRegistry(config)

        self.model_dir = user_data_dir() / "models" / "vosk-model-small-en-us-0.15"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="voice_listener")
        self._thread.start()
        logger.info("Voice command listener thread started", wake_word=self._wake_word)

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Voice command listener thread stopped")

    # ── Wake-word gate ────────────────────────────────────────────────────────

    def _check_wake_word(self, text: str) -> bool:
        """Return True if wake-word was just heard; updates cooldown timer."""
        if self._wake_word and self._wake_word in text.lower():
            self._last_wake_time = time.monotonic()
            return True
        return False

    def _is_within_wake_window(self) -> bool:
        """Return True if we're still within the post-wake-word cooldown."""
        if not self._wake_word_required:
            return True
        return (time.monotonic() - self._last_wake_time) < _WAKE_COOLDOWN_SECONDS

    # ── Command processing ────────────────────────────────────────────────────

    def process_command(self, text: str) -> bool:
        """Parse *text* and publish a gesture_triggered event if recognised.

        Returns True if a gesture was triggered.

        The wake-word gate works as follows:
        1. If *text* contains the wake word → open the window (or keep it open).
        2. If within the wake window → resolve the command.
        3. If outside the wake window → silently ignore.
        """
        text = text.lower().strip()
        logger.debug("Voice input received", text=text)

        # 1. Check/refresh wake word
        self._check_wake_word(text)

        # 2. Guard: must be within wake window to act
        if not self._is_within_wake_window():
            logger.debug("Voice input ignored (wake word not heard)", text=text)
            return False

        # 3. Strip wake word from text before resolving
        cleaned = text.replace(self._wake_word, "").strip() if self._wake_word else text

        # 4. Resolve gesture
        gesture_name = self._registry.resolve(cleaned) or self._registry.resolve(text)
        if not gesture_name:
            logger.debug("Voice command unrecognised", text=text)
            return False

        # 5. Publish
        event = GestureEvent(
            gesture_name=gesture_name,
            gesture_type="voice",
            action="",          # resolved by ActionDispatcher
            confidence=1.0,
            hand="None",
            timestamp=time.time(),
        )
        self.event_bus.publish("gesture_triggered", event)
        logger.info(
            "Voice command triggered gesture",
            voice_phrase=text,
            matched=gesture_name,
        )
        return True

    # ── Internal run loop ─────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        vosk_ok = False
        Model_cls = None
        KaldiRecognizer_cls = None
        pyaudio_mod = None

        try:
            from vosk import Model as VM, KaldiRecognizer as KR
            import pyaudio as PA
            Model_cls = VM
            KaldiRecognizer_cls = KR
            pyaudio_mod = PA
            vosk_ok = True
        except ImportError as e:
            logger.info("Vosk or PyAudio not installed, using mock loop", error=str(e))

        if vosk_ok and not self.model_dir.exists():
            logger.warning(
                "Vosk model not found. Run: maestro download-voice-model",
                path=str(self.model_dir),
            )
            vosk_ok = False

        if vosk_ok and Model_cls and KaldiRecognizer_cls and pyaudio_mod:
            try:
                model = Model_cls(str(self.model_dir))
                rec = KaldiRecognizer_cls(model, 16000)
                rec.SetWords(True)
                p = pyaudio_mod.PyAudio()
                stream = p.open(
                    format=pyaudio_mod.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=4000,
                )
                stream.start_stream()
                logger.info("Vosk offline speech recognition loop started")

                while self.running:
                    data = stream.read(2000, exception_on_overflow=False)
                    if len(data) == 0:
                        continue
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get("text", "").lower().strip()
                        if text:
                            self.process_command(text)

                stream.stop_stream()
                stream.close()
                p.terminate()
                return
            except Exception as e:
                logger.error("Error in Vosk loop, falling back to mock", error=str(e))

        # Fallback no-op loop
        logger.info("Running mock (no-op) voice listener loop")
        while self.running:
            time.sleep(0.5)
