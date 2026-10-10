from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from drova_voice.speech_text import StageDirection

EMOTIONS = ("neutral", "angry", "contemplative", "excited", "joyful", "mundane",
            "nervous", "sad", "stern", "surprised", "tender")
EVENTS = ("gasp", "giggle", "growl", "gulp", "laugh", "pause", "scoff", "sigh", "sob", "um")
SOURCES = ("default", "stage", "llm", "manual")


@dataclass(frozen=True)
class Event:
    tag: str
    pos: int


@dataclass
class EmotionTag:
    emotion: str = "neutral"
    intensity: float = 0.0
    events: list[Event] = field(default_factory=list)
    emphasis: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = "default"

    def __post_init__(self) -> None:
        if self.emotion not in EMOTIONS:
            raise ValueError(f"Unbekannte Emotion: {self.emotion}")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError(f"Intensität außerhalb 0..1: {self.intensity}")
        for ev in self.events:
            if ev.tag not in EVENTS:
                raise ValueError(f"Unbekannter Laut: {ev.tag}")
        if self.source not in SOURCES:
            raise ValueError(f"Unbekannte Quelle: {self.source}")

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "intensity": self.intensity,
            "events": [{"tag": e.tag, "pos": e.pos} for e in self.events],
            "emphasis": list(self.emphasis),
            "notes": list(self.notes),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionTag":
        return cls(
            emotion=d.get("emotion", "neutral"),
            intensity=float(d.get("intensity", 0.0)),
            events=[Event(e["tag"], int(e["pos"])) for e in d.get("events", [])],
            emphasis=list(d.get("emphasis", [])),
            notes=list(d.get("notes", [])),
            source=d.get("source", "default"),
        )


@dataclass(frozen=True)
class _Effect:
    emotion: str | None = None
    intensity: float = 0.0
    event: str | None = None
    note: str | None = None


# Reihenfolge: spezifische Wendungen vor einzelnen Verben.
_STAGE_RULES: list[tuple[str, _Effect]] = [
    ("knirscht mit den zähnen", _Effect("angry", 0.6)),
    ("runzelt die stirn", _Effect("stern", 0.3)),
    ("mustert", _Effect("contemplative", 0.3)),
    ("seufzt", _Effect(event="sigh")),
    ("stöhnt", _Effect(event="sigh")),
    ("schluchzt", _Effect("sad", 0.7, "sob")),
    ("weint", _Effect("sad", 0.8, "sob")),
    ("kichert", _Effect("joyful", 0.4, "giggle")),
    ("lacht", _Effect("joyful", 0.5, "laugh")),
    ("grinst", _Effect("joyful", 0.3)),
    ("lächelt", _Effect("tender", 0.3)),
    ("zwinkert", _Effect("joyful", 0.3)),
    ("knurrt", _Effect("angry", 0.5, "growl")),
    ("schnaubt", _Effect("stern", 0.4, "scoff")),
    ("grummelt", _Effect("stern", 0.4)),
    ("schluckt", _Effect("nervous", 0.4, "gulp")),
    ("keucht", _Effect(event="gasp")),
    ("räuspert", _Effect(event="um")),
    ("flüstert", _Effect(note="whisper")),
    ("hick", _Effect(note="drunk")),
    ("brüllt", _Effect("angry", 0.8)),
    ("schreit", _Effect("angry", 0.8)),
]
_COMPILED = [(re.compile(rf"\b{re.escape(needle)}"), eff) for needle, eff in _STAGE_RULES]


def from_stage_directions(stage: Sequence[StageDirection]) -> EmotionTag:
    tag = EmotionTag()
    matched = False
    for sd in stage:
        low = sd.text.lower()
        for pattern, eff in _COMPILED:
            if not pattern.search(low):
                continue
            matched = True
            if eff.emotion and eff.intensity > tag.intensity:
                tag.emotion, tag.intensity = eff.emotion, eff.intensity
            if eff.event:
                tag.events.append(Event(eff.event, sd.pos))
            if eff.note and eff.note not in tag.notes:
                tag.notes.append(eff.note)
    if matched:
        tag.source = "stage"
    return tag
