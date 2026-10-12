from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_ID_RE = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True)
class FishVoice:
    key: str
    id: str
    label: str
    gender: str
    region: str


def load_fish_voices(path: Path) -> dict[str, FishVoice]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    voices = raw.get("voices") if isinstance(raw, dict) else None
    if not isinstance(voices, dict) or not voices:
        raise ValueError(f"{path}: Abschnitt 'voices' fehlt oder ist leer")
    table = {}
    for key, v in voices.items():
        vid = str(v.get("id", ""))
        if not _ID_RE.fullmatch(vid):
            raise ValueError(f"{path}: Stimme '{key}' hat keine gültige ID (32 Hex-Zeichen erwartet)")
        if v.get("gender") not in ("m", "f"):
            raise ValueError(f"{path}: Stimme '{key}': gender muss 'm' oder 'f' sein")
        table[str(key).lower()] = FishVoice(str(key).lower(), vid, str(v.get("label", key)), v["gender"], str(v.get("region", "de")))
    return table


def resolve_fish_voice(table: dict[str, FishVoice], name_or_id: str) -> FishVoice:
    if name_or_id.lower() in table:
        return table[name_or_id.lower()]
    if _ID_RE.fullmatch(name_or_id):
        return FishVoice(name_or_id[:8], name_or_id, name_or_id, "?", "?")
    raise ValueError(f"Unbekannte Fish-Stimme '{name_or_id}' (Name aus casting/fish_voices.yaml oder 32-stellige ID)")
