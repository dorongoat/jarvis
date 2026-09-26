"""Entry point: ``python -m jarvis`` (HUD) or ``python -m jarvis --cli``."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .core.assistant import Assistant, Event
from .lang import detect_language


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jarvis", description="JARVIS bilingual voice assistant")
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--cli", action="store_true", help="run without the HUD window")
    parser.add_argument("--no-voice", action="store_true", help="disable microphone input")
    parser.add_argument("--mute", action="store_true", help="disable spoken replies")
    parser.add_argument("--say", help="speak one command and exit")
    parser.add_argument("--list-mics", action="store_true", help="list microphones and exit")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def run_cli(assistant: Assistant, speak: bool, voice: bool) -> None:
    def printer(event: Event) -> None:
        if event.kind == "user":
            print(f"> {event.text}")
        elif event.kind in {"jarvis", "log"}:
            print(f"JARVIS: {event.text}")

    assistant.listener = printer
    assistant.voice_enabled = voice
    if voice:
        assistant.start(greet=speak)
    print("JARVIS ready. Type a command, or Ctrl+C to quit. / ג'ארוויס מוכן. הקלד פקודה.")
    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit", "יציאה"}:
                break
            assistant.handle_text(line, detect_language(line), speak=speak)
    except KeyboardInterrupt:
        pass
    finally:
        assistant.stop()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.list_mics:
        from .audio.stt import list_microphones

        for index, name in enumerate(list_microphones()):
            print(f"{index}: {name}")
        return 0

    config = load_config(args.config)
    assistant = Assistant(config)

    if args.say:
        assistant.voice_enabled = False
        print(assistant.handle_text(args.say, speak=not args.mute))
        return 0

    if args.cli or not config.get("ui.enabled", True):
        run_cli(assistant, speak=not args.mute, voice=not args.no_voice)
        return 0

    try:
        from .ui.hud import run_hud
    except ImportError as exc:
        print(f"PyQt6 is not installed ({exc}); falling back to the console interface.", file=sys.stderr)
        run_cli(assistant, speak=not args.mute, voice=not args.no_voice)
        return 0

    return run_hud(assistant, voice=not args.no_voice, speak=not args.mute)


if __name__ == "__main__":
    raise SystemExit(main())
