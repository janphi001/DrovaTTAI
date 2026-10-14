import json
import shutil

import pytest

from drova_voice.cli import main

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")


@needs_ffmpeg
def test_install_after_encode(pipeline_repo, guarded, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    guarded(lambda: main(base + ["synth", "--engine", "fake"]))
    guarded(lambda: main(base + ["encode"]))
    capsys.readouterr()
    assert main(base + ["install", "--npc", "Mira"]) == 0
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert sorted(index["entries"]) == ["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1", "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2",
                                        "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_3|c0"]
    assert len(list(pipeline_repo.install_dir.rglob("*.ogg"))) == 3
    assert "3 Einträge" in capsys.readouterr().out


def test_install_without_encoded_fails_clearly(pipeline_repo, capsys):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "install"]) == 2
    assert "encode" in capsys.readouterr().err


@needs_ffmpeg
def test_install_drops_entries_of_speakers_that_lost_their_voice(pipeline_repo, guarded):
    base = ["--config", str(pipeline_repo.cfg)]
    main(base + ["extract"])
    guarded(lambda: main(base + ["synth", "--engine", "fake"]))
    guarded(lambda: main(base + ["encode"]))
    assert main(base + ["install"]) == 0
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    assert main(base + ["install"]) == 0
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert sorted(index["entries"]) == ["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_3|c0"]  # nur noch die Spielerzeile
