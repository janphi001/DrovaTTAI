"""Fish-Modell, Sprache und Sampling an einer Stelle: Konfiguration, Cache-Schlüssel, Wechsel.

Der Cache-Schlüssel von `synth` enthält den Modell-Alias `fish-audio/<id>` (Handshake
des Workers) und die Parameter Sprache, Latenz, temperature und top_p. Ein anderer
Stempel trifft keine vorhandene WAV. Der Wechsel ist nur mit `--accept-model-change` erlaubt.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Kostenloses Entwickler-Modell. Laut Fish-Changelog bis 30.11.2026, danach Nachfolger s2.1-pro.
DEFAULT_FISH_MODEL = "s2.1-pro-free"
FREE_UNTIL = date(2026, 11, 30)
PAID_SUCCESSOR = "s2.1-pro"
# Header-Werte aus der TTS-Doku. Ein anderer Name fällt bei Fish still auf s2.1-pro zurück.
KNOWN_FISH_MODELS = ("s2.1-pro-free", "s2.1-pro", "s2-pro", "s1", "drama-3")
PAID_TTS_MODELS = ("s2.1-pro", "s2-pro", "s1")
STAMP_NAME = "fish-model.txt"
# Cache, der vor dem Stempel entstand: Standardprofil, also nur der Modell-Alias.
HISTORICAL_CACHE_MODEL = f"fish-audio/{DEFAULT_FISH_MODEL}"
DEFAULT_LANGUAGE = "de"
DEFAULT_LATENCY = "normal"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.7
LATENCY_VALUES = ("normal", "balanced", "low")
_LANG = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")


def _num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


@dataclass(frozen=True)
class FishProfile:
    """Was eine Fish-Zeile eindeutig macht. params() liegt im Cache-Schlüssel, stamp() im Stempel."""

    model_id: str
    language: str
    latency: str
    temperature: float
    top_p: float

    def cache_model(self) -> str:
        return cache_model_name(self.model_id)

    def params(self) -> dict:
        """Nur Abweichungen vom Standard. Der Standard ist genau das, womit der vorhandene Cache entstand
        (temperature und top_p 0.7, Latenz normal, Sprache de); so bleiben dessen Schlüssel gültig."""
        sampling: dict = {}
        if self.language != DEFAULT_LANGUAGE:
            sampling["language"] = self.language
        if self.latency != DEFAULT_LATENCY:
            sampling["latency"] = self.latency
        if self.temperature != DEFAULT_TEMPERATURE:
            sampling["temperature"] = self.temperature
        if self.top_p != DEFAULT_TOP_P:
            sampling["top_p"] = self.top_p
        return sampling

    def stamp(self) -> str:
        parts = [
            f"{name}={_num(value) if isinstance(value, float) else value}"
            for name, value in sorted(self.params().items())
        ]
        return " ".join([self.cache_model(), *parts])

    def worker_env(self) -> dict[str, str]:
        return {
            "FISH_MODEL": self.model_id,
            "FISH_LANGUAGE": self.language,
            "FISH_LATENCY": self.latency,
            "FISH_TEMPERATURE": _num(self.temperature),
            "FISH_TOP_P": _num(self.top_p),
        }


def cache_model_name(model_id: str) -> str:
    """Alias im Cache-Schlüssel. Muss zum Handshake des Fish-Workers passen."""
    return f"fish-audio/{model_id}"


def resolve_fish_model(configured: str | None, env: Mapping[str, str] | None = None) -> str:
    """FISH_MODEL in der Umgebung, sonst fish_model aus der Konfiguration, sonst der Standard."""
    source = os.environ if env is None else env
    chosen = (
        source.get("FISH_MODEL", "").strip() or (configured or "").strip() or DEFAULT_FISH_MODEL
    )
    if chosen not in KNOWN_FISH_MODELS:
        allowed = ", ".join(KNOWN_FISH_MODELS)
        raise ValueError(
            f"Unbekanntes Fish-Modell '{chosen}'. Erlaubt: {allowed}. "
            "Ein unbekannter Name fällt bei Fish still auf s2.1-pro zurück und wird berechnet."
        )
    return chosen


def _unit(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} muss eine Zahl sein")
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 1:
        raise ValueError(f"{label} muss größer als 0 und höchstens 1 sein")
    return number


def _from_env(env: Mapping[str, str], name: str) -> str:
    return env.get(name, "").strip()


def _env_unit(raw: str, label: str) -> float:
    try:
        number = float(raw)
    except ValueError:
        raise ValueError(f"{label} muss eine Zahl sein") from None
    return _unit(number, label)


def resolve_fish_profile(
    language: str,
    model: str | None,
    latency: str | None,
    temperature: float | None,
    top_p: float | None,
    env: Mapping[str, str] | None = None,
) -> FishProfile:
    """Sprache aus der Konfiguration. FISH_* in der Umgebung überschreibt Latenz und Sampling für einen Lauf."""
    source = os.environ if env is None else env
    if isinstance(language, str):
        language = language.replace("_", "-")  # Spielordner zh_CN -> BCP-47 zh-CN
    if not isinstance(language, str) or not _LANG.fullmatch(language):
        raise ValueError(
            "language muss ein BCP-47-Kürzel sein, z. B. de (steht in config.yaml und geht an Fish)"
        )
    chosen_latency = _from_env(source, "FISH_LATENCY") or (latency or "").strip() or DEFAULT_LATENCY
    if chosen_latency not in LATENCY_VALUES:
        raise ValueError(
            f"Fish-Latenz '{chosen_latency}' ist unbekannt. Erlaubt: {', '.join(LATENCY_VALUES)}."
        )
    raw_temperature = _from_env(source, "FISH_TEMPERATURE")
    raw_top_p = _from_env(source, "FISH_TOP_P")
    chosen_temperature = (
        _env_unit(raw_temperature, "FISH_TEMPERATURE")
        if raw_temperature
        else _unit(DEFAULT_TEMPERATURE if temperature is None else temperature, "fish_temperature")
    )
    chosen_top_p = (
        _env_unit(raw_top_p, "FISH_TOP_P")
        if raw_top_p
        else _unit(DEFAULT_TOP_P if top_p is None else top_p, "fish_top_p")
    )
    return FishProfile(
        resolve_fish_model(model, source),
        language,
        chosen_latency,
        chosen_temperature,
        chosen_top_p,
    )


def _model_id(stamp: str) -> str:
    head = stamp.split(" ", 1)[0]
    prefix = "fish-audio/"
    return head.removeprefix(prefix)


def _read_stamp(cache_dir: Path) -> str | None:
    path = Path(cache_dir) / STAMP_NAME
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def guard_fish_model(cache_dir: Path, model_alias: str, accept: bool) -> tuple[bool, str]:
    """(weitermachen, Meldung). Ohne Stempel gelten vorhandene WAVs als HISTORICAL_CACHE_MODEL."""
    cache_dir = Path(cache_dir)
    recorded = _read_stamp(cache_dir)
    has_wav = cache_dir.is_dir() and any(cache_dir.glob("*.wav"))
    if recorded is None:
        if not has_wav:
            return True, ""
        recorded = HISTORICAL_CACHE_MODEL
    if recorded == model_alias:
        return True, ""
    cost = ""
    if _model_id(model_alias) in PAID_TTS_MODELS and _model_id(recorded) not in PAID_TTS_MODELS:
        cost = " s2.1-pro kostet 15 USD je Million UTF-8-Bytes (s2-pro und s1 ebenso)."
    change = f"Cache-Schlüssel wechselt: {recorded} -> {model_alias}."
    if not accept:
        return False, (
            f"{change} Der Schlüssel enthält Modell, Sprache, Latenz und Sampling. Vorhandene WAVs bleiben liegen "
            f"und gelten für den neuen Lauf als Fehltreffer. Die Auswahl geht neu an Fish.{cost} "
            "Nur mit --accept-model-change fortsetzen, wenn der Wechsel beabsichtigt ist."
        )
    return True, (
        f"{change} Wechsel bestätigt: vorhandene WAVs bleiben liegen und gelten für den neuen Lauf als Fehltreffer.{cost}"
    )


def write_model_stamp(cache_dir: Path, model_alias: str) -> None:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / STAMP_NAME).write_text(model_alias + "\n", encoding="utf-8")


def free_tier_warning(model_id: str, today: date | None = None) -> str | None:
    """Hinweis, wenn das abgelaufene Gratis-Modell noch konfiguriert ist. Blockiert den Lauf nicht."""
    if model_id != DEFAULT_FISH_MODEL or (today or date.today()) <= FREE_UNTIL:
        return None
    return (
        "WARNUNG: s2.1-pro-free gilt laut Fish-Doku nur bis 30.11.2026. "
        "Ein unbekannter Modellname fällt still auf s2.1-pro zurück und wird berechnet "
        "(15 USD je Million UTF-8-Bytes), der Cache-Schlüssel bleibt dabei derselbe. "
        f"Zum Wechsel fish_model auf {PAID_SUCCESSOR} setzen und synth --accept-model-change ausführen."
    )
