from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from drova_voice.jsonl import replace_with_retry
from drova_voice.lines import Line

AUTO_HEADER = ("# ERZEUGT von `drova-voice cast --propose`. Nicht von Hand ändern: Korrekturen gehören in\n"
               "# casting/casting.yaml (gewinnt bei Überschneidung).\n")


@dataclass(frozen=True)
class Casting:
    default_player: str
    speakers: dict[str, str]  # Sprechername (klein) -> Stimmen- oder Variantenschlüssel aus fish_voices.yaml
    auto: frozenset[str] = frozenset()  # Sprecher, die nur aus casting_auto.yaml stammen

    def voice_for(self, line: Line) -> str | None:
        if line.category == "player":
            return self.default_player
        return self.speakers.get(line.actor.lower())


@dataclass(frozen=True)
class CastReport:
    missing: dict[str, int]  # Sprecher ohne Stimme -> Zeilenzahl
    usage: dict[str, int]  # Stimme -> Zeilenzahl


def _read_yaml(path: Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Datei muss aus 'Schlüssel: Wert'-Zeilen bestehen")
    return raw


def _speakers_from(path: Path, raw: dict, voices: Mapping[str, object]) -> dict[str, str]:
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
    return speakers


def load_casting(path: Path, voices: Mapping[str, object], auto_path: Path | None = None) -> Casting:
    raw = _read_yaml(path)
    default_player = str(raw.get("default_player") or "").lower()
    if default_player not in voices:
        raise ValueError(f"{path}: default_player '{default_player}' fehlt oder steht nicht in fish_voices.yaml")
    manual = _speakers_from(path, raw, voices)
    auto: dict[str, str] = {}
    if auto_path is not None and Path(auto_path).is_file():
        auto = _speakers_from(auto_path, _read_yaml(auto_path), voices)
    return Casting(default_player, {**auto, **manual}, frozenset(n for n in auto if n not in manual))


def write_auto_casting(path: Path, assignments: Mapping[str, str]) -> None:
    import json  # Namen als JSON-String schreiben: gültiges YAML auch mit Umlauten, Leerzeichen und Anführungszeichen

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = AUTO_HEADER + "speakers:\n" + "".join(
        f"  {json.dumps(name, ensure_ascii=False)}: {{voice: {assignments[name]}}}\n" for name in sorted(assignments))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    replace_with_retry(tmp, path)


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


def voice_speakers(lines: Sequence[Line], casting: Casting) -> dict[str, set[str]]:
    """Stimme -> Sprecher (klein), nur Dialogzeilen, die gesprochen werden."""
    out: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        if line.skip or line.category != "dialog":
            continue
        voice = casting.speakers.get(line.actor.lower())
        if voice:
            out[voice].add(line.actor.lower())
    return dict(out)


def tree_conflicts(lines: Sequence[Line], casting: Casting) -> list[tuple[str, str, list[str]]]:
    """(Baum, Stimme, Sprecher), wenn zwei Sprecher in einem Baum dieselbe Stimme haben."""
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for line in lines:
        if line.skip or line.category != "dialog":
            continue
        voice = casting.speakers.get(line.actor.lower())
        if voice:
            seen[(line.tree, voice)].add(line.actor.lower())
    return sorted((tree, voice, sorted(who)) for (tree, voice), who in seen.items() if len(who) > 1)
