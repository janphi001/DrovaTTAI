from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from drova_voice.fish_model import resolve_fish_model

_DRIVE = re.compile(r"^[A-Za-z]:")


def _rooted(text: str) -> bool:
    return text[:1] in "/\\" or bool(_DRIVE.match(text))


def _path_from_config(text: str, base: Path) -> Path:
    # Ein Laufwerksbuchstabe ist unter Linux kein absoluter Pfad. resolve() würde ihn an
    # das Arbeitsverzeichnis hängen. Relative Angaben gehören zur Konfigurationsdatei.
    path = Path(text)
    if _rooted(text):
        return path.resolve() if path.is_absolute() else path
    return (base / text).resolve()


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
# Dieselbe Ordnerregel wie AudioLanguage in der Mod (VoiceSettings.CleanFolderName): 1–16 Zeichen,
# nur Buchstaben, Ziffern, '_' und '-'. Punkte und Schrägstriche würden install --prune aus dem Sprachordner heben.
_LANGUAGE_FOLDER = re.compile(r"[A-Za-z0-9_-]{1,16}\Z")


@dataclass(frozen=True)
class Config:
    game_dir: Path
    language: str
    repo_root: Path
    fish_model: str | None = (
        None  # None: Standard aus drova_voice.fish_model, sonst diese Modell-ID
    )
    fish_latency: str | None = None
    fish_temperature: float | None = None
    fish_top_p: float | None = None

    @property
    def loc_dir(self) -> Path:
        return self.game_dir / "Drova_Data" / "StreamingAssets" / "Localization" / self.language

    @property
    def data_dir(self) -> Path:
        return self.repo_root / "data"

    @property
    def out_dir(self) -> Path:
        return self.repo_root / "out"

    @property
    def voices_dir(self) -> Path:
        return self.repo_root / "voices"

    @property
    def workers_dir(self) -> Path:
        return self.repo_root / "generator" / "workers"

    @property
    def cache_dir(self) -> Path:
        return self.repo_root / "cache"

    @property
    def casting_dir(self) -> Path:
        return self.repo_root / "casting"

    @property
    def install_dir(self) -> Path:
        return self.game_dir / "Mods" / "DrovaVoice" / "Audio" / self.language


def load_config(path: Path) -> Config:
    config_path = Path(path)
    try:
        text = config_path.read_text(encoding="utf-8")
    except UnicodeError as e:
        raise ValueError(f"{path}: Konfiguration ist kein UTF-8 ({e})") from e
    try:
        raw = yaml.safe_load(text)
    except yaml.scanner.ScannerError as e:
        # Typisch: Windows-Pfad mit Backslash in doppelten Anführungszeichen, z. B. "C:\Games" (\G ist ungültig).
        raise ValueError(
            f"{path}: YAML-Fehler: {e}. Hinweis: Windows-Pfade mit '/' oder in einfachen "
            "Anführungszeichen schreiben, z. B. 'C:/Games/...'"
        ) from e
    except yaml.YAMLError as e:
        raise ValueError(f"{path}: YAML-Fehler: {e}") from e
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: Konfiguration muss aus 'Schlüssel: Wert'-Zeilen bestehen")
    if "game_dir" not in raw:
        raise ValueError(f"{path}: 'game_dir' fehlt")
    game_dir = raw["game_dir"]
    if not isinstance(game_dir, str) or not game_dir.strip():
        raise ValueError(f"{path}: 'game_dir' muss ein nicht-leerer Text sein")
    root_raw = raw.get("repo_root")
    base = config_path.resolve().parent
    if root_raw is None or root_raw == "":
        repo_root = base.parent
    elif isinstance(root_raw, str):
        repo_root = _path_from_config(root_raw, base)
    else:
        raise ValueError(f"{path}: 'repo_root' muss ein Text sein")
    language = _language_folder(raw.get("language", "de"), path)
    fish_model = raw.get("fish_model")
    if fish_model is None or fish_model == "":
        fish_model = None
    elif not isinstance(fish_model, str):
        raise ValueError(f"{path}: 'fish_model' muss ein Text sein")
    else:
        fish_model = resolve_fish_model(
            fish_model, {}
        )  # leere Umgebung: nur den Konfigurationswert prüfen
    fish_latency = _optional_text(raw, path, "fish_latency")
    fish_temperature = _optional_unit(raw, path, "fish_temperature")
    fish_top_p = _optional_unit(raw, path, "fish_top_p")
    return Config(
        game_dir=_path_from_config(game_dir, base),
        language=language,
        repo_root=repo_root,
        fish_model=fish_model,
        fish_latency=fish_latency,
        fish_temperature=fish_temperature,
        fish_top_p=fish_top_p,
    )


def _language_folder(language: object, path: Path) -> str:
    if language is None or language == "":
        return "de"
    if not isinstance(language, str):
        raise ValueError(f"{path}: 'language' muss ein Text sein")
    language = language.strip()
    if language == "":
        return "de"
    if _LANGUAGE_FOLDER.fullmatch(language) is None:
        raise ValueError(
            f"{path}: 'language' = '{language}' ist kein gültiger Ordnername "
            "(erlaubt sind 1–16 Zeichen aus Buchstaben, Ziffern, '_' und '-')"
        )
    return language


def _optional_text(raw: dict, path: Path, field: str) -> str | None:
    if field not in raw or raw[field] is None or raw[field] == "":
        return None
    value = raw[field]
    if not isinstance(value, str):
        raise ValueError(f"{path}: '{field}' muss ein Text sein")
    return value


def _optional_unit(raw: dict, path: Path, field: str) -> float | None:
    if field not in raw or raw[field] is None or raw[field] == "":
        return None
    value = raw[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: '{field}' muss eine Zahl sein")
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 1:
        raise ValueError(f"{path}: '{field}' muss größer als 0 und höchstens 1 sein")
    return number
