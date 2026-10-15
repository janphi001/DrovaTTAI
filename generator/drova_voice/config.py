from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


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
    language = raw.get("language", "de")
    if language is None or language == "":
        language = "de"
    elif not isinstance(language, str):
        raise ValueError(f"{path}: 'language' muss ein Text sein")
    return Config(
        game_dir=Path(game_dir),
        language=language,
        repo_root=repo_root.resolve(),
    )
