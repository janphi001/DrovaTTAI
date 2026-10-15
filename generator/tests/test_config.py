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


@pytest.mark.parametrize("value", ['""', "123", "[a, b]", "null"])
def test_game_dir_must_be_non_empty_string(tmp_path, value):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"game_dir: {value}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="game_dir"):
        load_config(cfg_file)


def test_yaml_root_must_be_mapping(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("- eins\n- zwei\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Konfiguration"):
        load_config(cfg_file)


def test_backslash_path_in_double_quotes_gives_german_hint(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(r'game_dir: "C:\Drova\Spiel"' + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="einfachen Anführungszeichen"):
        load_config(cfg_file)


@pytest.mark.parametrize("value", ["5", "[a, b]", "true", "0"])
def test_repo_root_must_be_a_string(tmp_path, value):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f'game_dir: "C:/Game"\nrepo_root: {value}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="repo_root"):
        load_config(cfg_file)


def test_null_or_empty_language_stays_de_and_a_number_is_rejected(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('game_dir: "/tmp/game"\nlanguage: null\n', encoding="utf-8")
    assert load_config(cfg_file).language == "de"
    cfg_file.write_text('game_dir: "/tmp/game"\nlanguage: ""\n', encoding="utf-8")
    assert load_config(cfg_file).language == "de"
    cfg_file.write_text('game_dir: "/tmp/game"\nlanguage: 5\n', encoding="utf-8")
    with pytest.raises(ValueError, match="language"):
        load_config(cfg_file)
