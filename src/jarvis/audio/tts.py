"""Text to speech with a natural Hebrew voice.

``edge`` uses Microsoft Edge neural voices (free, no API key, great Hebrew).
``sapi`` falls back to the offline Windows voices through pyttsx3.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
from pathlib import Path

from ..config import Config
from ..lang import HE, detect_language

log = logging.getLogger(__name__)


class TextToSpeech:
    def __init__(self, config: Config):
        self.config = config
        self.engine = config.get("text_to_speech.engine", "edge")
        self.voices = {
            HE: config.get("text_to_speech.voice_he", "he-IL-AvriNeural"),
            "en": config.get("text_to_speech.voice_en", "en-GB-RyanNeural"),
        }
        self.rate = config.get("text_to_speech.rate", "+8%")
        self.volume = float(config.get("text_to_speech.volume", 1.0))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sapi = None

    def stop(self) -> None:
        """Interrupt whatever is currently being spoken."""
        self._stop.set()
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:  # pragma: no cover - playback backend optional
            pass

    def say(self, text: str, language: str | None = None) -> None:
        text = (text or "").strip()
        if not text:
            return
        language = language or detect_language(text)
        with self._lock:
            self._stop.clear()
            if self.engine == "edge":
                try:
                    self._say_edge(text, language)
                    return
                except Exception as exc:
                    log.warning("edge-tts failed, falling back to SAPI: %s", exc)
            self._say_sapi(text, language)

    # -- backends ------------------------------------------------------
    def _say_edge(self, text: str, language: str) -> None:
        import edge_tts
        import pygame

        voice = self.voices.get(language, self.voices["en"])
        out = Path(tempfile.gettempdir()) / f"jarvis_tts_{threading.get_ident()}.mp3"

        async def synthesize() -> None:
            communicate = edge_tts.Communicate(text, voice, rate=self.rate)
            await communicate.save(str(out))

        asyncio.run(synthesize())

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(str(out))
        pygame.mixer.music.set_volume(self.volume)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() and not self._stop.is_set():
            pygame.time.wait(80)
        pygame.mixer.music.unload()
        out.unlink(missing_ok=True)

    def _say_sapi(self, text: str, language: str) -> None:
        try:
            import pyttsx3
        except ImportError:  # pragma: no cover - non Windows
            log.error("No speech backend available; printing instead: %s", text)
            return
        engine = pyttsx3.init()
        engine.setProperty("volume", self.volume)
        wanted = "he" if language == HE else "en"
        for voice in engine.getProperty("voices"):
            languages = " ".join(str(item) for item in getattr(voice, "languages", []))
            haystack = f"{voice.id} {voice.name} {languages}".lower()
            if wanted in haystack or (wanted == "he" and "hebrew" in haystack):
                engine.setProperty("voice", voice.id)
                break
        engine.say(text)
        engine.runAndWait()
        engine.stop()
