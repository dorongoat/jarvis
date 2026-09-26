"""Decides whether a command is a skill or a conversation.

Order of resolution:
 1. Phrase patterns (instant, offline, works in Hebrew and English).
 2. Optional language-model routing into the same skill catalog.
 3. Free conversation with the language model.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from ..config import Config
from ..lang import phrase
from ..skills import SkillContext, SkillResult, match_skill, run_skill
from ..skills.builtin import catalog
from .base import Brain, Message
from .persona import system_prompt

log = logging.getLogger(__name__)

ROUTING_PROMPT = """You route a voice command to one skill of a personal assistant.
Available skills:
{catalog}

Reply with JSON only, no prose: {{"skill": "<skill name or chat>", "arguments": {{}}}}
Use "chat" when the command is a question, small talk or anything not covered by a skill.
Command: {command}"""

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class RouteResult:
    speech: str
    source: str  # "skill:<name>" | "chat" | "fallback"
    quit: bool = False
    sleep: bool = False


@dataclass
class Router:
    config: Config
    brain: Brain
    history: list[Message] = field(default_factory=list)

    @property
    def persona(self) -> str:
        return self.config.get("assistant.persona", "jarvis")

    def handle(self, text: str, language: str, assistant: object | None = None) -> RouteResult:
        text = (text or "").strip()
        if not text:
            return RouteResult(phrase("not_understood", language), "fallback")

        context = SkillContext(config=self.config, language=language, text=text, assistant=assistant)

        matched = match_skill(text)
        if matched:
            skill, match = matched
            result = skill.handler(context, match)
            if result.handled:
                return RouteResult(result.speech, f"skill:{skill.name}", result.quit, result.sleep)

        if self.config.get("brain.llm_routing", True) and self.brain.available():
            routed = self._route_with_model(context)
            if routed is not None:
                return routed

        return self._chat(text, language)

    # -- internals -----------------------------------------------------
    def _route_with_model(self, context: SkillContext) -> RouteResult | None:
        prompt = ROUTING_PROMPT.format(catalog=catalog(), command=context.text)
        try:
            raw = self.brain.complete(
                [
                    Message("system", "You output strict JSON and nothing else."),
                    Message("user", prompt),
                ],
                temperature=0.0,
            )
        except Exception as exc:
            log.warning("skill routing failed: %s", exc)
            return None
        payload = parse_route(raw)
        if not payload:
            return None
        name = payload.get("skill")
        if not name or name == "chat":
            return None
        try:
            result: SkillResult = run_skill(name, context, payload.get("arguments") or {})
        except KeyError:
            return None
        except Exception as exc:
            log.warning("skill %s failed: %s", name, exc)
            return RouteResult(phrase("error", context.language, error=str(exc)), "fallback")
        return RouteResult(result.speech, f"skill:{name}", result.quit, result.sleep)

    def _chat(self, text: str, language: str) -> RouteResult:
        if not self.brain.available():
            return RouteResult(phrase("no_brain", language), "fallback")
        messages = [
            Message("system", system_prompt(self.persona, language)),
            *self.history,
            Message("user", text),
        ]
        temperature = float(self.config.get("brain.temperature", 0.6))
        try:
            answer = self.brain.complete(messages, temperature=temperature)
        except Exception as exc:
            log.warning("chat completion failed: %s", exc)
            return RouteResult(phrase("error", language, error=str(exc)), "fallback")
        if not answer:
            return RouteResult(phrase("not_understood", language), "fallback")
        self.remember(text, answer)
        return RouteResult(answer, "chat")

    def remember(self, user_text: str, answer: str) -> None:
        self.history.extend([Message("user", user_text), Message("assistant", answer)])
        limit = int(self.config.get("brain.max_history_turns", 12)) * 2
        if len(self.history) > limit:
            self.history = self.history[-limit:]


def parse_route(raw: str) -> dict | None:
    """Extract the routing JSON object out of a model reply."""
    if not raw:
        return None
    block = JSON_BLOCK.search(raw)
    if not block:
        return None
    try:
        payload = json.loads(block.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
