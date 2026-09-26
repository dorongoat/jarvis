"""The built-in skill set: system control, apps, web, weather, notes and timers."""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import requests

from ..lang import HE, phrase
from .registry import Skill, SkillContext, SkillResult, register

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

HEBREW_DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def _bilingual(context: SkillContext, hebrew: str, english: str) -> SkillResult:
    return SkillResult(hebrew if context.language == HE else english)


# ---------------------------------------------------------------- time
def _time(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    now = dt.datetime.now()
    return _bilingual(
        context,
        f"השעה {now.hour:02d}:{now.minute:02d}, אדוני.",
        f"It is {now.strftime('%I:%M %p').lstrip('0')}, sir.",
    )


def _date(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    today = dt.date.today()
    hebrew_day = HEBREW_DAYS[today.weekday()]
    return _bilingual(
        context,
        f"היום יום {hebrew_day}, {today.day} ב{today:%B} {today.year}.",
        f"Today is {today:%A, %d %B %Y}.",
    )


# ---------------------------------------------------------------- apps
CLAUSE_BREAKS = {"and", "then", "also", "please", "ואז", "אחרכך"}


def _app_name(target: str, apps: dict[str, str]) -> str:
    """Pull the application name out of a spoken sentence.

    Speech recognition hands over whole utterances ("open blender and make me a
    statue"), so a known alias wins, and otherwise the name is cut at the first
    word that starts a new clause - in Hebrew that is any word prefixed with vav.
    """
    cleaned = " ".join(target.lower().split()).strip(" .,\"'")
    for alias in sorted(apps, key=len, reverse=True):
        if cleaned == alias or cleaned.startswith(f"{alias} "):
            return alias
    head: list[str] = []
    for index, word in enumerate(cleaned.split(" ")):
        if index and (word in CLAUSE_BREAKS or (word.startswith("ו") and len(word) > 2)):
            break
        head.append(word)
        if len(head) == 3:
            break
    return " ".join(head)


START_MENU_DIRS = (
    r"%ProgramData%\Microsoft\Windows\Start Menu\Programs",
    r"%AppData%\Microsoft\Windows\Start Menu\Programs",
)


def _start_menu_shortcut(name: str) -> str | None:
    """Find a Start Menu .lnk for an app that is not on PATH (Blender, Steam, ...)."""
    wanted = name.lower().removesuffix(".exe")
    for directory in START_MENU_DIRS:
        root = Path(os.path.expandvars(directory))
        if not root.is_dir():
            continue
        for link in root.rglob("*.lnk"):
            stem = link.stem.lower()
            if stem == wanted or stem.startswith(f"{wanted} "):
                return str(link)
    return None


def _start_windows(command: str) -> None:
    try:
        os.startfile(command)  # type: ignore[attr-defined]  # noqa: S606
    except OSError:
        shortcut = _start_menu_shortcut(command)
        if not shortcut:
            raise
        os.startfile(shortcut)  # type: ignore[attr-defined]  # noqa: S606


def _open_app(context: SkillContext, match: re.Match[str]) -> SkillResult:
    raw = (match.groupdict().get("target") or "").strip(" .,\"'")
    if not raw:
        return _bilingual(context, "איזו תוכנה לפתוח, אדוני?", "Which application, sir?")
    apps: dict[str, str] = context.config.get("skills.apps", {}) or {}
    target = _app_name(raw, apps)
    command = apps.get(target, target)
    try:
        if command.startswith("http"):
            webbrowser.open(command)
        elif IS_WINDOWS:
            _start_windows(command)
        else:
            subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        log.warning("Could not launch %s: %s", command, exc)
        return _bilingual(
            context, f"לא הצלחתי לפתוח את {target}, אדוני.", f"I could not open {target}, sir."
        )
    return _bilingual(context, f"פותח את {target}, אדוני.", f"Opening {target}, sir.")


# ---------------------------------------------------------------- web
def _search(context: SkillContext, match: re.Match[str]) -> SkillResult:
    query = (match.groupdict().get("query") or "").strip(" .,\"'")
    if not query:
        return _bilingual(context, "מה לחפש, אדוני?", "What should I search for, sir?")
    template = context.config.get("skills.search_engine", "https://www.google.com/search?q={query}")
    webbrowser.open(template.format(query=quote_plus(query)))
    return _bilingual(context, f"מחפש {query}, אדוני.", f"Searching for {query}, sir.")


def _play_youtube(context: SkillContext, match: re.Match[str]) -> SkillResult:
    query = (match.groupdict().get("query") or "").strip(" .,\"'")
    url = (
        f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        if query
        else "https://www.youtube.com"
    )
    webbrowser.open(url)
    return _bilingual(context, f"מנגן {query} ביוטיוב, אדוני.", f"Playing {query} on YouTube, sir.")


# ---------------------------------------------------------------- weather
def _weather(context: SkillContext, match: re.Match[str]) -> SkillResult:
    location = (match.groupdict().get("place") or "").strip(" .,?\"'")
    location = location or context.config.get("skills.weather_location", "Tel Aviv")
    language = "he" if context.language == HE else "en"
    try:
        response = requests.get(
            f"https://wttr.in/{quote_plus(location)}?format=%C+%t+%w&lang={language}", timeout=8
        )
        response.raise_for_status()
        summary = response.text.strip()
    except Exception as exc:
        log.warning("weather lookup failed: %s", exc)
        return SkillResult(phrase("error", context.language, error=str(exc)))
    return _bilingual(
        context, f"מזג האוויר ב{location}: {summary}.", f"The weather in {location} is {summary}."
    )


# ---------------------------------------------------------------- volume
def _set_volume(level: float) -> bool:
    """Set the master volume (0.0 - 1.0). Returns True on success."""
    if not IS_WINDOWS:
        return False
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-not-found]

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
        return True
    except Exception as exc:  # pragma: no cover - Windows only
        log.warning("volume control failed: %s", exc)
        return False


def _get_volume() -> float | None:
    if not IS_WINDOWS:
        return None
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-not-found]

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume)).GetMasterVolumeLevelScalar()
    except Exception:  # pragma: no cover - Windows only
        return None


