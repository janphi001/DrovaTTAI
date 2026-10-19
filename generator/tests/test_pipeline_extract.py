import json

import pytest

from drova_voice.cli import main
from drova_voice.lines import read_lines


def test_extract_writes_lines_and_reports_skips(pipeline_repo, capsys):
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    assert [l.skip for l in lines] == [
        None,
        None,
        None,
        "gvar_value",
        "unspeakable",
        "player_choice",
    ]
    assert (
        lines[0].speech == "Der Weg nach Norden ist weit." and lines[0].stage[0]["text"] == "seufzt"
    )
    out = capsys.readouterr().out
    assert (
        "6 Zeilen" in out
        and "gvar_value: 1" in out
        and "unspeakable: 1" in out
        and "player_choice: 1" in out
    )


def test_extract_without_manifest_fails_clearly(pipeline_repo, capsys):
    (pipeline_repo.data / "export" / "de" / "manifest.json").unlink()
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    err = capsys.readouterr().err
    assert "Manifest nicht gefunden" in err and "manifest-loaded.json" in err


def test_extract_uses_the_loaded_manifest_when_the_full_one_is_missing(pipeline_repo, capsys):
    export = pipeline_repo.data / "export" / "de"
    full = export / "manifest.json"
    loaded = export / "manifest-loaded.json"
    data = json.loads(full.read_text(encoding="utf-8"))
    data["lines"] = data["lines"][:1]
    full.unlink()
    loaded.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    assert len(read_lines(pipeline_repo.data / "lines.jsonl")) == 1
    assert "manifest-loaded.json" in capsys.readouterr().out


def test_extract_prefers_the_full_manifest_when_both_exist(pipeline_repo, capsys):
    export = pipeline_repo.data / "export" / "de"
    full = export / "manifest.json"
    loaded = export / "manifest-loaded.json"
    data = json.loads(full.read_text(encoding="utf-8"))
    data["lines"] = data["lines"][:1]
    loaded.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    assert len(read_lines(pipeline_repo.data / "lines.jsonl")) == 6
    assert "manifest-loaded.json" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "payload", ["{", "[]", "null", '"text"', '{"lines": null}', '{"lines": {}}']
)
def test_extract_rejects_unusable_manifest_json(pipeline_repo, capsys, payload):
    path = pipeline_repo.data / "export" / "de" / "manifest.json"
    path.write_text(payload, encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "Manifest" in err and "Traceback" not in err
    assert not (pipeline_repo.data / "lines.jsonl").exists()


def test_extract_rejects_a_loc_file_that_is_not_utf8(pipeline_repo, capsys):
    loc = (
        pipeline_repo.game
        / "Drova_Data"
        / "StreamingAssets"
        / "Localization"
        / "de"
        / "Dialog"
        / "NPC_Mira_de.loc"
    )
    loc.write_bytes(b"Plh_1 { Aa\xe4 }\n")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "kein gültiges UTF-8" in err and "Traceback" not in err
    assert "Aa" not in err and not (pipeline_repo.data / "lines.jsonl").exists()


def test_extract_rejects_manifest_that_is_not_utf8(pipeline_repo, capsys):
    path = pipeline_repo.data / "export" / "de" / "manifest.json"
    path.write_bytes(b"\xff\xfe{")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "nicht lesbar" in err and "Traceback" not in err
