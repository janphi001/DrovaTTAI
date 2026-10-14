from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line


@dataclass(frozen=True)
class Casting:
    default_player: str
    speakers: dict[str, str]  # Sprechername (klein) -> Stimmenschlüssel aus fish_voices.yaml

    def voice_for(self, line: Line) -> str | None:
        if line.category == "player":
            return self.default_player
        return self.speakers.get(line.actor.lower())


@dataclass(frozen=True)
class CastReport:
    missing: dict[str, int]  # Sprecher ohne Stimme -> Zeilenzahl
    usage: dict[str, int]  # Stimme -> Zeilenzahl


def load_casting(path: Path, voices: Mapping[str, FishVoice]) -> Casting:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Datei muss aus 'Schlüssel: Wert'-Zeilen bestehen")
    default_player = str(raw.get("default_player") or "").lower()
    if default_player not in voices:
        raise ValueError(f"{path}: default_player '{default_player}' fehlt oder steht nicht in fish_voices.yaml")
    speakers: dict[str, str] = {}
    for name, spec in (raw.get("speakers") or {}).items():
        key = str(name).lower()
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: Sprecher '{name}' muss als '{name}: {{voice: <Stimme>}}' angegeben werden")
        voice = str(spec.get("voice", "")).lower()
        if key in speakers:
            raise ValueError(f"{path}: Sprecher '{name}' ist doppelt (Groß-/Kleinschreibung zählt nicht)")
        if voice not in voices:
            raise ValueError(f"{path}: Unbekannte Stimme '{voice}' für Sprecher '{name}' (Schlüssel aus casting/fish_voices.yaml)")
        speakers[key] = voice
    return Casting(default_player, speakers)


def cast_report(lines: Sequence[Line], casting: Casting) -> CastReport:
    missing: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    for line in lines:
        if line.skip:
            continue
        voice = casting.voice_for(line)
        if voice is None:
            missing[line.actor or "(ohne Sprecher)"] += 1
        else:
            usage[voice] += 1
    return CastReport(dict(missing), dict(usage))