def _volume(context: SkillContext, match: re.Match[str]) -> SkillResult:
    groups = match.groupdict()
    current = _get_volume()
    if groups.get("percent"):
        target = int(groups["percent"]) / 100
    elif groups.get("mute"):
        target = 0.0
    elif groups.get("up"):
        target = min(1.0, (current if current is not None else 0.5) + 0.15)
    else:
        target = max(0.0, (current if current is not None else 0.5) - 0.15)
    if not _set_volume(target):
        return _bilingual(
            context, "שליטה בעוצמת הקול זמינה רק בווינדוס, אדוני.", "Volume control is Windows only, sir."
        )
    percent = round(target * 100)
    return _bilingual(context, f"עוצמת הקול על {percent} אחוז.", f"Volume at {percent} percent.")


# ---------------------------------------------------------------- system
def _screenshot(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    try:
        from PIL import ImageGrab

        folder = Path.home() / "Pictures" / "Jarvis"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"screenshot_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
        ImageGrab.grab().save(path)
    except Exception as exc:
        return SkillResult(phrase("error", context.language, error=str(exc)))
    return _bilingual(context, f"צילום המסך נשמר ב{path}.", f"Screenshot saved to {path}.")


def _system_status(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.4)
        memory = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
    except Exception as exc:
        return SkillResult(phrase("error", context.language, error=str(exc)))
    battery_he = f", הסוללה על {int(battery.percent)} אחוז" if battery else ""
    battery_en = f", battery at {int(battery.percent)} percent" if battery else ""
    return _bilingual(
        context,
        f"המעבד על {cpu:.0f} אחוז, הזיכרון על {memory:.0f} אחוז{battery_he}. הכול תקין, אדוני.",
        f"CPU at {cpu:.0f} percent, memory at {memory:.0f} percent{battery_en}. All systems nominal, sir.",
    )


def _power(context: SkillContext, match: re.Match[str]) -> SkillResult:
    groups = match.groupdict()
    if not IS_WINDOWS:
        return _bilingual(
            context, "פקודות כיבוי נתמכות רק בווינדוס, אדוני.", "Power commands are Windows only, sir."
        )
    if groups.get("lock"):
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
        return _bilingual(context, "נועל את המחשב, אדוני.", "Locking the workstation, sir.")
    if groups.get("restart"):
        subprocess.run(["shutdown", "/r", "/t", "30"], check=False)
        return _bilingual(
            context, "מפעיל מחדש בעוד שלושים שניות. אמור 'בטל כיבוי' כדי לעצור.",
            "Restarting in thirty seconds. Say 'cancel shutdown' to abort.",
        )
    if groups.get("cancel"):
        subprocess.run(["shutdown", "/a"], check=False)
        return _bilingual(context, "הכיבוי בוטל, אדוני.", "Shutdown aborted, sir.")
    subprocess.run(["shutdown", "/s", "/t", "30"], check=False)
    return _bilingual(
        context, "מכבה בעוד שלושים שניות. אמור 'בטל כיבוי' כדי לעצור.",
        "Shutting down in thirty seconds. Say 'cancel shutdown' to abort.",
    )


# ---------------------------------------------------------------- notes
def _notes_path(context: SkillContext) -> Path:
    path = Path(context.config.get("skills.notes_file", "~/.jarvis/notes.txt")).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _add_note(context: SkillContext, match: re.Match[str]) -> SkillResult:
    note = (match.groupdict().get("note") or "").strip()
    if not note:
        return _bilingual(context, "מה לרשום, אדוני?", "What should I note down, sir?")
    path = _notes_path(context)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"[{dt.datetime.now():%Y-%m-%d %H:%M}] {note}\n")
    return _bilingual(context, "רשמתי, אדוני.", "Noted, sir.")


