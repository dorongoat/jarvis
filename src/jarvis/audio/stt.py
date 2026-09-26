"""Speech to text with Hebrew and English support.

Two engines are supported:
  * ``google``  - free Google Web Speech endpoint used by SpeechRecognition (needs internet).
  * ``whisper`` - fully offline transcription through ``faster-whisper``.

Both are optional at import time so the rest of JARVIS (and the tests) run
on machines without a microphone or without the audio dependencies installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import Config
from ..lang import EN, HE, detect_language

log = logging.getLogger(__name__)

LOCALE = {HE: "he-IL", EN: "en-US"}


@dataclass
class Transcript:
    text: str
    language: str

    def __bool__(self) -> bool:
        return bool(self.text.strip())


class MicrophoneUnavailable(RuntimeError):
    pass


def list_microphones() -> list[str]:
    try:
        import speech_recognition as sr
    except ImportError:  # pragma: no cover - depends on optional deps
        return []
    return list(sr.Microphone.list_microphone_names())


Candidate = str | tuple[str, float]

SCRIPT_MATCH_BONUS = 0.4
DEFAULT_CONFIDENCE = 0.5


def pick_transcript(candidates: dict[str, Candidate], default_language: str = EN) -> Transcript:
    """Choose the best transcript out of ``{language: text}`` candidates.

    Each candidate may carry the recogniser confidence as ``(text, confidence)``.
    A transcript is boosted when its script matches the language it was decoded
    with - a Hebrew decode that comes back as Latin text is almost always a
    mis-recognition, and vice versa.
    """
    scored: list[tuple[float, int, str, str]] = []
    for language, candidate in candidates.items():
        text, confidence = candidate if isinstance(candidate, tuple) else (candidate, DEFAULT_CONFIDENCE)
        clean = (text or "").strip()
        if not clean:
            continue
        matches_script = detect_language(clean, default=language) == language
        score = float(confidence) + (SCRIPT_MATCH_BONUS if matches_script else 0.0)
        scored.append((score, len(clean), language, clean))
    if not scored:
        return Transcript("", default_language)
    scored.sort(reverse=True)
    _, _, language, text = scored[0]
    return Transcript(text, detect_language(text, default=language))


def _best_alternative(response: object) -> tuple[str, float] | None:
    """Normalise the Google Web Speech payload into ``(text, confidence)``."""
    if isinstance(response, str):
        return (response, DEFAULT_CONFIDENCE) if response.strip() else None
    if not isinstance(response, dict):
        return None
    alternatives = response.get("alternative") or []
    best: tuple[str, float] | None = None
    for alternative in alternatives:
        text = (alternative.get("transcript") or "").strip()
        if not text:
            continue
        confidence = float(alternative.get("confidence", DEFAULT_CONFIDENCE))
        if best is None or confidence > best[1]:
            best = (text, confidence)
    return best


class SpeechToText:
    """Records a phrase from the microphone and transcribes it bilingually."""

    def __init__(self, config: Config):
        self.config = config
        self.engine = config.get("speech_to_text.engine", "google")
        self.phrase_time_limit = config.get("speech_to_text.phrase_time_limit", 12)
        self._recognizer = None
        self._microphone = None
        self._whisper = None

    # -- setup ---------------------------------------------------------
    def _ensure_microphone(self):
        if self._microphone is not None:
            return self._recognizer, self._microphone
        try:
            import speech_recognition as sr
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise MicrophoneUnavailable("SpeechRecognition is not installed") from exc

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = self.config.get("speech_to_text.energy_threshold", 300)
        recognizer.dynamic_energy_threshold = self.config.get("speech_to_text.dynamic_energy", True)
        recognizer.pause_threshold = 0.7
        index = self.config.get("speech_to_text.microphone_index")
        try:
            microphone = sr.Microphone(device_index=index)
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
        except Exception as exc:  # pragma: no cover - hardware dependent
            raise MicrophoneUnavailable(str(exc)) from exc
        self._recognizer, self._microphone = recognizer, microphone
        return recognizer, microphone

    @property
    def available(self) -> bool:
        try:
            self._ensure_microphone()
        except MicrophoneUnavailable:
            return False
        return True

    # -- capture -------------------------------------------------------
    def listen(self, timeout: float | None = None) -> Transcript:
        """Block until a phrase is captured, then transcribe it."""
        recognizer, microphone = self._ensure_microphone()
        import speech_recognition as sr

        try:
            with microphone as source:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=self.phrase_time_limit)
        except sr.WaitTimeoutError:
            return Transcript("", EN)
        return self.transcribe(audio)

    def transcribe(self, audio) -> Transcript:
        if self.engine == "whisper":
            return self._transcribe_whisper(audio)
        return self._transcribe_google(audio)

    def _transcribe_google(self, audio) -> Transcript:
        import speech_recognition as sr

        recognizer = self._recognizer or sr.Recognizer()
        candidates: dict[str, Candidate] = {}
        for language, locale in LOCALE.items():
            try:
                response = recognizer.recognize_google(audio, language=locale, show_all=True)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as exc:
                log.warning("Google speech request failed (%s): %s", locale, exc)
                continue
            candidate = _best_alternative(response)
            if candidate:
                candidates[language] = candidate
        return pick_transcript(candidates)

    def _transcribe_whisper(self, audio) -> Transcript:
        import io
        import wave

        if self._whisper is None:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]

            self._whisper = WhisperModel(
                self.config.get("speech_to_text.whisper_model", "small"), compute_type="int8"
            )
        buffer = io.BytesIO(audio.get_wav_data())
        with wave.open(buffer, "rb"):
            buffer.seek(0)
        segments, info = self._whisper.transcribe(buffer, beam_size=5)
        text = " ".join(segment.text for segment in segments).strip()
        language = HE if info.language == "he" else EN
        return Transcript(text, detect_language(text, default=language))
