import json

from drova_voice.cli import main
from drova_voice.profiles import read_profiles


def run(repo, *args):
    return main(["--config", str(repo.cfg), *args])


def test_set_show_and_import(pipeline_repo, tmp_path, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--set", "Mira", "--gender", "f", "--age", "mittel", "--note", "ruhig") == 0
    profiles = read_profiles(pipeline_repo.casting / "profiles.jsonl")
    assert profiles["mira"].source == "manual" and profiles["mira"].note == "ruhig"
    capsys.readouterr()
    assert run(pipeline_repo, "profile") == 0
    out = capsys.readouterr().out
    assert "Mira" in out and "mittel" in out and "manual" in out
    incoming = tmp_path / "result.jsonl"
    incoming.write_text(json.dumps({"speaker": "fremder", "gender": "m", "age": "alt"}) + "\n", encoding="utf-8")
    assert run(pipeline_repo, "profile", "--import", str(incoming)) == 1
    assert "fremder" in capsys.readouterr().err


def test_set_needs_gender_and_age(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--set", "mira") == 2
    assert "--gender" in capsys.readouterr().err


def test_prepare_writes_packets_for_speakers_without_profile(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--prepare", "--size", "5") == 0
    packet = json.loads((pipeline_repo.repo / "out" / "subagent" / "profile" / "packet_001.json").read_text(encoding="utf-8"))
    assert [e["speaker"] for e in packet] == ["mira"]
    assert "1 Sprecher in 1 Paketen" in capsys.readouterr().out


def test_import_fails_on_missing_file(pipeline_repo, tmp_path, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "profile", "--import", str(tmp_path / "gibt_es_nicht.jsonl")) == 2
    assert "Importdatei nicht gefunden" in capsys.readouterr().err
    assert not (pipeline_repo.casting / "profiles.jsonl").exists()


def test_import_reports_unreadable_lines_but_keeps_valid_rows(pipeline_repo, tmp_path, capsys):
    run(pipeline_repo, "extract")
    incoming = tmp_path / "partial.jsonl"
    incoming.write_text(json.dumps({"speaker": "mira", "gender": "f", "age": "mittel"}) + "\n"
                        + '{"speaker": "mira", "gender": "f", "ag', encoding="utf-8")
    assert run(pipeline_repo, "profile", "--import", str(incoming)) == 1
    err = capsys.readouterr().err
    assert "1 unlesbare Zeilen in" in err and "partial.jsonl" in err
    assert read_profiles(pipeline_repo.casting / "profiles.jsonl")["mira"].source == "llm"
