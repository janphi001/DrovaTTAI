from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_ID_RE = re.compile(r"[0-9a-f]{32}")

AGES = ("kind", "jung", "mittel", "alt")
TYPES = ("riese", "zwerg", "schurke")


@dataclass(frozen=True)
class FishVoice:
    key: str
    id: str
    label: str
    gender: str
    region: str
    age: str | None = None
    type: str | None = None


@dataclass(frozen=True)
class FishVariant:
    """Abwandlung einer Basisstimme per ffmpeg (Rezept siehe casting/fish_voices.yaml)."""
    key: str
    base: str
    label: str
    gender: str
    age: str | None
    type: str | None
    pitch: float
    formant: float
    tempo: float


@dataclass(frozen=True)
class Candidate:
    """Eine Stimme oder Variante, wie die Zuteilung sie sieht."""
    key: str
    gender: str
    age: str | None
    type: str | None
    variant: bool


@dataclass(frozen=True)
class Catalog:
    voices: dict[str, FishVoice]
    variants: dict[str, FishVariant]
    fallbacks: dict[str, str]  # Stimmenschlüssel -> Ersatz, wenn die Fish-ID fehlt (synth wechselt nicht von selbst)

    def synth_table(self) -> dict[str, FishVoice]:
        """Schlüssel -> Stimme, mit der Fish aufgerufen wird (Varianten nutzen die Basisstimme)."""
        table = dict(self.voices)
        for key, v in self.variants.items():
            table[key] = self.voices[v.base]
        return table

    def known(self) -> dict[str, object]:
        return {**self.voices, **self.variants}

    def candidates(self) -> list[Candidate]:
        out = [Candidate(v.key, v.gender, v.age, v.type, False) for v in self.voices.values()]
        out += [Candidate(v.key, v.gender, v.age, v.type, True) for v in self.variants.values()]
        return sorted(out, key=lambda c: c.key)


def _optional(value, allowed: tuple[str, ...], field: str, key: str, path: Path) -> str | None:
    if value is None or value == "":
        return None
    if value not in allowed:
        raise ValueError(f"{path}: '{key}': {field} muss eines von {', '.join(allowed)} sein")
    return str(value)


def _read(path: Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _voices(raw: dict, path: Path) -> dict[str, FishVoice]:
    voices = raw.get("voices")
    if not isinstance(voices, dict) or not voices:
        raise ValueError(f"{path}: Abschnitt 'voices' fehlt oder ist leer")
    table = {}
    for key, v in voices.items():
        vid = str(v.get("id", ""))
        if not _ID_RE.fullmatch(vid):
            raise ValueError(f"{path}: Stimme '{key}' hat keine gültige ID (32 Hex-Zeichen erwartet)")
        if v.get("gender") not in ("m", "f"):
            raise ValueError(f"{path}: Stimme '{key}': gender muss 'm' oder 'f' sein")
        age = _optional(v.get("age"), AGES, "age", key, path)
        table[str(key).lower()] = FishVoice(str(key).lower(), vid, str(v.get("label", key)), v["gender"],
                                            str(v.get("region", "de")), age, None)
    return table


def _positive(v: dict, name: str, key: str, path: Path) -> float:
    try:
        value = float(v[name])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{path}: Variante '{key}': {name} fehlt oder ist keine Zahl") from None
    if value <= 0:
        raise ValueError(f"{path}: Variante '{key}': {name} muss größer als 0 sein")
    return value


def _variants(raw: dict, voices: dict[str, FishVoice], path: Path) -> dict[str, FishVariant]:
    out: dict[str, FishVariant] = {}
    for key, v in (raw.get("variants") or {}).items():
        name = str(key).lower()
        if name in voices or name in out:
            raise ValueError(f"{path}: Variante '{key}' ist doppelt (auch Stimmenschlüssel sind belegt)")
        base = str(v.get("base", "")).lower()
        if base not in voices:
            raise ValueError(f"{path}: Variante '{key}': Basis '{base}' steht nicht unter voices")
        if v.get("gender") not in ("m", "f"):
            raise ValueError(f"{path}: Variante '{key}': gender muss 'm' oder 'f' sein")
        out[name] = FishVariant(
            name, base, str(v.get("label", key)), v["gender"],
            _optional(v.get("age"), AGES, "age", key, path), _optional(v.get("type"), TYPES, "type", key, path),
            _positive(v, "pitch", key, path), _positive(v, "formant", key, path), _positive(v, "tempo", key, path))
    return out


def load_fish_voices(path: Path) -> dict[str, FishVoice]:
    return _voices(_read(path), Path(path))


def _fallbacks(raw: dict, voices: dict[str, FishVoice], variants: dict[str, FishVariant], path: Path) -> dict[str, str]:
    known = set(voices) | set(variants)
    out: dict[str, str] = {}
    for key, spec in (raw.get("voices") or {}).items():
        if not isinstance(spec, dict):
            continue
        target = spec.get("fallback")
        if target is None or target == "":
            continue
        out[str(key).lower()] = str(target).lower()
    section = raw.get("fallbacks") or {}
    if not isinstance(section, dict):
        raise ValueError(f"{path}: Abschnitt 'fallbacks' muss aus 'Stimme: Ersatz'-Zeilen bestehen")
    for key, target in section.items():
        name = str(key).lower()
        if name in out:
            raise ValueError(f"{path}: Fallback für '{key}' steht doppelt (Feld fallback und Abschnitt fallbacks)")
        if target is None or str(target).strip() == "":
            raise ValueError(f"{path}: Fallback für '{key}' ist leer")
        out[name] = str(target).lower()
    for key, target in out.items():
        if key not in known:
            raise ValueError(f"{path}: Fallback für unbekannte Stimme '{key}'")
        if target not in known:
            raise ValueError(f"{path}: Fallback '{target}' für '{key}' steht nicht in fish_voices.yaml")
        if target == key:
            raise ValueError(f"{path}: Fallback für '{key}' zeigt auf sich selbst")
    for start in out:
        seen: set[str] = set()
        current: str | None = start
        while current in out:
            if current in seen:
                raise ValueError(f"{path}: Fallback-Kreis ab '{start}'")
            seen.add(current)
            current = out[current]
    return out


def load_catalog(path: Path) -> Catalog:
    raw = _read(path)
    file = Path(path)
    voices = _voices(raw, file)
    variants = _variants(raw, voices, file)
    return Catalog(voices, variants, _fallbacks(raw, voices, variants, file))


def resolve_fish_voice(table: dict[str, FishVoice], name_or_id: str) -> FishVoice:
    if name_or_id.lower() in table:
        return table[name_or_id.lower()]
    if _ID_RE.fullmatch(name_or_id):
        return FishVoice(name_or_id[:8], name_or_id, name_or_id, "?", "?")
    raise ValueError(f"Unbekannte Fish-Stimme '{name_or_id}' (Name aus casting/fish_voices.yaml oder 32-stellige ID)")
