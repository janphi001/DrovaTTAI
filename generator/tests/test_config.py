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


def test_fish_settings_are_optional_and_checked(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'game_dir: "/tmp/game"\nfish_model: s2.1-pro\nfish_temperature: 0.5\n', encoding="utf-8"
    )
    cfg = load_config(cfg_file)
    assert cfg.fish_model == "s2.1-pro" and cfg.fish_temperature == 0.5 and cfg.fish_top_p is None
    cfg_file.write_text('game_dir: "/tmp/game"\nfish_model: kein-modell\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Unbekanntes Fish-Modell"):
        load_config(cfg_file)
    cfg_file.write_text('game_dir: "/tmp/game"\nfish_temperature: 2\n', encoding="utf-8")
    with pytest.raises(ValueError, match="fish_temperature"):
        load_config(cfg_file)


def test_relative_paths_follow_the_config_file_not_the_working_directory(tmp_path, monkeypatch):
    gen = tmp_path / "generator"
    gen.mkdir()
    cfg_file = gen / "config.yaml"
    cfg_file.write_text("game_dir: spiel\nrepo_root: ..\n", encoding="utf-8")
    elsewhere = tmp_path / "other" / "nested"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)
    cfg = load_config(cfg_file)
    assert cfg.game_dir == (gen / "spiel").resolve()
    assert cfg.repo_root == tmp_path.resolve()
    assert cfg.data_dir == tmp_path.resolve() / "data"


def test_windows_drive_path_stays_a_drive_path_from_another_directory(tmp_path, monkeypatch):
    gen = tmp_path / "generator"
    gen.mkdir()
    cfg_file = gen / "config.yaml"
    cfg_file.write_text('game_dir: "C:/Game Dir"\nrepo_root: "D:/Arbeit"\n', encoding="utf-8")
    (tmp_path / "other").mkdir()
    monkeypatch.chdir(tmp_path / "other")
    cfg = load_config(cfg_file)
    assert cfg.game_dir == Path("C:/Game Dir")
    assert cfg.loc_dir == Path("C:/Game Dir/Drova_Data/StreamingAssets/Localization/de")
    assert cfg.repo_root == Path("D:/Arbeit")
    assert "other" not in cfg.game_dir.parts and "other" not in cfg.repo_root.parts


def test_config_that_is_not_utf8_names_the_file(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_bytes(b"\xffgame_dir")
    with pytest.raises(ValueError, match="UTF-8") as caught:
        load_config(cfg_file)
    assert cfg_file.name in str(caught.value)


def test_null_or_empty_language_stays_de_and_a_number_is_rejected(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('game_dir: "/tmp/game"\nlanguage: null\n', encoding="utf-8")
    assert load_config(cfg_file).language == "de"
    cfg_file.write_text('game_dir: "/tmp/game"\nlanguage: ""\n', encoding="utf-8")
    assert load_config(cfg_file).language == "de"
    cfg_file.write_text('game_dir: "/tmp/game"\nlanguage: 5\n', encoding="utf-8")
    with pytest.raises(ValueError, match="language"):
        load_config(cfg_file)


@pytest.mark.parametrize(
    "value", ["..", "de/..", "../de", "de/en", "d e", ".de", "de.", "averyveryverylonglanguage"]
)
def test_language_must_be_a_short_folder_name(tmp_path, value):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"game_dir: '/tmp/game'\nlanguage: '{value}'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="gültiger Ordnername"):
        load_config(cfg_file)


def test_language_folder_codes_with_hyphen_or_underscore(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("game_dir: '/tmp/game'\nlanguage: 'zh_CN'\n", encoding="utf-8")
    assert load_config(cfg_file).language == "zh_CN"
    cfg_file.write_text("game_dir: '/tmp/game'\nlanguage: 'en-GB'\n", encoding="utf-8")
    assert load_config(cfg_file).language == "en-GB"
    cfg_file.write_text("game_dir: '/tmp/game'\nlanguage: ' en '\n", encoding="utf-8")
    assert load_config(cfg_file).language == "en"
    cfg_file.write_text("game_dir: '/tmp/game'\nlanguage: 'abcdefghijklmnop'\n", encoding="utf-8")
    assert load_config(cfg_file).language == "abcdefghijklmnop"
