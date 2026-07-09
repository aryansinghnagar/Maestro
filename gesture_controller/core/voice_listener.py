import time
import threading
import structlog
from typing import Any, Optional

from gesture_controller.core.event_bus import EventBus
from gesture_controller.models.data_types import GestureEvent

logger = structlog.get_logger(__name__)


class VoiceCommandListener:
    """Listens for voice commands and maps them to Maestro gesture triggers (Phase 15)."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Voice command listener thread started")

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Voice command listener thread stopped")

    def _run_loop(self) -> None:
        # Try to initialize SpeechRecognition if installed
        recognizer = None
        microphone = None
        try:
            import speech_recognition as sr  # type: ignore[import-not-found]
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            # Calibrate recognizer for ambient noise
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except Exception as e:
            logger.info("Local SpeechRecognition not available, running voice mock listener", error=str(e))

        while self.running:
            if recognizer and microphone:
                try:
                    import speech_recognition as sr
                    with microphone as source:
                        audio = recognizer.listen(source, timeout=1.0, phrase_time_limit=2.0)
                    text = recognizer.recognize_google(audio).lower()
                    self.process_command(text)
                except Exception:
                    # Timeout or noise error, continue
                    pass
            else:
                # Mock sleep
                time.sleep(0.5)

    def process_command(self, text: str) -> None:
        """Parse voice text and trigger corresponding actions."""
        text = text.lower().strip()
        logger.info("Parsed voice command text", text=text)
        
        # Format command checks (e.g. "maestro trigger swipeleft", "maestro trigger MinimizeWindow")
        if "maestro trigger" in text or "maestro" in text:
            # Extract gesture name
            parts = text.split("trigger")
            gesture_name = parts[-1].strip() if len(parts) > 1 else ""
            if not gesture_name:
                gesture_name = text.replace("maestro", "").strip()

            # Clean and match gesture
            gesture_map = {
                "swipe left": "SwipeLeft",
                "swipeleft": "SwipeLeft",
                "swipe right": "SwipeRight",
                "swiperight": "SwipeRight",
                "swipe up": "SwipeUp",
                "swipeup": "SwipeUp",
                "swipe down": "SwipeDown",
                "swipedown": "SwipeDown",
                "fist": "Fist",
                "minimize": "MinimizeWindow",
                "copy": "CustomCopy"
            }
            matched_gesture = gesture_map.get(gesture_name.lower())
            
            if matched_gesture:
                event = GestureEvent(
                    gesture_name=matched_gesture,
                    gesture_type="voice",
                    action="",  # resolved by ActionDispatcher
                    confidence=1.0,
                    hand="None",
                    timestamp=time.time()
                )
                self.event_bus.publish("gesture_triggered", event)
                logger.info("Voice command triggered gesture", voice_phrase=text, matched=matched_gesture)
