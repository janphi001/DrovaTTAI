from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from drova_voice.fish_voices import AGES, Candidate
from drova_voice.profiles import Profile
from drova_voice.selection import SpeakerStat

AGE_RANK = {age: i for i, age in enumerate(AGES)}
UNKNOWN_AGE_DISTANCE = 1  # offizielle Stimmen ohne Altersangabe passen mäßig zu jedem Alter

# Kosten (kleiner ist besser)
W_AGE = 3.0  # je Altersstufe Abstand
W_TYPE_MATCH = 10.0  # Abzug, wenn der verlangte Typ (Riese, Zwerg, Schurke) passt
W_TYPE_EXTRA = 30.0  # Aufschlag, wenn eine Typ-Variante für eine gewöhnliche Figur benutzt würde
W_KIND_ONLY = 20.0  # Kinderstimmen nur für Kinder
W_VARIANT = 2.0  # Basisstimmen vor Varianten
W_SPEAKER = 1.5  # je Sprecher, der die Stimme schon hat
W_LINES = 0.01  # je Zeile, die die Stimme schon hat
W_SHARED_TREE = 20.0  # je Dialogbaum, in dem schon jemand mit dieser Stimme spricht


@dataclass
class Assignment:
    voices: dict[str, str] = field(default_factory=dict)  # Sprecher -> Schlüssel (nur neu zugeteilte)
    open: list[str] = field(default_factory=list)  # Sprecher ohne brauchbaren Steckbrief
    emergency: dict[str, str] = field(default_factory=dict)  # Sprecher -> Grund, warum die Stimme nur Notlösung ist


class _Load:
    def __init__(self) -> None:
        self.speakers: Counter[str] = Counter()
        self.lines: Counter[str] = Counter()
        self.trees: dict[str, set[str]] = defaultdict(set)

    def add(self, key: str, stat: SpeakerStat) -> None:
        self.speakers[key] += 1
        self.lines[key] += stat.lines
        self.trees[key] |= stat.trees


def mismatch(profile: Profile, cand: Candidate) -> str | None:
    if profile.type and cand.type != profile.type:
        return f"Typ '{profile.type}' ohne passende Stimme"
    if cand.type and not profile.type:
        return "Typ-Variante für gewöhnliche Figur"
    if profile.age == "kind" and cand.age != "kind":
        return "Kind ohne Kinderstimme"
    if cand.age and abs(AGE_RANK[cand.age] - AGE_RANK[profile.age]) >= 2:
        return "Alter weicht stark ab"
    return None


def _cost(profile: Profile, cand: Candidate, load: _Load, stat: SpeakerStat) -> float:
    distance = UNKNOWN_AGE_DISTANCE if cand.age is None else abs(AGE_RANK[cand.age] - AGE_RANK[profile.age])
    cost = W_AGE * distance
    if profile.type:
        if cand.type == profile.type:
            cost -= W_TYPE_MATCH
    elif cand.type:
        cost += W_TYPE_EXTRA
    if cand.age == "kind" and profile.age != "kind":
        cost += W_KIND_ONLY
    if cand.variant:
        cost += W_VARIANT
    cost += W_SPEAKER * load.speakers[cand.key] + W_LINES * load.lines[cand.key]
    cost += W_SHARED_TREE * len(stat.trees & load.trees[cand.key])
    return cost


def assign(stats: Sequence[SpeakerStat], profiles: Mapping[str, Profile], candidates: Sequence[Candidate],
           pinned: Mapping[str, str]) -> Assignment:
    """Stimmen verteilen, wichtigste Sprecher (meiste Zeilen) zuerst; `pinned` bleibt unberührt, zählt aber mit."""
    ordered = sorted(stats, key=lambda s: (-s.lines, s.name))
    by_name = {s.name: s for s in ordered}
    load = _Load()
    for name, key in pinned.items():
        if name in by_name:
            load.add(key, by_name[name])
    result = Assignment()
    for stat in ordered:
        if stat.name in pinned:
            continue
        profile = profiles.get(stat.name)
        options = [c for c in candidates if profile is not None and c.gender == profile.gender]
        if not options:
            result.open.append(stat.name)
            continue
        best = min(options, key=lambda c: (_cost(profile, c, load, stat), c.key))
        result.voices[stat.name] = best.key
        load.add(best.key, stat)
        why = mismatch(profile, best)
        if why:
            result.emergency[stat.name] = why
    return result
