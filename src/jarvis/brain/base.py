"""Common language model interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class Brain:
    """Base class for language model backends."""

    name = "brain"

    def available(self) -> bool:
        raise NotImplementedError

    def complete(self, messages: list[Message], temperature: float = 0.6) -> str:
        raise NotImplementedError


class NullBrain(Brain):
    """Used when no model is configured or reachable."""

    name = "offline"

    def available(self) -> bool:
        return False

    def complete(self, messages: list[Message], temperature: float = 0.6) -> str:
        return ""
