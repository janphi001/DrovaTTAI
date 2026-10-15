#!/usr/bin/env python3
"""Fail if player choice lines can be synthesized or played.

The game leaves saySelection off. Commit 8a8f93d skips those lines in the
generator, and commit 5571c73 returns from ChoiceHook before it sets audio.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINES = ROOT / "generator" / "drova_voice" / "lines.py"
HOOK = ROOT / "mod" / "DrovaVoice" / "Playback" / "ChoiceHook.cs"


def _choice_bodies(text: str) -> list[str]:
    rows = text.splitlines()
    bodies: list[str] = []
    for index, line in enumerate(rows):
        if 'row.get("nodeType") == "choice"' not in line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        body: list[str] = []
        for nxt in rows[index + 1:]:
            if nxt.strip() == "":
                continue
            if len(nxt) - len(nxt.lstrip(" ")) <= indent:
                break
            body.append(nxt)
        bodies.append("\n".join(body))
    return bodies


def check_lines(text: str, label: str) -> list[str]:
    bodies = _choice_bodies(text)
    if not any("SKIP_PLAYER_CHOICE" in body for body in bodies):
        return [
            f"{label}: choice lines must set skip to SKIP_PLAYER_CHOICE in "
            "generator/drova_voice/lines.py. Player choice lines stay silent."
        ]
    for body in bodies:
        if "build_speech_text" in body or re.search(r"\bspeech\s*=", body):
            return [
                f"{label}: do not build speech for nodeType choice. "
                "Set skip to SKIP_PLAYER_CHOICE and leave the line silent."
            ]
    return []


def check_hook(text: str, label: str) -> list[str]:
    gate = text.find("if (!__instance.saySelection)")
    assign = text.find("statement.audio = clip")
    if gate < 0 or assign < 0 or gate > assign or "return;" not in text[gate:assign]:
        return [
            f"{label}: ChoiceHook must return before setting statement.audio "
            "when saySelection is false. Player choice lines stay silent."
        ]
    return []


def main(argv: list[str]) -> int:
    errors: list[str] = []
    if not argv:
        errors.extend(check_lines(LINES.read_text(encoding="utf-8"), LINES.relative_to(ROOT).as_posix()))
        errors.extend(check_hook(HOOK.read_text(encoding="utf-8"), HOOK.relative_to(ROOT).as_posix()))
    else:
        index = 0
        while index < len(argv):
            flag, path = argv[index], argv[index + 1]
            file = Path(path)
            text = file.read_text(encoding="utf-8")
            if flag == "--lines":
                errors.extend(check_lines(text, str(file)))
            elif flag == "--hook":
                errors.extend(check_hook(text, str(file)))
            else:
                errors.append("usage: player_choice_silent.py [--lines PATH] [--hook PATH]")
                break
            index += 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"player_choice_silent.py: {len(errors)} problem(s)", file=sys.stderr)
        return 1
    print("player_choice_silent.py: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
