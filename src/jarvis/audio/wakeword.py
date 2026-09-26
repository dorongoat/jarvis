"""Wake word matching ("Jarvis" / "ג\'ארוויס")."""

from __future__ import annotations

import re
import unicodedata

PUNCTUATION = re.compile(r"[^\w\s\u0590-\u05FF]", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("׳", "").replace("'", "").replace("\u05f4", "").replace('"', "")
    text = PUNCTUATION.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


class WakeWordDetector:
    def __init__(self, wake_words: list[str]):
        self.wake_words = [normalize(word) for word in wake_words if normalize(word)]

    def find(self, text: str) -> tuple[bool, str]:
        """Return ``(heard, remainder)`` where remainder is the command after the wake word."""
        normalized = normalize(text)
        if not normalized:
            return False, ""
        for word in sorted(self.wake_words, key=len, reverse=True):
            index = normalized.find(word)
            if index == -1:
                continue
            remainder = normalized[index + len(word) :].strip(" ,.-")
            return True, remainder
        return False, ""
