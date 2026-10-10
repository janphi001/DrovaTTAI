from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

from drova_voice.emotions import from_stage_directions
from drova_voice.loc import read_loc_file
from drova_voice.player_name import NAME_TOKEN, make_name_variants
from drova_voice.speech_text import GVAR_RE, STAGE_RE, SpeechText, build_speech_text

BUCKETS = ("short", "long", "stage", "player_name", "gvar", "question", "exclaim", "normal")
BAKEOFF_GVAR_FALLBACK = "zehn"


@dataclass(frozen=True)
class Sample:
    sample_id: str
    source: str
    key: str
    raw: str
    text: str
    emotion: dict
    bucket: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Sample":
        return cls(**d)


def classify(raw: str) -> str:
    if NAME_TOKEN in raw:
        return "player_name"
    if "$GVAR:" in raw:
        return "gvar"
    if STAGE_RE.search(raw):
        return "stage"
    plain = raw.strip()
    if len(plain) <= 12:
        return "short"
    if len(plain) >= 200:
        return "long"
    if plain.endswith("?"):
        return "question"
    if plain.endswith("!"):
        return "exclaim"
    return "normal"


def _prepare(raw: str) -> SpeechText:
    prepared = make_name_variants(raw).arden if NAME_TOKEN in raw else raw
    values = {name: BAKEOFF_GVAR_FALLBACK for name in GVAR_RE.findall(prepared)}
    return build_speech_text(prepared, values)


def select_samples(loc_dir: Path, per_bucket: int = 4, seed: int = 42) -> list[Sample]:
    # Nicht sprechbare Zeilen (z. B. nur "*grinst*") gar nicht erst in den Pool,
    # sonst könnte ein Bucket je nach Zufall leer bleiben.
    pool: dict[str, list[tuple[str, str, str, SpeechText]]] = {b: [] for b in BUCKETS}
    for f in sorted((Path(loc_dir) / "Dialog").glob("NPC_*.loc")):
        for e in read_loc_file(f).entries:
            if not e.text.strip():
                continue
            st = _prepare(e.text)
            if st.is_speakable:
                pool[classify(e.text)].append((f.stem, e.key, e.text, st))
    rng = random.Random(seed)
    samples: list[Sample] = []
    for bucket in BUCKETS:
        candidates = pool[bucket]
        for source, key, raw, st in rng.sample(candidates, min(per_bucket, len(candidates))):
            tag = from_stage_directions(st.stage)
            samples.append(Sample(f"{bucket}_{len(samples):02d}", source, key, raw, st.text, tag.to_dict(), bucket))
    return samples
