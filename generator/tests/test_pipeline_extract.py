from drova_voice.cli import main
from drova_voice.lines import read_lines


def test_extract_writes_lines_and_reports_skips(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    assert [l.skip for l in lines] == [None, None, None, "gvar", "unspeakable"]
    assert lines[0].speech == "Der Weg nach Norden ist weit." and lines[0].stage[0]["text"] == "seufzt"
    out = capsys.readouterr().out
    assert "5 Zeilen" in out and "gvar: 1" in out and "unspeakable: 1" in out


def test_extract_without_manifest_fails_clearly(pipeline_repo, capsys):
    (pipeline_repo.data / "export" / "de" / "manifest.json").unlink()
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    assert "Manifest nicht gefunden" in capsys.readouterr().err
