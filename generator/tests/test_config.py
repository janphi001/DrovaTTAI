from pathlib import Path

import pytest

from drova_voice.config import load_config


def test_load_config_defaults(tmp_path):
    gen = tmp_path / "generator"
    gen.mkdir()
    cfg_file = gen / "config.yaml"
    cfg_file.write_text('game_dir: "C:/Game Dir"\n', encoding="utf-8")

    cfg = load_config(cfg_file)

    assert cfg.language == "de"
    assert cfg.repo_root == tmp_path.resolve()
    assert cfg.loc_dir == Path("C:/Game Dir/Drova_Data/StreamingAssets/Localization/de")
    assert cfg.data_dir == tmp_path.resolve() / "data"
    assert cfg.workers_dir == tmp_path.resolve() / "generator" / "workers"


def test_missing_game_dir_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("language: de\n", encoding="utf-8")
    with pytest.raises(ValueError, match="game_dir"):
        load_config(cfg_file)
