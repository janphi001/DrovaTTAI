import pytest

from drova_voice.cli import main
from drova_voice.lines import read_lines


def test_extract_writes_lines_and_reports_skips(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    assert [l.skip for l in lines] == [None, None, None, "gvar_value", "unspeakable", "player_choice"]
    assert lines[0].speech == "Der Weg nach Norden ist weit." and lines[0].stage[0]["text"] == "seufzt"
    out = capsys.readouterr().out
    assert "6 Zeilen" in out and "gvar_value: 1" in out and "unspeakable: 1" in out and "player_choice: 1" in out


def test_extract_without_manifest_fails_clearly(pipeline_repo, capsys):
    (pipeline_repo.data / "export" / "de" / "manifest.json").unlink()
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    assert "Manifest nicht gefunden" in capsys.readouterr().err


@pytest.mark.parametrize("payload", ["{", "[]", "null", '"text"', '{"lines": null}', '{"lines": {}}'])
def test_extract_rejects_unusable_manifest_json(pipeline_repo, capsys, payload):
    path = pipeline_repo.data / "export" / "de" / "manifest.json"
    path.write_text(payload, encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "Manifest" in err and "Traceback" not in err
    assert not (pipeline_repo.data / "lines.jsonl").exists()


def test_extract_rejects_manifest_that_is_not_utf8(pipeline_repo, capsys):
    path = pipeline_repo.data / "export" / "de" / "manifest.json"
    path.write_bytes(b"\xff\xfe{")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "nicht lesbar" in err and "Traceback" not in err
