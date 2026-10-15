import json

from drova_voice.cli import main
from drova_voice.emote import read_emotions


def test_emote_writes_stage_rows(pipeline_repo, capsys):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    assert main(["--config", str(pipeline_repo.cfg), "emote"]) == 0
    emotions = read_emotions(pipeline_repo.casting / "emotions.jsonl")
    assert list(emotions) == ["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1"]
    assert "stage: 1" in capsys.readouterr().out


def test_emote_keeps_llm_rows_on_rerun(pipeline_repo):
    main(["--config", str(pipeline_repo.cfg), "extract"])
    path = pipeline_repo.casting / "emotions.jsonl"
    path.write_text('{"id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2", "emotion": "stern", "intensity": 0.5, "source": "llm"}\n',
                    encoding="utf-8")
    assert main(["--config", str(pipeline_repo.cfg), "emote"]) == 0
    emotions = read_emotions(path)
    assert emotions["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2"].source == "llm"
    assert emotions["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1"].source == "stage"


def test_emote_prepare_and_import(pipeline_repo, tmp_path, capsys):
    cfg = str(pipeline_repo.cfg)
    main(["--config", cfg, "extract"])
    assert main(["--config", cfg, "emote", "--prepare"]) == 0
    packet = json.loads((pipeline_repo.repo / "out" / "subagent" / "emote" / "packet_001.json").read_text(encoding="utf-8"))
    assert packet[0]["tree"] == "DT_Test_NPC_Mira" and len(packet[0]["lines"]) == 3
    incoming = tmp_path / "result.jsonl"
    incoming.write_text(json.dumps({"id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2", "emotion": "tender", "intensity": 0.6}) + "\n"
                        + json.dumps({"id": "gibt|es|nicht", "emotion": "sad", "intensity": 0.5}) + "\n", encoding="utf-8")
    assert main(["--config", cfg, "emote", "--import", str(incoming)]) == 1
    assert "gibt|es|nicht" in capsys.readouterr().err
    emotions = read_emotions(pipeline_repo.casting / "emotions.jsonl")
    assert emotions["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2"].source == "llm"


def test_emote_import_fails_on_missing_file(pipeline_repo, tmp_path, capsys):
    cfg = str(pipeline_repo.cfg)
    main(["--config", cfg, "extract"])
    assert main(["--config", cfg, "emote", "--import", str(tmp_path / "gibt_es_nicht.jsonl")]) == 2
    assert "Importdatei nicht gefunden" in capsys.readouterr().err
    assert not (pipeline_repo.casting / "emotions.jsonl").exists()


def test_emote_import_reports_unreadable_lines_but_keeps_valid_rows(pipeline_repo, tmp_path, capsys):
    cfg = str(pipeline_repo.cfg)
    main(["--config", cfg, "extract"])
    incoming = tmp_path / "partial.jsonl"
    incoming.write_text(json.dumps({"id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2", "emotion": "tender", "intensity": 0.6}) + "\n"
                        + '{"id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_1", "emotion": "sa', encoding="utf-8")
    assert main(["--config", cfg, "emote", "--import", str(incoming)]) == 1
    err = capsys.readouterr().err
    assert "1 unlesbare Zeilen in" in err and "partial.jsonl" in err
    assert read_emotions(pipeline_repo.casting / "emotions.jsonl")["DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_2"].source == "llm"
