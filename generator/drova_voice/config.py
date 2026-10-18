from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
# Dieselbe Ordnerregel wie AudioLanguage in der Mod (VoiceSettings.CleanFolderName): 1–16 Zeichen,
# nur Buchstaben, Ziffern, '_' und '-'. Punkte und Schrägstriche würden install --prune aus dem Sprachordner heben.
_LANGUAGE_FOLDER = re.compile(r"[A-Za-z0-9_-]{1,16}\Z")


@dataclass(frozen=True)
class Config:
    game_dir: Path
    language: str
    repo_root: Path

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
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
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
    if root_raw is None or root_raw == "":
        repo_root = Path(path).resolve().parent.parent
    elif isinstance(root_raw, str):
        repo_root = Path(root_raw)
    else:
        raise ValueError(f"{path}: 'repo_root' muss ein Text sein")
    language = _language_folder(raw.get("language", "de"), path)
    return Config(
        game_dir=Path(game_dir),
        language=language,
        repo_root=repo_root.resolve(),
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
