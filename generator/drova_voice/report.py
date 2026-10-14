from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from drova_voice.casting import Casting
from drova_voice.lines import Line
from drova_voice.synth import SKIP_NO_VOICE

ORDER = ("installiert", "kodiert", "erzeugt", "fehler", "offen")


@dataclass
class CategoryStatus:
    counts: Counter = field(default_factory=Counter)
    flagged: int = 0

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _status(line: Line, casting: Casting, synth: Mapping[str, dict], encoded: Mapping[str, dict],
            index: Mapping[str, dict]) -> str:
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


def build_report(lines: Sequence[Line], casting: Casting, synth_rows: Mapping[str, dict],
                 encoded: Mapping[str, dict], index_entries: Mapping[str, dict]) -> dict[str, CategoryStatus]:
    result: dict[str, CategoryStatus] = {}
    for line in lines:
        status = result.setdefault(line.category, CategoryStatus())
        status.counts[_status(line, casting, synth_rows, encoded, index_entries)] += 1
        row = synth_rows.get(line.id)
        if row and row.get("ok") and row.get("flagged"):
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
