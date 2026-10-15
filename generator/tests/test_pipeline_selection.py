from drova_voice.cli import main
from drova_voice.jsonl import read_jsonl_lenient

TREE = "DT_Test_NPC_Mira|Dialog/NPC_Mira|"


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def test_batches_command_lists_the_speakers_and_writes_the_plan(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "batches") == 0
    out = capsys.readouterr().out
    assert "Etappe 1" in out and "Mira" in out and (pipeline_repo.data / "batches.json").is_file()


def test_synth_batch_runs_the_speaker_and_the_player(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    run(pipeline_repo, "batches")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--batch", "1")) == 0
    ids = sorted(r["id"] for r in read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl"))
    assert ids == [TREE + "Plh_1", TREE + "Plh_2", TREE + "Plh_3"]


def test_unknown_batch_and_missing_plan_are_clear_errors(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "synth", "--engine", "fake", "--batch", "1") == 2
    assert "batches" in capsys.readouterr().err
    run(pipeline_repo, "batches")
    assert run(pipeline_repo, "synth", "--engine", "fake", "--batch", "7") == 2
    assert "Etappe 7" in capsys.readouterr().err


def test_synth_sample_runs_one_line_per_speaker(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--sample")) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl")
    assert [r["id"] for r in rows] == [TREE + "Plh_1"]