def _read_notes(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    path = _notes_path(context)
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return _bilingual(context, "אין פתקים שמורים, אדוני.", "You have no notes, sir.")
    lines = [line.split("] ", 1)[-1] for line in path.read_text(encoding="utf-8").strip().splitlines()]
    recent = lines[-5:]
    joined = "; ".join(recent)
    return _bilingual(context, f"הפתקים האחרונים שלך: {joined}.", f"Your latest notes: {joined}.")


# ---------------------------------------------------------------- timers
def _timer(context: SkillContext, match: re.Match[str]) -> SkillResult:
    groups = match.groupdict()
    amount = int(groups.get("amount") or 0)
    unit = (groups.get("unit") or "").lower()
    if not amount:
        return _bilingual(context, "לכמה זמן להגדיר טיימר, אדוני?", "For how long, sir?")
    if unit in {"hour", "hours", "שעה", "שעות"}:
        multiplier = 3600
    elif unit in {"minute", "minutes", "דקה", "דקות"}:
        multiplier = 60
    else:
        multiplier = 1
    seconds = amount * multiplier

    def ring() -> None:
        message = "הטיימר הסתיים, אדוני." if context.language == HE else "Your timer has finished, sir."
        assistant = context.assistant
        if assistant is not None and hasattr(assistant, "announce"):
            assistant.announce(message, context.language)

    threading.Timer(seconds, ring).start()
    return _bilingual(
        context, f"טיימר ל{amount} {unit} הופעל, אדוני.", f"Timer set for {amount} {unit}, sir."
    )


# ---------------------------------------------------------------- session
def _sleep(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    return SkillResult(phrase("sleep", context.language), sleep=True)


def _quit(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    return SkillResult(phrase("goodbye", context.language), quit=True)


def _who_are_you(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    return _bilingual(
        context,
        "אני ג'ארוויס, מערכת ההפעלה האישית שלך. אני מדבר עברית ואנגלית, שולט במחשב ועונה על שאלות.",
        "I am Jarvis, your personal operating system. I speak Hebrew and English, "
        "control this machine and answer questions.",
    )


def _help(context: SkillContext, _match: re.Match[str]) -> SkillResult:
    return _bilingual(
        context,
        "אפשר לבקש ממני שעה, מזג אוויר, לפתוח תוכנות, לחפש בגוגל, לשלוט בעוצמת הקול, לצלם מסך, "
        "לרשום פתקים, להגדיר טיימר, לבדוק את מצב המערכת - או פשוט לשוחח איתי.",
        "You can ask me for the time, the weather, to open applications, search the web, control the volume, "
        "take a screenshot, keep notes, set timers, check system status - or simply talk with me.",
    )


SKILLS = [
    Skill("time", "Tell the current time", [r"\b(what.*time|time is it)\b", r"(מה\s+)?השעה"], _time),
    Skill(
        "date",
        "Tell today's date",
        [r"\b(what.*date|what day)\b", r"מה\s+התאריך|איזה\s+יום\s+היום|מה\s+היום\b"],
        _date,
    ),
    Skill(
        "open_app",
        "Open an application, folder or website",
        [
            r"\b(?:open|launch|start|run)\s+(?P<target>.+)",
            r"(?:תפתח|פתח|תריץ|הפעל)\s+(?:לי\s+)?(?:את\s+)?(?P<target>.+)",
        ],
        _open_app,
        arguments=["target"],
    ),
    Skill(
        "play_youtube",
        "Play something on YouTube",
        [r"\bplay\s+(?P<query>.+?)(?:\s+on\s+youtube)?$", r"(?:תנגן|נגן|תשים)\s+(?:לי\s+)?(?P<query>.+)"],
        _play_youtube,
        arguments=["query"],
    ),
    Skill(
        "search",
        "Search the web",
        [
            r"\b(?:search|google|look up)\s+(?:for\s+)?(?P<query>.+)",
            r"(?:תחפש|חפש|תגגל)\s+(?:לי\s+)?(?P<query>.+)",
        ],
        _search,
        arguments=["query"],
    ),
    Skill(
        "weather",
        "Report the weather for a place",
        [
            r"\bweather\b(?:\s+(?:in|for|at)\s+(?P<place>.+))?",
            r"מזג\s*האוויר(?:\s+ב(?P<place>.+))?",
            r"\bקר\s+בחוץ|\bחם\s+בחוץ",
        ],
        _weather,
        arguments=["place"],
    ),
    Skill(
        "volume",
        "Change the system volume",
        [
            r"\b(?:set\s+)?volume\s+(?:to\s+)?(?P<percent>\d{1,3})\s*(?:percent|%)?",
            r"\bvolume\s+(?P<up>up)\b|\bvolume\s+(?P<down>down)\b|\b(?P<mute>mute)\b",
            r"(?:תעלה|העלה|תגביר|הגבר)\s+(?:את\s+)?(?:ה)?(?:ווליום|קול|עוצמה)(?P<up>)",
            r"(?:תוריד|הורד|תנמיך|הנמך)\s+(?:את\s+)?(?:ה)?(?:ווליום|קול|עוצמה)(?P<down>)",
            r"(?:תשתיק|השתק)(?P<mute>)",
            r"(?:ווליום|עוצמת\s*קול)\s+(?P<percent>\d{1,3})",
        ],
        _volume,
        arguments=["percent"],
    ),
    Skill(
        "screenshot",
        "Capture the screen",
        [r"\bscreen\s*shot\b|\bcapture (?:the )?screen\b", r"(?:תצלם|צלם)\s+(?:את\s+)?(?:ה)?מסך"],
        _screenshot,
    ),
    Skill(
        "system_status",
        "Report CPU, memory and battery",
        [
            r"\b(?:system|status|diagnostics|how are you feeling|cpu|battery)\b",
            r"(?:מצב\s+ה?מערכת|סטטוס|אבחון|סוללה|מעבד)",
        ],
        _system_status,
    ),
    Skill(
        "power",
        "Shut down, restart or lock the computer",
        [
            r"\b(?P<cancel>cancel (?:the )?shutdown)\b",
            r"\b(?P<lock>lock)\s+(?:the\s+)?(?:computer|pc|workstation)\b",
            r"\b(?P<restart>restart|reboot)\s+(?:the\s+)?(?:computer|pc)\b",
            r"\bshut\s*down\s+(?:the\s+)?(?:computer|pc)\b",
            r"(?P<cancel>בטל\s+(?:את\s+ה)?כיבוי)",
            r"(?P<lock>נעל|תנעל)\s+(?:את\s+)?(?:ה)?מחשב",
            r"(?P<restart>אתחל|תאתחל)\s+(?:את\s+)?(?:ה)?מחשב",
            r"(?:כבה|תכבה)\s+(?:את\s+)?(?:ה)?מחשב",
        ],
        _power,
    ),
    Skill(
        "add_note",
        "Remember a note",
        [
            r"\b(?:note|remember|write down)(?:\s+that)?\s+(?P<note>.+)",
            r"(?:תרשום|רשום|תזכור|זכור)\s+(?:לי\s+)?(?:ש)?(?P<note>.+)",
        ],
        _add_note,
        arguments=["note"],
    ),
    Skill(
        "read_notes",
        "Read back saved notes",
        [
            r"\b(?:read|what are) my notes\b",
            r"(?:מה\s+)?(?:ה)?פתקים\s*(?:שלי)?|תקריא\s+(?:לי\s+)?(?:את\s+)?הפתקים",
        ],
        _read_notes,
    ),
    Skill(
        "timer",
        "Set a countdown timer",
        [
            r"\b(?:set (?:a )?)?timer (?:for )?(?P<amount>\d+)\s*(?P<unit>seconds?|minutes?|hours?)",
            r"(?:תזכיר\s+לי\s+בעוד|טיימר\s+ל?|תעיר\s+אותי\s+בעוד)\s*(?P<amount>\d+)\s*"
            r"(?P<unit>שניות|שנייה|דקות|דקה|שעות|שעה)",
        ],
        _timer,
        arguments=["amount", "unit"],
    ),
    Skill(
        "sleep",
        "Stop listening until the wake word is heard again",
        [
            r"\b(?:go to sleep|stand ?by|stop listening|never mind)\b",
            r"(?:לך\s+לישון|תפסיק\s+להקשיב|מצב\s+המתנה|עזוב)",
        ],
        _sleep,
    ),
    Skill(
        "quit",
        "Shut JARVIS down",
        [
            r"\b(?:shut ?down jarvis|exit|quit|goodbye jarvis|power down)\b",
            r"(?:כבה\s+את\s+ג|תכבה\s+את\s+ג|צא|יציאה|להתראות\s+ג)",
        ],
        _quit,
    ),
    Skill(
        "identity",
        "Explain what JARVIS is",
        [r"\bwho are you\b|\bwhat are you\b", r"(?:מי\s+אתה|מה\s+אתה)"],
        _who_are_you,
    ),
    Skill(
        "help",
        "List what JARVIS can do",
        [r"\b(?:help|what can you do)\b", r"(?:עזרה|מה\s+אתה\s+יודע\s+לעשות|מה\s+אתה\s+יכול)"],
        _help,
    ),
]

for _skill in SKILLS:
    register(_skill)


def catalog() -> str:
    """Human readable skill catalog, used in the language model prompt."""
    lines = []
    for skill in SKILLS:
        arguments = f" (arguments: {', '.join(skill.arguments)})" if skill.arguments else ""
        lines.append(f"- {skill.name}: {skill.description}{arguments}")
    return "\n".join(lines)
