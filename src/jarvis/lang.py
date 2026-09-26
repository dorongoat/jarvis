"""Language detection and bilingual phrase book (Hebrew / English)."""

from __future__ import annotations

import random
import re

HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
LATIN_RE = re.compile(r"[A-Za-z]")

HE = "he"
EN = "en"


def detect_language(text: str, default: str = EN) -> str:
    """Return "he" or "en" for a piece of text.

    Hebrew sentences frequently embed Latin product names ("תפתח לי Spotify"),
    so any meaningful amount of Hebrew script wins over Latin script.
    """
    hebrew = len(HEBREW_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if hebrew == 0 and latin == 0:
        return default
    if hebrew >= 2 and hebrew * 3 >= latin:
        return HE
    return HE if hebrew > latin else EN


def is_rtl(language: str) -> bool:
    return language == HE


PHRASES: dict[str, dict[str, list[str]]] = {
    "boot": {
        EN: ["All systems nominal, sir. Jarvis online."],
        HE: ["כל המערכות תקינות, אדוני. ג\'ארוויס מקוון."],
    },
    "listening": {EN: ["Listening."], HE: ["מקשיב."]},
    "yes": {
        EN: ["Yes, sir?", "At your service.", "Go ahead, sir."],
        HE: ["כן, אדוני?", "לשירותך.", "אני מקשיב, אדוני."],
    },
    "working": {EN: ["Right away, sir."], HE: ["מיד, אדוני."]},
    "done": {EN: ["Done, sir."], HE: ["בוצע, אדוני."]},
    "not_understood": {
        EN: ["I did not catch that, sir.", "Apologies, sir, could you repeat that?"],
        HE: ["לא הצלחתי לקלוט, אדוני.", "סליחה אדוני, תוכל לחזור על זה?"],
    },
    "goodbye": {EN: ["Powering down. Goodbye, sir."], HE: ["מכבה מערכות. להתראות, אדוני."]},
    "sleep": {EN: ["Going to standby, sir."], HE: ["עובר למצב המתנה, אדוני."]},
    "error": {
        EN: ["Something went wrong, sir: {error}"],
        HE: ["משהו השתבש, אדוני: {error}"],
    },
    "no_brain": {
        EN: ["My language core is offline, sir. Voice commands still work."],
        HE: ["ליבת השפה שלי לא זמינה, אדוני. פקודות קוליות עדיין פועלות."],
    },
    "no_microphone": {
        EN: ["No microphone is available, sir. You can still type to me."],
        HE: ["אין מיקרופון זמין, אדוני. עדיין אפשר להקליד לי."],
    },
}

UI_TEXT: dict[str, dict[str, str]] = {
    "state_idle": {EN: "STANDBY", HE: "המתנה"},
    "state_listening": {EN: "LISTENING", HE: "מקשיב"},
    "state_thinking": {EN: "PROCESSING", HE: "מעבד"},
    "state_speaking": {EN: "SPEAKING", HE: "מדבר"},
    "state_offline": {EN: "MIC OFFLINE", HE: "מיקרופון כבוי"},
    "input_placeholder": {EN: "Type a command...", HE: "הקלד פקודה..."},
    "mic_on": {EN: "MIC ON", HE: "מיקרופון פועל"},
    "mic_off": {EN: "MIC OFF", HE: "מיקרופון כבוי"},
    "you": {EN: "YOU", HE: "אתה"},
}


def phrase(key: str, language: str, **kwargs: object) -> str:
    options = PHRASES.get(key, {}).get(language) or PHRASES.get(key, {}).get(EN) or [key]
    return random.choice(options).format(**kwargs)


def ui_text(key: str, language: str) -> str:
    entry = UI_TEXT.get(key, {})
    return entry.get(language) or entry.get(EN) or key
