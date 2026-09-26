from jarvis.config import Config
from jarvis.core.assistant import Assistant, State
from jarvis.lang import HE


class DummyTTS:
    def __init__(self):
        self.spoken: list[tuple[str, str]] = []

    def say(self, text, language=None):
        self.spoken.append((text, language))

    def stop(self):
        pass


def build_assistant() -> Assistant:
    assistant = Assistant(Config({"brain": {"provider": "offline"}}))
    assistant.tts = DummyTTS()
    return assistant


def test_typed_hebrew_command_is_answered_and_spoken_in_hebrew():
    assistant = build_assistant()
    events = []
    assistant.listener = events.append
    answer = assistant.handle_text("מה השעה")
    assert "אדוני" in answer
    assert assistant.tts.spoken[-1][1] == HE
    assert any(event.kind == "state" and event.state == State.THINKING for event in events)


def test_quit_command_stops_the_assistant():
    assistant = build_assistant()
    assistant._running.set()
    assistant.handle_text("power down")
    assert assistant.running is False
