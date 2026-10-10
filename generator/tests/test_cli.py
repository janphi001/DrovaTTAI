from drova_voice.cli import main
from drova_voice.jsonl import read_jsonl


def test_bakeoff_select_and_run_with_fake_engine(tmp_path):
    repo = tmp_path / "repo"
    gen = repo / "generator"
    gen.mkdir(parents=True)
    game = tmp_path / "game"
    dialog = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    dialog.mkdir(parents=True)
    (dialog / "NPC_A_de.loc").write_text("Plh_1 { Wohin führt dieser Weg eigentlich? }\n", encoding="utf-8")
    cfg = gen / "config.yaml"
    cfg.write_text(f'game_dir: "{game.as_posix()}"\n', encoding="utf-8")
    voices = gen / "voices.yaml"
    voices.write_text("- {engine: fake}\n", encoding="utf-8")

    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    samples = read_jsonl(repo / "data" / "bakeoff" / "samples.jsonl")
    assert [s["bucket"] for s in samples] == ["question"]

    assert main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices)]) == 0
    assert (repo / "out" / "bakeoff" / "fake" / "default" / "question_00.wav").exists()
    assert (repo / "out" / "bakeoff" / "index.html").exists()
