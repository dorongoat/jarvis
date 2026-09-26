"""The JARVIS orchestrator: wake word -> speech -> router -> voice."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from ..audio.stt import MicrophoneUnavailable, SpeechToText, Transcript
from ..audio.tts import TextToSpeech
from ..audio.wakeword import WakeWordDetector
from ..brain.providers import build_brain
from ..brain.router import Router
from ..config import Config, load_config
from ..lang import EN, detect_language, phrase

log = logging.getLogger(__name__)


class State(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    OFFLINE = "offline"


@dataclass
class Event:
    kind: str  # "state" | "user" | "jarvis" | "log"
    text: str = ""
    language: str = EN
    state: State | None = None


Listener = Callable[[Event], None]


class Assistant:
    """Runs the full voice loop in a background thread and emits UI events."""

    def __init__(self, config: Config | None = None, listener: Listener | None = None):
        self.config = config or load_config()
        self.listener = listener or (lambda event: None)
        self.language = (
            self.config.get("assistant.default_language", "auto")
            if self.config.get("assistant.default_language", "auto") in {"he", "en"}
            else EN
        )
        self.stt = SpeechToText(self.config)
        self.tts = TextToSpeech(self.config)
        self.wake = WakeWordDetector(self.config.get("assistant.wake_words", ["jarvis"]))
        self.router = Router(self.config, build_brain(self.config))
        self.state = State.IDLE
        self.awake = False
        self.voice_enabled = True
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._speech_lock = threading.Lock()
        self._last_interaction = 0.0

    # -- events --------------------------------------------------------
    def emit(self, event: Event) -> None:
        try:
            self.listener(event)
        except Exception:  # pragma: no cover - listener belongs to the UI
            log.exception("event listener failed")

    def set_state(self, state: State) -> None:
        self.state = state
        self.emit(Event("state", state=state))

    # -- speech --------------------------------------------------------
    def say(self, text: str, language: str | None = None) -> None:
        language = language or detect_language(text, default=self.language)
        self.emit(Event("jarvis", text, language))
        previous = self.state
        self.set_state(State.SPEAKING)
        with self._speech_lock:
            self.tts.say(text, language)
        self.set_state(State.IDLE if previous == State.SPEAKING else previous)

    def announce(self, text: str, language: str | None = None) -> None:
        """Speak unprompted (timers, reminders)."""
        self.say(text, language)

    # -- command handling ----------------------------------------------
    def handle_text(self, text: str, language: str | None = None, speak: bool = True) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        language = language or detect_language(text, default=self.language)
        self.language = language
        self.emit(Event("user", text, language))
        self.set_state(State.THINKING)
        result = self.router.handle(text, language, assistant=self)
        self._last_interaction = time.time()
        if speak:
            self.say(result.speech, language)
        else:
            self.emit(Event("jarvis", result.speech, language))
        if result.sleep:
            self.awake = False
        if result.quit:
            self.stop()
        self.set_state(State.IDLE)
        return result.speech

    def handle_text_async(self, text: str, language: str | None = None, speak: bool = True) -> None:
        """Handle a typed command off the UI thread."""
        threading.Thread(
            target=self.handle_text, args=(text, language, speak), daemon=True
        ).start()

    # -- voice loop ------------------------------------------------------
    def start(self, greet: bool = True) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._loop, kwargs={"greet": greet}, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self.tts.stop()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def _loop(self, greet: bool = True) -> None:
        if greet:
            self.say(phrase("boot", self.language), self.language)
        timeout = float(self.config.get("assistant.conversation_timeout", 25))
        while self._running.is_set():
            if not self.voice_enabled:
                self.set_state(State.IDLE)
                time.sleep(0.3)
                continue
            try:
                self.set_state(State.LISTENING if self.awake else State.IDLE)
                transcript = self.stt.listen(timeout=4)
            except MicrophoneUnavailable as exc:
                log.warning("microphone unavailable: %s", exc)
                self.set_state(State.OFFLINE)
                self.emit(Event("log", phrase("no_microphone", self.language), self.language))
                time.sleep(3)
                continue
            except Exception as exc:  # pragma: no cover - hardware dependent
                log.warning("listening failed: %s", exc)
                time.sleep(1)
                continue

            if not transcript:
                if self.awake and time.time() - self._last_interaction > timeout:
                    self.awake = False
                    self.set_state(State.IDLE)
                continue

            self._consume(transcript)

    def _consume(self, transcript: Transcript) -> None:
        heard, remainder = self.wake.find(transcript.text)
        if heard:
            self.awake = True
            self._last_interaction = time.time()
            if remainder:
                self.handle_text(remainder, transcript.language)
            else:
                self.emit(Event("user", transcript.text, transcript.language))
                self.say(phrase("yes", transcript.language), transcript.language)
            return
        if self.awake:
            self.handle_text(transcript.text, transcript.language)
