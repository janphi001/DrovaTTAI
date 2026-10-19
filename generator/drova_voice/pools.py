from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import yaml

from drova_voice.ids import VARIANT_SEP, with_variant
from drova_voice.lines import Line

GENDERS = ("m", "w")


def load_pools(path: Path, voices: Mapping[str, object]) -> dict[str, str]:
    """casting/pools.yaml -> {Tag: Stimmenschlüssel}; Tag = v<Geschlecht><Position ab 1>. Fehlt die Datei, ist der Pool leer."""
    path = Path(path)
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pools = raw.get("pools") if isinstance(raw, dict) else None
    if not isinstance(pools, dict):
        raise ValueError(f"{path}: 'pools:' mit den Listen m und w fehlt")
    result: dict[str, str] = {}
    for gender, keys in pools.items():
        if str(gender) not in GENDERS:
            raise ValueError(f"{path}: Unbekanntes Geschlecht '{gender}' (erlaubt: m, w)")
        if keys is None:
            keys = []
        elif not isinstance(keys, list):
            raise ValueError(f"{path}: Pool '{gender}' muss eine Liste von Stimmen sein")
        for number, key in enumerate(keys, start=1):
            voice = str(key).lower()
            if voice not in voices:
                raise ValueError(
                    f"{path}: Unbekannte Stimme '{voice}' im Pool '{gender}' (Schlüssel aus casting/fish_voices.yaml)"
                )
            result[f"v{gender}{number}"] = voice
    return result


def expand_pool_lines(lines: Sequence[Line], pools: Mapping[str, str]) -> list[Line]:
    """Ersetzt jede sprechbare Zeile eines generischen Sprechers durch eine Zeile je Poolstimme (`<ID>#v<g><n>`).
    Benannte, übersprungene und schon variantenhaltige Zeilen bleiben unverändert."""
    if not pools:
        return list(lines)
    out: list[Line] = []
    for line in lines:
        if not line.generic or line.skip or line.pool or VARIANT_SEP in line.id:
            out.append(line)
            continue
        for tag in sorted(pools):
            out.append(replace(line, id=with_variant(line.id, tag), pool=tag))
    return out


TEACHER_ACTOR = "Teacher"
TEACHER_PREFIX = "t_"


def load_teachers(path: Path) -> list[str]:
    """casting/teachers.yaml -> Sprecherschlüssel der Lehrer (klein, ohne Doppelte). Fehlt die Datei, gibt es keine."""
    path = Path(path)
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = raw.get("teachers") if isinstance(raw, dict) else None
    if not isinstance(names, list):
        raise ValueError(f"{path}: 'teachers:' mit einer Liste von Sprechern fehlt")
    result: list[str] = []
    for name in names:
        key = str(name).lower()
        if not key or VARIANT_SEP in key or "|" in key:
            raise ValueError(f"{path}: Unzulässiger Lehrername '{name}'")
        if key not in result:
            result.append(key)
    return result


def expand_teacher_lines(expanded: Sequence[Line], base: Sequence[Line], teachers: Sequence[str]) -> list[Line]:
    """Hängt an `expanded` je sprechbarer generischer Lehrerzeile (Sprecher „Teacher“) aus `base` eine Variante je
    Lehrer an (`<ID>#t_<lehrer>`); die Mod spielt sie, wenn die Figur dieser Lehrer ist, sonst die Poolstimme."""
    out = list(expanded)
    for line in base:
        if line.actor != TEACHER_ACTOR or not line.generic or line.skip or line.pool or VARIANT_SEP in line.id:
            continue
        for name in teachers:
            tag = TEACHER_PREFIX + name
            out.append(replace(line, id=with_variant(line.id, tag), pool=tag))
    return out
