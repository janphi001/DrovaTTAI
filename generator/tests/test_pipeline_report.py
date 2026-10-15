import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


def test_report_right_after_extract(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    capsys.readouterr()
    assert main(base + ["report"]) == 0
    out = capsys.readouterr().out
    assert "offen: 2" in out and "übersprungen: gvar_value: 1" in out and "übersprungen: unspeakable: 1" in out


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
    assert "dialog: 4 Zeilen -> installiert: 2" in out and "player: 2 Zeilen -> installiert: 1, übersprungen: player_choice: 1" in out


def test_report_by_speaker(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    capsys.readouterr()
    assert main(base + ["report", "--by-speaker"]) == 0
    out = capsys.readouterr().out
    assert "Mira (lena)" in out and "Lücken" in out
