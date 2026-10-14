import shutil

import pytest

from drova_voice.cli import main
from drova_voice.jsonl import read_jsonl_lenient

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


@needs_ffmpeg
def test_encode_after_synth(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    assert guarded(lambda: main(base + ["synth", "--engine", "fake"])) == 0
    capsys.readouterr()
    assert guarded(lambda: main(base + ["encode", "--workers", "2"])) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "encoded.jsonl")
    assert len(rows) == 3 and all(r["duration"] > 0.2 for r in rows)
    ogg = sorted((pipeline_repo.repo / "out" / "audio" / "de").rglob("*.ogg"))
    assert len(ogg) == 3 and {p.parent.name for p in ogg} == {"dialog", "default"}
    assert "3 kodiert" in capsys.readouterr().out


def test_encode_without_synth_results_fails_clearly(pipeline_repo, capsys):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "encode"]) == 2
    assert "synth" in capsys.readouterr().err
