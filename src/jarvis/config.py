"""Configuration loading and typed access."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "assistant": {
        "name_en": "Jarvis",
        "name_he": "ג\'ארוויס",
        "wake_words": ["jarvis", "hey jarvis", "ג\'ארוויס", "גארוויס", "גרוויס", "ג׳ארוויס"],
        "default_language": "auto",
        "conversation_timeout": 25,
        "persona": "jarvis",
    },
    "speech_to_text": {
        "engine": "google",
        "whisper_model": "small",
        "microphone_index": None,
        "energy_threshold": 300,
        "dynamic_energy": True,
        "phrase_time_limit": 12,
    },
    "text_to_speech": {
        "engine": "edge",
        "voice_he": "he-IL-AvriNeural",
        "voice_en": "en-GB-RyanNeural",
        "rate": "+8%",
        "volume": 1.0,
    },
    "brain": {
        "provider": "ollama",
        "ollama": {"host": "http://localhost:11434", "model": "llama3.1:8b"},
        "openai": {"model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
        "anthropic": {"model": "claude-3-5-sonnet-latest", "api_key_env": "ANTHROPIC_API_KEY"},
        "temperature": 0.6,
        "max_history_turns": 12,
        "llm_routing": True,
    },
    "skills": {
        "weather_location": "Tel Aviv",
        "search_engine": "https://www.google.com/search?q={query}",
        "notes_file": "~/.jarvis/notes.txt",
        "apps": {
            "spotify": "spotify.exe",
            "chrome": "chrome.exe",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "explorer": "explorer.exe",
            "youtube": "https://www.youtube.com",
            "whatsapp": "https://web.whatsapp.com",
        },
    },
    "ui": {"enabled": True, "always_on_top": False, "accent": "#33d6ff", "opacity": 0.97},
}

CONFIG_FILENAMES = ("config.yaml", "config.yml")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class Config:
    """Dotted-path access over the merged configuration mapping."""

    def __init__(self, data: dict[str, Any], path: Path | None = None):
        self.data = data
        self.path = path

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node if node is not None else default

    def __getitem__(self, dotted: str) -> Any:
        return self.get(dotted)


def find_config_file(start: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if env_path := os.environ.get("JARVIS_CONFIG"):
        candidates.append(Path(env_path).expanduser())
    base = start or Path.cwd()
    for directory in (base, *base.parents, Path.home() / ".jarvis"):
        candidates.extend(directory / name for name in CONFIG_FILENAMES)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration, falling back to built-in defaults."""
    config_path = Path(path).expanduser() if path else find_config_file()
    if config_path and config_path.is_file():
        with open(config_path, encoding="utf-8") as handle:
            user_data = yaml.safe_load(handle) or {}
        return Config(_deep_merge(DEFAULTS, user_data), config_path)
    return Config(copy.deepcopy(DEFAULTS), None)
