from drova_voice.cli import main
from drova_voice.jsonl import latest_by_id, read_jsonl_lenient

NPC_TREE = "DT_Test_NPC_Mira|Dialog/NPC_Mira|"


def run(pipeline_repo, *args):
    return main(["--config", str(pipeline_repo.cfg), *args])


def test_synth_fake_engine_writes_results_and_cache(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--workers", "2")) == 0
    rows = latest_by_id(read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl"))
    assert sorted(rows) == [NPC_TREE + "Plh_1", NPC_TREE + "Plh_2", NPC_TREE + "Plh_3"]
    assert all(r["ok"] for r in rows.values())
    assert len(list((pipeline_repo.repo / "cache" / "synth").glob("*.wav"))) == 3
    out = capsys.readouterr().out
    assert "3 erzeugt" in out and "übersprungen: gvar_value: 1, player_choice: 1, unspeakable: 1" in out


def test_synth_second_run_uses_the_cache(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    capsys.readouterr()
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    assert "0 neu erzeugt" in capsys.readouterr().out


def test_synth_reports_speaker_without_voice(pipeline_repo, guarded, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    assert "no_voice: 2" in capsys.readouterr().out


def test_synth_limit(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--limit", "1")) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl")
    assert len(rows) == 1


def test_synth_records_the_characters_sent(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    first = capsys.readouterr().out
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "usage.jsonl")
    assert [r["chars"] > 0 for r in rows] == [True, False] and rows[0]["engine"] == "fake"
    assert "Zeichen neu" in first and f"insgesamt bisher: {rows[0]['chars']}" in first
