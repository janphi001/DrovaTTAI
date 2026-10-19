from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from drova_voice.lines import Line

DEFAULT_BATCH_CHARS = 100_000
SAMPLE_TARGET_CHARS = 80  # Beispielzeile: mittellang, damit Stimme und Betonung hörbar sind


@dataclass(frozen=True)
class SpeakerStat:
    name: str  # klein
    display: str  # Schreibung der ersten Zeile
    lines: int
    chars: int
    trees: frozenset[str]


@dataclass(frozen=True)
class Batch:
    n: int
    speakers: tuple[str, ...]
    lines: int
    chars: int
    player: bool  # enthält zusätzlich die Aussagen des Spielers


def is_named_dialog(line: Line) -> bool:
    """Zeile eines benannten Sprechers, die gesprochen wird (Plan 5: ohne Barks, generische Sprecher und Spieler)."""
    return not line.skip and line.category == "dialog" and not line.generic and bool(line.actor)


def speaker_stats(lines: Sequence[Line]) -> list[SpeakerStat]:
    acc: dict[str, list] = {}
    for line in lines:
        if not is_named_dialog(line):
            continue
        entry = acc.setdefault(line.actor.lower(), [line.actor, 0, 0, set()])
        entry[1] += 1
        entry[2] += len(line.speech)
        entry[3].add(line.tree)
    stats = [SpeakerStat(name, v[0], v[1], v[2], frozenset(v[3])) for name, v in acc.items()]
    return sorted(stats, key=lambda s: (-s.lines, s.name))


def _sample_rank(line: Line) -> tuple[int, str]:
    return abs(len(line.speech) - SAMPLE_TARGET_CHARS), line.id


def sample_lines(lines: Sequence[Line]) -> list[Line]:
    """Je benanntem Sprecher eine Zeile (deterministisch), nach Sprechername sortiert."""
    best: dict[str, Line] = {}
    for line in lines:
        if not is_named_dialog(line):
            continue
        name = line.actor.lower()
        if name not in best or _sample_rank(line) < _sample_rank(best[name]):
            best[name] = line
    return [best[name] for name in sorted(best)]


def plan_batches(lines: Sequence[Line], max_chars: int = DEFAULT_BATCH_CHARS) -> list[Batch]:
    groups: list[tuple[list[str], int, int]] = []
    names: list[str] = []
    n_lines = n_chars = 0
    for s in speaker_stats(lines):
        if names and n_chars + s.chars > max_chars:
            groups.append((names, n_lines, n_chars))
            names, n_lines, n_chars = [], 0, 0
        names.append(s.name)
        n_lines += s.lines
        n_chars += s.chars
    if names:
        groups.append((names, n_lines, n_chars))
    batches = [Batch(i, tuple(g[0]), g[1], g[2], False) for i, g in enumerate(groups, start=1)]
    player = [l for l in lines if l.category == "player" and not l.skip]
    if player:
        extra_chars = sum(len(l.speech) for l in player)
        if batches:
            last = batches[-1]
            batches[-1] = replace(
                last, lines=last.lines + len(player), chars=last.chars + extra_chars, player=True
            )
        else:
            batches.append(Batch(1, (), len(player), extra_chars, True))
    return batches


def write_batches(path: Path, batches: Sequence[Batch], max_chars: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "max_chars": max_chars,
        "batches": [
            {
                "n": b.n,
                "speakers": list(b.speakers),
                "lines": b.lines,
                "chars": b.chars,
                "player": b.player,
            }
            for b in batches
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def read_batches(path: Path) -> list[Batch]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return [
        Batch(
            int(b["n"]), tuple(b["speakers"]), int(b["lines"]), int(b["chars"]), bool(b["player"])
        )
        for b in data["batches"]
    ]


def batch_lines(lines: Sequence[Line], batch: Batch) -> list[Line]:
    names = set(batch.speakers)
    return [
        l
        for l in lines
        if (l.category == "dialog" and not l.generic and l.actor.lower() in names)
        or (batch.player and l.category == "player")
    ]
