from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from drova_voice.fish_voices import AGES, TYPES
from drova_voice.jsonl import write_jsonl
from drova_voice.lines import Line
from drova_voice.selection import is_named_dialog, speaker_stats

SOURCES = ("llm", "manual")
LOW_CONFIDENCE = 0.6
MAX_NOTE = 200


@dataclass(frozen=True)
class Profile:
    speaker: str  # klein
    gender: str  # m | f
    age: str  # kind | jung | mittel | alt
    type: str | None  # riese | zwerg | schurke | None
    confidence: float
    note: str  # ein Satz zum Charakter, keine Zitate (liegt im Git)
    source: str  # llm | manual

    def to_dict(self) -> dict:
        return {"speaker": self.speaker, "gender": self.gender, "age": self.age, "type": self.type or "",
                "confidence": self.confidence, "note": self.note, "source": self.source}

    @classmethod
    def from_dict(cls, d: Mapping) -> "Profile":
        speaker = str(d.get("speaker") or "").strip().lower()
        if not speaker:
            raise ValueError("speaker fehlt")
        if d.get("gender") not in ("m", "f"):
            raise ValueError(f"{speaker}: gender muss 'm' oder 'f' sein")
        if d.get("age") not in AGES:
            raise ValueError(f"{speaker}: age muss eines von {', '.join(AGES)} sein")
        type_ = d.get("type") or None
        if type_ is not None and type_ not in TYPES:
            raise ValueError(f"{speaker}: type muss leer oder eines von {', '.join(TYPES)} sein")
        try:
            confidence = float(d.get("confidence", 0.5))
        except (TypeError, ValueError):
            raise ValueError(f"{speaker}: confidence ist keine Zahl") from None
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"{speaker}: confidence außerhalb 0..1")
        source = d.get("source", "llm")
        if source not in SOURCES:
            raise ValueError(f"{speaker}: source muss llm oder manual sein")
        return cls(speaker, d["gender"], d["age"], type_, confidence, str(d.get("note") or "").strip()[:MAX_NOTE], source)


def read_profiles(path: Path) -> dict[str, Profile]:
    path = Path(path)
    if not path.exists():
        return {}
    result: dict[str, Profile] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), start=1):
        if not raw.strip():
            continue
        try:
            p = Profile.from_dict(json.loads(raw))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"{path}: Zeile {number} ungültig ({e})") from e
        result[p.speaker] = p
    return result


def write_profiles(path: Path, profiles: Iterable[Profile]) -> None:
    write_jsonl(path, (p.to_dict() for p in sorted(profiles, key=lambda p: p.speaker)))


def merge_import(existing: Mapping[str, Profile], rows: Iterable[Mapping], known: set[str]) -> tuple[dict[str, Profile], list[str]]:
    """LLM-Steckbriefe einlesen: Quelle wird auf llm gesetzt, manual-Zeilen bleiben, unbekannte Sprecher werden gemeldet."""
    merged = dict(existing)
    errors: list[str] = []
    for number, row in enumerate(rows, start=1):
        try:
            p = Profile.from_dict({**row, "source": "llm"})
        except ValueError as e:
            errors.append(f"Zeile {number}: {e}")
            continue
        if p.speaker not in known:
            errors.append(f"Zeile {number}: Sprecher '{p.speaker}' kommt im Export nicht vor")
            continue
        if p.speaker in merged and merged[p.speaker].source == "manual":
            continue
        merged[p.speaker] = p
    return merged, errors


def prepare_packets(lines: Sequence[Line], profiles: Mapping[str, Profile], size: int = 20, max_own: int = 40,
                    max_mentions: int = 12, include_known: bool = False) -> list[list[dict]]:
    """Pakete für Subagents: je Sprecher ein Auszug seiner Zeilen und Zeilen anderer, die ihn nennen."""
    dialog = [l for l in lines if is_named_dialog(l)]
    own_by_name: dict[str, list[Line]] = {}
    for l in sorted(dialog, key=lambda l: l.id):
        own_by_name.setdefault(l.actor.lower(), []).append(l)
    entries = []
    for s in speaker_stats(lines):
        if s.name in profiles and not include_known:
            continue
        own = own_by_name[s.name]
        own = own[:: max(1, len(own) // max_own)][:max_own]
        pattern = re.compile(rf"\b{re.escape(s.display)}\b")
        mentions = [{"by": l.actor, "text": l.speech} for l in dialog
                    if l.actor.lower() != s.name and pattern.search(l.speech)][:max_mentions]
        entries.append({"speaker": s.name, "display": s.display, "lines": s.lines, "trees": sorted(s.trees)[:8],
                        "own": [l.speech for l in own], "mentions": mentions})
    return [entries[i:i + size] for i in range(0, len(entries), size)]
