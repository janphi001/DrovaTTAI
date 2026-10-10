from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields


@dataclass(frozen=True)
class SynthRequest:
    id: str
    text: str
    out_path: str
    voice: str | None = None
    reference: str | None = None
    params: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass(frozen=True)
class SynthResponse:
    id: str | None
    ok: bool
    out_path: str | None = None
    sample_rate: int | None = None
    duration: float | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "SynthResponse":
        return cls(**{f.name: d.get(f.name) for f in fields(cls)})
