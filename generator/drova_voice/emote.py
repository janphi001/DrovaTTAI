from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.emotions import EmotionTag, from_stage_directions
from drova_voice.jsonl import write_jsonl
from drova_voice.lines import Line
from drova_voice.speech_text import StageDirection

KEEP_SOURCES = ("llm", "manual")


def merge_emotions(existing: Mapping[str, EmotionTag], lines: Sequence[Line]) -> dict[str, EmotionTag]:
    """Regieanweisungen -> Tags für die gewählten Zeilen; llm/manual-Zeilen und alles außerhalb der Auswahl bleibt."""
    selected = {l.id for l in lines}
    result = {i: t for i, t in existing.items() if i not in selected or t.source in KEEP_SOURCES}
    for line in lines:
        if line.skip or line.id in result or not line.stage:
            continue
        tag = from_stage_directions([StageDirection(s["text"], int(s["pos"])) for s in line.stage])
        if tag.source == "stage":
            result[line.id] = tag
    return result


def read_emotions(path: Path) -> dict[str, EmotionTag]:
    path = Path(path)
    if not path.exists():
        return {}
    result: dict[str, EmotionTag] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
            result[row["id"]] = EmotionTag.from_dict(row)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{path}: Zeile {number} ungültig ({e})") from e
    return result


def write_emotions(path: Path, emotions: Mapping[str, EmotionTag]) -> None:
    write_jsonl(path, ({"id": i, **emotions[i].to_dict()} for i in sorted(emotions)))
