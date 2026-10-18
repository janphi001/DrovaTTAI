from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from drova_voice.emotions import EmotionTag, from_stage_directions
from drova_voice.jsonl import write_jsonl
from drova_voice.lines import Line
from drova_voice.profiles import Profile
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


@dataclass
class ImportResult:
    merged: dict[str, EmotionTag]
    imported: int
    kept: int  # manual- und stage-Zeilen bleiben, wie sie sind
    errors: list[str]


def prepare_emote_packets(lines: Sequence[Line], profiles: Mapping[str, Profile],
                          trees_per_packet: int = 20) -> list[list[dict]]:
    """Pakete für Subagents: je Dialogbaum alle sprechbaren Zeilen am Stück plus Steckbriefe der Sprecher."""
    if trees_per_packet < 1:
        raise ValueError("Paketgröße muss mindestens 1 sein")
    by_tree: dict[str, list[Line]] = {}
    for line in lines:
        if not line.skip and line.category != "bark":
            by_tree.setdefault(line.tree, []).append(line)
    trees = []
    for tree in sorted(by_tree):
        speakers = {}
        for line in by_tree[tree]:
            p = profiles.get(line.actor.lower())
            if p is not None:
                speakers[p.speaker] = {"gender": p.gender, "age": p.age, "note": p.note}
        trees.append({"tree": tree, "speakers": speakers,
                      "lines": [{"id": l.id, "actor": l.actor, "text": l.speech, "stage": [s["text"] for s in l.stage]}
                                for l in by_tree[tree]]})
    return [trees[i:i + trees_per_packet] for i in range(0, len(trees), trees_per_packet)]


def import_llm_emotions(existing: Mapping[str, EmotionTag], rows: Sequence[Mapping], valid_ids: set[str]) -> ImportResult:
    """LLM-Zeilen übernehmen: Quelle wird llm, manual und stage (feste Signale) bleiben, unbekannte IDs werden gemeldet."""
    merged = dict(existing)
    imported = kept = 0
    errors: list[str] = []
    for number, row in enumerate(rows, start=1):
        line_id = row.get("id")
        if line_id not in valid_ids:
            errors.append(f"Zeile {number}: unbekannte ID {line_id!r}")
            continue
        try:
            tag = EmotionTag.from_dict({**row, "source": "llm"})
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"Zeile {number} ({line_id}): {e}")
            continue
        if line_id in merged and merged[line_id].source in ("manual", "stage"):
            kept += 1
            continue
        merged[line_id] = tag
        imported += 1
    return ImportResult(merged, imported, kept, errors)
