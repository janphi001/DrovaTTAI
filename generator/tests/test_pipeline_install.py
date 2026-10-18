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
                                        "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_3"]
    assert len(list(pipeline_repo.install_dir.rglob("*.ogg"))) == 3
    assert "3 Einträge" in capsys.readouterr().out


def test_install_prune_and_dry_run_flags(pipeline_repo, capsys):
    base = ["--config", str(pipeline_repo.cfg)]
    assert main(base + ["extract"]) == 0
    line_id = "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1"
    key = "k-test"
    rel = "dialog/keep.ogg"
    synth = pipeline_repo.data / "synth" / "results.jsonl"
    synth.parent.mkdir(parents=True)
    synth.write_text(json.dumps({"id": line_id, "key": key, "ok": True}) + "\n", encoding="utf-8")
    (pipeline_repo.data / "encoded.jsonl").write_text(
        json.dumps({"id": line_id, "rel": rel, "duration": 1.25, "key": key}) + "\n", encoding="utf-8")
    audio = pipeline_repo.repo / "out" / "audio" / "de" / "dialog"
    audio.mkdir(parents=True)
    (audio / "keep.ogg").write_bytes(b"OggS-keep")
    target = pipeline_repo.install_dir
    (target / "dialog").mkdir(parents=True)
    (target / "bark").mkdir()
    (target / "dialog" / "old.ogg").write_bytes(b"OggS-old")
    (target / "bark" / "note.txt").write_text("bleiben", encoding="utf-8")
    capsys.readouterr()

    assert main(base + ["install"]) == 0
    plain = capsys.readouterr().out
    assert "verwaiste" not in plain and "Dry-Run" not in plain
    assert (target / "dialog" / "keep.ogg").read_bytes() == b"OggS-keep"
    assert (target / "dialog" / "old.ogg").is_file()

    assert main(base + ["install", "--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert "Dry-Run:" in dry and "dialog/old.ogg" in dry
    assert (target / "dialog" / "old.ogg").is_file()

    assert main(base + ["install", "--prune", "--dry-run"]) == 0
    both = capsys.readouterr().out
    assert "Dry-Run:" in both and "gelöscht:" not in both
    assert (target / "dialog" / "old.ogg").is_file()

    assert main(base + ["install", "--prune"]) == 0
    pruned = capsys.readouterr().out
    assert "gelöscht:" in pruned and "dialog/old.ogg" in pruned
    assert not (target / "dialog" / "old.ogg").exists()
    assert (target / "dialog" / "keep.ogg").is_file()
    assert (target / "bark" / "note.txt").is_file()
    assert (audio / "keep.ogg").is_file()


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
    assert sorted(index["entries"]) == ["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_3"]  # nur noch die Spielerzeile
