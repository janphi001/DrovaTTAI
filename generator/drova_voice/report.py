from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from drova_voice.casting import Casting
from drova_voice.lines import Line
from drova_voice.synth import SKIP_NO_VOICE

ORDER = ("installiert", "kodiert", "erzeugt", "fehler", "offen")
_PRODUCED = frozenset({"installiert", "kodiert", "erzeugt"})


@dataclass
class CategoryStatus:
    counts: Counter = field(default_factory=Counter)
    flagged: int = 0

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _status(
    line: Line,
    casting: Casting,
    synth: Mapping[str, dict],
    encoded: Mapping[str, dict],
    index: Mapping[str, dict],
) -> str:
    if line.skip:
        return f"übersprungen: {line.skip}"
    if casting.voice_for(line) is None:
        return f"übersprungen: {SKIP_NO_VOICE}"
    if line.id in index:
        return "installiert"
    if line.id in encoded:
        return "kodiert"
    row = synth.get(line.id)
    if row is not None:
        return "erzeugt" if row.get("ok") else "fehler"
    return "offen"


def build_report(
    lines: Sequence[Line],
    casting: Casting,
    synth_rows: Mapping[str, dict],
    encoded: Mapping[str, dict],
    index_entries: Mapping[str, dict],
) -> dict[str, CategoryStatus]:
    result: dict[str, CategoryStatus] = {}
    for line in lines:
        status = result.setdefault(line.category, CategoryStatus())
        label = _status(line, casting, synth_rows, encoded, index_entries)
        status.counts[label] += 1
        row = synth_rows.get(line.id)
        if label in _PRODUCED and row and row.get("ok") and row.get("flagged"):
            status.flagged += 1
    return result


def format_report(statuses: Mapping[str, CategoryStatus]) -> str:
    out = []
    for category in sorted(statuses):
        st = statuses[category]
        parts = [f"{k}: {st.counts[k]}" for k in ORDER if st.counts[k]]
        parts += [f"{k}: {n}" for k, n in sorted(st.counts.items()) if k.startswith("übersprungen")]
        flag = f"; auffällige Dauer: {st.flagged}" if st.flagged else ""
        out.append(f"{category}: {st.total} Zeilen -> " + (", ".join(parts) or "-") + flag)
    return "\n".join(out) or "keine Zeilen"


GAP_STATUSES = ("kodiert", "erzeugt", "fehler", "offen", f"übersprungen: {SKIP_NO_VOICE}")


def build_speaker_report(
    lines: Sequence[Line],
    casting: Casting,
    synth_rows: Mapping[str, dict],
    encoded: Mapping[str, dict],
    index_entries: Mapping[str, dict],
) -> dict[str, Counter]:
    """Status je Sprecher; Barks und generische Sprecher gehören nicht zu Plan 5."""
    result: dict[str, Counter] = {}
    for line in lines:
        if line.category == "bark" or line.generic:
            continue
        who = "(Spieler)" if line.category == "player" else line.actor
        result.setdefault(who, Counter())[
            _status(line, casting, synth_rows, encoded, index_entries)
        ] += 1
    return result


def format_speaker_report(report: Mapping[str, Counter], casting: Casting) -> str:
    def total(counts: Counter) -> int:
        return sum(counts.values())

    out = []
    gap_lines = gap_speakers = 0
    for who in sorted(report, key=lambda w: (-total(report[w]), w)):
        counts = report[who]
        voice = casting.default_player if who == "(Spieler)" else casting.speakers.get(who.lower())
        parts = [f"{counts[k]} {k}" for k in ORDER if counts[k]]
        parts += [f"{n} {k}" for k, n in sorted(counts.items()) if k.startswith("übersprungen")]
        out.append(
            f"{who} ({voice or 'keine Stimme'}): {total(counts)} Zeilen -> " + ", ".join(parts)
        )
        gaps = sum(counts[k] for k in GAP_STATUSES)
        if gaps:
            gap_lines += gaps
            gap_speakers += 1
    out.append(
        f"Lücken: {gap_lines} Zeilen bei {gap_speakers} Sprechern (nicht installiert, ohne Stimme eingeschlossen)"
    )
    return "\n".join(out)
