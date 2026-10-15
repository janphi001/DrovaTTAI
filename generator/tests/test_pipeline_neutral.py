import json
import shutil

import pytest

from drova_voice.cli import main
from drova_voice.lines import read_lines

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe nicht installiert")
NEUTRAL_ID = "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_4#neutral"


def _use_name_line(pipeline_repo):
    loc = pipeline_repo.game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog" / "NPC_Mira_de.loc"
    text = loc.read_text(encoding="utf-8")
    loc.write_text(text.replace("Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen.", "Hallo $GVAR:EVars_Player.Name$!"),
                   encoding="utf-8")


def test_extract_gives_the_name_line_a_neutral_id(pipeline_repo):
    _use_name_line(pipeline_repo)
    assert main(["--config", str(pipeline_repo.cfg), "extract"]) == 0
    line = next(l for l in read_lines(pipeline_repo.data / "lines.jsonl") if l.id == NEUTRAL_ID)
    assert line.speech == "Hallo!" and line.skip is None


@needs_ffmpeg
def test_neutral_line_is_installed_with_a_variants_block(pipeline_repo, guarded):
    _use_name_line(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (["extract"], ["synth", "--engine", "fake", "--workers", "2"], ["encode"], ["install"]):
        assert guarded(lambda s=step: main(base + s)) == 0, step
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert NEUTRAL_ID in index["entries"]
    assert index["variants"] == {"DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_4": ["neutral"]}


@needs_ffmpeg
def test_neutral_entry_disappears_when_the_speaker_loses_the_voice(pipeline_repo, guarded):
    _use_name_line(pipeline_repo)
    base = ["--config", str(pipeline_repo.cfg)]
    for step in (["extract"], ["synth", "--engine", "fake"], ["encode"], ["install"]):
        guarded(lambda s=step: main(base + s))
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    assert main(base + ["install"]) == 0
    index = json.loads((pipeline_repo.install_dir / "index.json").read_text(encoding="utf-8"))
    assert NEUTRAL_ID not in index["entries"] and index["variants"] == {}
