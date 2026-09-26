from jarvis.brain.base import Brain, Message
from jarvis.brain.router import Router, parse_route
from jarvis.config import load_config
from jarvis.lang import EN, HE

CONFIG = load_config("/nonexistent/config.yaml")


class FakeBrain(Brain):
    name = "fake"

    def __init__(self, reply: str = "Certainly, sir."):
        self.reply = reply
        self.calls: list[list[Message]] = []

    def available(self) -> bool:
        return True

    def complete(self, messages, temperature: float = 0.6) -> str:
        self.calls.append(messages)
        return self.reply


def test_skill_wins_over_the_model():
    brain = FakeBrain()
    router = Router(CONFIG, brain)
    result = router.handle("what time is it", EN)
    assert result.source == "skill:time"
    assert brain.calls == []


def test_chat_falls_back_to_the_model_in_hebrew():
    brain = FakeBrain("בהחלט, אדוני.")
    router = Router(CONFIG, brain)
    result = router.handle("ספר לי בדיחה על איירון מן", HE)
    assert result.source in {"chat", "skill:chat"}
    assert result.speech == "בהחלט, אדוני."
    assert router.history[-1].content == "בהחלט, אדוני."


def test_without_a_model_the_user_is_told():
    from jarvis.brain.base import NullBrain

    router = Router(CONFIG, NullBrain())
    result = router.handle("tell me a joke", EN)
    assert result.source == "fallback"
    assert "offline" in result.speech.lower()


def test_quit_command_is_propagated():
    router = Router(CONFIG, FakeBrain())
    assert router.handle("power down", EN).quit is True
    assert router.handle("go to sleep", EN).sleep is True


def test_parse_route_extracts_json():
    assert parse_route('sure: {"skill": "time", "arguments": {}} ')["skill"] == "time"
    assert parse_route("no json here") is None
