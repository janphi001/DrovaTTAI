import json

import pytest

from drova_voice.cli import main
from drova_voice.lines import read_lines
from drova_voice.pipeline import read_runtime_lines


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


def _runtime_row(manifest_row: dict, **changes) -> str:
    row = dict(manifest_row)
    row.update(changes)
    return json.dumps(row, ensure_ascii=False)


def test_extract_adds_runtime_lines_from_the_mod(pipeline_repo, capsys):
    export = pipeline_repo.data / "export" / "de"
    first = json.loads((export / "manifest.json").read_text(encoding="utf-8"))["lines"][0]
    tree, path = "DT_Test_Template", first["locaPath"]
    new = _runtime_row(
        first,
        id=f"{tree}|{path}|Plh_900",
        tree=tree,
        locaKey="Plh_900",
        text="Ein erfundener Satz.",
    )
    (export / "manifest-runtime.jsonl").write_text(new + "\n", encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    assert len(lines) == 7
    added = [l for l in lines if l.id == f"{tree}|{path}|Plh_900"]
    assert added and added[0].speech == "Ein erfundener Satz." and added[0].skip is None
    assert "1 Laufzeit-Zeilen" in capsys.readouterr().out


def test_extract_keeps_the_manifest_line_when_the_runtime_file_repeats_it(pipeline_repo):
    export = pipeline_repo.data / "export" / "de"
    first = json.loads((export / "manifest.json").read_text(encoding="utf-8"))["lines"][0]
    (export / "manifest-runtime.jsonl").write_text(
        _runtime_row(first, actorName="Jemand") + "\n", encoding="utf-8"
    )
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    lines = read_lines(pipeline_repo.data / "lines.jsonl")
    assert len(lines) == 6
    assert [l.actor for l in lines if l.id == first["id"]] == [first["actorName"]]


def test_extract_skips_unreadable_runtime_lines(pipeline_repo, capsys):
    export = pipeline_repo.data / "export" / "de"
    (export / "manifest-runtime.jsonl").write_text(
        '{kaputt\n\n{"id": "ohne Felder"}\n[]\n', encoding="utf-8"
    )
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    assert len(read_lines(pipeline_repo.data / "lines.jsonl")) == 6
    out = capsys.readouterr().out
    assert "0 Laufzeit-Zeilen" in out and "3 unlesbar" in out


def test_a_missing_runtime_file_adds_no_lines(tmp_path):
    assert read_runtime_lines(tmp_path / "manifest-runtime.jsonl") == ([], 0)
