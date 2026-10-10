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


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "game_dir" not in raw:
        raise ValueError(f"{path}: 'game_dir' fehlt")
    repo_root = Path(raw["repo_root"]) if raw.get("repo_root") else Path(path).resolve().parent.parent
    return Config(
        game_dir=Path(raw["game_dir"]),
        language=str(raw.get("language", "de")),
        repo_root=repo_root.resolve(),
    )
