"""Concrete language model providers: Ollama (local), OpenAI and Anthropic."""

from __future__ import annotations

import logging
import os

import requests

from ..config import Config
from .base import Brain, Message, NullBrain

log = logging.getLogger(__name__)


class OllamaBrain(Brain):
    """Local, free, no API key. Requires `ollama serve` and a pulled model."""

    name = "ollama"

    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def available(self) -> bool:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=3)
            response.raise_for_status()
        except Exception as exc:
            log.warning("Ollama is not reachable at %s: %s", self.host, exc)
            return False
        models = [item.get("name", "") for item in response.json().get("models", [])]
        if models and not any(name.split(":")[0] == self.model.split(":")[0] for name in models):
            log.warning("Ollama model %s is not pulled. Available: %s", self.model, ", ".join(models))
        return True

    def complete(self, messages: list[Message], temperature: float = 0.6) -> str:
        response = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [message.as_dict() for message in messages],
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=120,
        )
        response.raise_for_status()
        return (response.json().get("message", {}).get("content") or "").strip()


class OpenAIBrain(Brain):
    name = "openai"

    def __init__(self, model: str, api_key: str | None):
        self.model = model
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: list[Message], temperature: float = 0.6) -> str:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [message.as_dict() for message in messages],
                "temperature": temperature,
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


class AnthropicBrain(Brain):
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None):
        self.model = model
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: list[Message], temperature: float = 0.6) -> str:
        system = " ".join(message.content for message in messages if message.role == "system")
        conversation = [message.as_dict() for message in messages if message.role != "system"]
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "system": system,
                "messages": conversation,
                "max_tokens": 600,
                "temperature": temperature,
            },
            timeout=90,
        )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        return "".join(block.get("text", "") for block in blocks).strip()


def build_brain(config: Config) -> Brain:
    provider = (config.get("brain.provider", "ollama") or "offline").lower()
    if provider == "ollama":
        return OllamaBrain(
            config.get("brain.ollama.host", "http://localhost:11434"),
            config.get("brain.ollama.model", "llama3.1:8b"),
        )
    if provider == "openai":
        return OpenAIBrain(
            config.get("brain.openai.model", "gpt-4o-mini"),
            os.environ.get(config.get("brain.openai.api_key_env", "OPENAI_API_KEY")),
        )
    if provider == "anthropic":
        return AnthropicBrain(
            config.get("brain.anthropic.model", "claude-3-5-sonnet-latest"),
            os.environ.get(config.get("brain.anthropic.api_key_env", "ANTHROPIC_API_KEY")),
        )
    return NullBrain()
