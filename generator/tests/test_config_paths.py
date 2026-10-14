from pathlib import Path

from drova_voice.config import load_config


def test_new_paths(tmp_path):
    (tmp_path / "generator").mkdir()
    cfg_file = tmp_path / "generator" / "config.yaml"
    cfg_file.write_text("game_dir: 'D:/Spiel'\nlanguage: de\n", encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.cache_dir == tmp_path.resolve() / "cache"
    assert cfg.casting_dir == tmp_path.resolve() / "casting"
    assert cfg.install_dir == Path("D:/Spiel") / "Mods" / "DrovaVoice" / "Audio" / "de"
