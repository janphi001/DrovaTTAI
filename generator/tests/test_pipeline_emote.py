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
