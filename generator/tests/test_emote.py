import pytest

from drova_voice.emote import merge_emotions, read_emotions, write_emotions
from drova_voice.emotions import EmotionTag, Event
from drova_voice.lines import Line


def line(key, stage=(), skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor="Mira", category="dialog", generic=False, raw="x", speech="x" if not skip else "", stage=tuple(stage), skip=skip)


def test_stage_directions_become_tags():
    result = merge_emotions({}, [line("Plh_1", [{"text": "seufzt", "pos": 0}]), line("Plh_2")])
    assert list(result) == ["T|P|Plh_1"]
    tag = result["T|P|Plh_1"]
    assert tag.source == "stage" and [(e.tag, e.pos) for e in tag.events] == [("sigh", 0)]


def test_llm_and_manual_rows_are_kept_over_stage_rows():
    llm = EmotionTag("stern", 0.6, source="llm")
    result = merge_emotions({"T|P|Plh_1": llm}, [line("Plh_1", [{"text": "seufzt", "pos": 0}])])
    assert result["T|P|Plh_1"] is llm


def test_stale_stage_rows_are_dropped_and_other_rows_untouched():
    old_stage = EmotionTag("joyful", 0.3, source="stage")
    outside = EmotionTag("sad", 0.5, source="stage")
    existing = {"T|P|Plh_1": old_stage, "X|Q|Plh_9": outside}
    result = merge_emotions(existing, [line("Plh_1")])  # Regieanweisung ist weggefallen
    assert "T|P|Plh_1" not in result and result["X|Q|Plh_9"] is outside


def test_skipped_lines_get_no_tag():
    assert merge_emotions({}, [line("Plh_1", [{"text": "seufzt", "pos": 0}], skip="gvar")]) == {}


def test_roundtrip_sorted_and_validated(tmp_path):
    path = tmp_path / "emotions.jsonl"
    write_emotions(path, {"B|P|Plh_2": EmotionTag("sad", 0.5, source="llm"),
                          "A|P|Plh_1": EmotionTag("stern", 0.4, [Event("sigh", 3)], ["nie"], source="manual")})
    ids = [l.split('"')[3] for l in path.read_text(encoding="utf-8").splitlines()]
    assert ids == ["A|P|Plh_1", "B|P|Plh_2"]
    back = read_emotions(path)
    assert back["A|P|Plh_1"].events == [Event("sigh", 3)] and back["A|P|Plh_1"].emphasis == ["nie"]


def test_read_rejects_unknown_emotion_with_line_number(tmp_path):
    path = tmp_path / "emotions.jsonl"
    path.write_text('{"id": "a", "emotion": "neutral"}\n{"id": "b", "emotion": "verwirrt", "intensity": 0.5}\n',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="Zeile 2"):
        read_emotions(path)


def test_read_missing_file_is_empty(tmp_path):
    assert read_emotions(tmp_path / "gibt-es-nicht.jsonl") == {}
