import json
import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe nicht installiert",
)


def test_report_right_after_extract(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    capsys.readouterr()
    assert main(base + ["report"]) == 0
    out = capsys.readouterr().out
    assert (
        "offen: 2" in out
        and "übersprungen: gvar_value: 1" in out
        and "übersprungen: unspeakable: 1" in out
    )


@needs_ffmpeg
def test_report_after_full_run(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    guarded(lambda: main(base + ["synth", "--engine", "fake"]))
    guarded(lambda: main(base + ["encode"]))
    main(base + ["install"])
    capsys.readouterr()
    assert main(base + ["report"]) == 0
    out = capsys.readouterr().out
    assert (
        "dialog: 4 Zeilen -> installiert: 2" in out
        and "player: 2 Zeilen -> installiert: 1, übersprungen: player_choice: 1" in out
    )


@pytest.mark.parametrize(
    "payload, needle",
    [
        ("{", "nicht lesbar"),
        ("[]", "kein JSON-Objekt"),
        ("null", "kein JSON-Objekt"),
        ('{"version": 1, "language": "de", "entries": null}', "entries ist kein Objekt"),
        ('{"entries": []}', "entries ist kein Objekt"),
        ('{"entries": "dialog/a.ogg"}', "entries ist kein Objekt"),
    ],
)
def test_report_rejects_unusable_index_json(pipeline_repo, capsys, payload, needle):
    base = ["--config", str(pipeline_repo.cfg)]
    assert main(base + ["extract"]) == 0
    capsys.readouterr()
    index = pipeline_repo.install_dir / "index.json"
    index.parent.mkdir(parents=True)
    index.write_text(payload, encoding="utf-8")
    assert main(base + ["report"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and needle in err and "Traceback" not in err


def test_report_rejects_index_that_is_not_utf8(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    assert main(base + ["extract"]) == 0
    capsys.readouterr()
    index = pipeline_repo.install_dir / "index.json"
    index.parent.mkdir(parents=True)
    index.write_bytes(b"\xff\xfe{")
    assert main(base + ["report"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "nicht lesbar" in err and "Traceback" not in err


def test_report_counts_a_valid_index(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    assert main(base + ["extract"]) == 0
    index = pipeline_repo.install_dir / "index.json"
    index.parent.mkdir(parents=True)
    line_id = "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1"
    index.write_text(
        json.dumps(
            {
                "version": 1,
                "language": "de",
                "entries": {line_id: {"file": "dialog/a.ogg", "duration": 1}},
            }
        ),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert main(base + ["report"]) == 0
    assert "installiert: 1" in capsys.readouterr().out


def test_report_by_speaker(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    capsys.readouterr()
    assert main(base + ["report", "--by-speaker"]) == 0
    out = capsys.readouterr().out
    assert "Mira (lena)" in out and "Lücken" in out
