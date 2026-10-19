import json
import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe nicht installiert",
)


@needs_ffmpeg
def test_whole_pipeline_with_fake_engine(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    steps = [
        ["extract"],
        ["cast", "--check", "--npc", "Mira"],
        ["emote", "--npc", "Mira"],
        ["synth", "--engine", "fake", "--workers", "2", "--npc", "Mira"],
        ["encode", "--npc", "Mira"],
        ["install", "--npc", "Mira"],
        ["report", "--npc", "Mira"],
        ["preview", "--npc", "Mira"],
    ]
    for step in steps:
        assert guarded(lambda s=step: main(base + s)) == 0, step
    out = capsys.readouterr().out
    assert (
        "dialog: 4 Zeilen" in out
        and "installiert: 2" in out
        and "player: 2 Zeilen" in out
        and "player_choice: 1" in out
    )
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index["entries"]) == 3
    assert (pipeline_repo.repo / "out" / "preview" / "index.html").is_file()
    # zweiter Durchlauf: alles kommt aus Cache bzw. Stempeln, der Index bleibt gleich
    for step in steps[3:]:
        assert guarded(lambda s=step: main(base + s)) == 0, step
    assert (
        json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8")) == index
    )
