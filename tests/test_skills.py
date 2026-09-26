import pytest

from jarvis.config import load_config
from jarvis.lang import EN, HE
from jarvis.skills import SkillContext, match_skill

CONFIG = load_config("/nonexistent/config.yaml")


def context(text: str, language: str) -> SkillContext:
    return SkillContext(config=CONFIG, language=language, text=text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("what time is it", "time"),
        ("מה השעה", "time"),
        ("open spotify", "open_app"),
        ("תפתח לי ספוטיפיי", "open_app"),
        ("search for iron man suit", "search"),
        ("תחפש חליפת איירון מן", "search"),
        ("set volume to 40", "volume"),
        ("תוריד את הווליום", "volume"),
        ("take a screenshot", "screenshot"),
        ("תצלם מסך", "screenshot"),
        ("set a timer for 5 minutes", "timer"),
        ("טיימר ל 10 דקות", "timer"),
        ("lock the computer", "power"),
        ("תנעל את המחשב", "power"),
        ("who are you", "identity"),
        ("מי אתה", "identity"),
        ("weather in Haifa", "weather"),
        ("מזג האוויר בתל אביב", "weather"),
    ],
)
def test_phrase_routing(text, expected):
    matched = match_skill(text)
    assert matched is not None, f"no skill matched {text!r}"
    assert matched[0].name == expected


def test_time_skill_answers_in_the_right_language():
    skill, match = match_skill("מה השעה")
    assert "אדוני" in skill.handler(context("מה השעה", HE), match).speech
    skill, match = match_skill("what time is it")
    assert "sir" in skill.handler(context("what time is it", EN), match).speech


def test_notes_roundtrip(tmp_path, monkeypatch):
    from jarvis.config import Config

    config = Config({"skills": {"notes_file": str(tmp_path / "notes.txt")}})
    skill, match = match_skill("תרשום שצריך לקנות חלב")
    result = skill.handler(SkillContext(config, HE, "תרשום שצריך לקנות חלב"), match)
    assert "רשמתי" in result.speech
    skill, match = match_skill("read my notes")
    read = skill.handler(SkillContext(config, EN, "read my notes"), match)
    assert "חלב" in read.speech
