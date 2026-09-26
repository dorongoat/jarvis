"""Skill registry: phrase matching and execution."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import Config


@dataclass
class SkillContext:
    """Everything a skill handler may need."""

    config: Config
    language: str
    text: str
    assistant: Any = None


@dataclass
class SkillResult:
    speech: str
    handled: bool = True
    quit: bool = False
    sleep: bool = False


Handler = Callable[[SkillContext, re.Match[str]], SkillResult]


@dataclass
class Skill:
    name: str
    description: str
    patterns: list[str]
    handler: Handler
    # Parameters the language model may fill in when it routes to this skill.
    arguments: list[str] = field(default_factory=list)
    compiled: list[re.Pattern[str]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.compiled = [re.compile(pattern, re.IGNORECASE | re.UNICODE) for pattern in self.patterns]

    def match(self, text: str) -> re.Match[str] | None:
        for pattern in self.compiled:
            found = pattern.search(text)
            if found:
                return found
        return None


_REGISTRY: dict[str, Skill] = {}


def register(skill: Skill) -> Skill:
    _REGISTRY[skill.name] = skill
    return skill


def all_skills() -> list[Skill]:
    from . import builtin  # noqa: F401  (import for side effects: registration)

    return list(_REGISTRY.values())


def match_skill(text: str) -> tuple[Skill, re.Match[str]] | None:
    """Return the first skill whose phrase pattern matches ``text``."""
    for skill in all_skills():
        found = skill.match(text)
        if found:
            return skill, found
    return None


def run_skill(name: str, context: SkillContext, arguments: dict[str, str] | None = None) -> SkillResult:
    """Run a skill by name with explicit arguments (used by the language-model router)."""
    skills = {skill.name: skill for skill in all_skills()}
    skill = skills[name]
    pseudo_text = " ".join(str(value) for value in (arguments or {}).values())
    match = skill.match(context.text) or skill.match(pseudo_text)
    if match is None:
        match = re.match(r"(?P<query>.*)", pseudo_text, re.UNICODE | re.DOTALL)
        assert match is not None
    return skill.handler(context, match)
