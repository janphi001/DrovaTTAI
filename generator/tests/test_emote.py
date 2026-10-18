import pytest

from drova_voice.emote import import_llm_emotions, merge_emotions, prepare_emote_packets, read_emotions, write_emotions
from drova_voice.emotions import EmotionTag, Event
from drova_voice.lines import Line
from drova_voice.profiles import Profile


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


def eline(key, actor="Anna", speech="Hallo da.", tree="T1", category="dialog", skip=None, stage=()):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw=speech, speech="" if skip else speech, stage=stage, skip=skip)


@pytest.mark.parametrize("size", [0, -1])
def test_prepare_emote_packets_rejects_a_non_positive_size(size):
    with pytest.raises(ValueError, match="mindestens 1"):
        prepare_emote_packets([eline("1")], {}, trees_per_packet=size)


def test_prepare_emote_packets_hold_whole_trees_with_speaker_profiles():
    lines = [eline("1", "Anna", stage=({"text": "seufzt", "pos": 0},)), eline("2", "Bob"), eline("3", "Anna", tree="T2"),
             eline("4", "Cy", skip="gvar"), eline("5", "Cy", category="bark", tree="T3"),
             eline("6", "Player", category="player", tree="T2")]
    profiles = {"anna": Profile("anna", "f", "mittel", None, 0.9, "ruhig", "llm")}
    packets = prepare_emote_packets(lines, profiles, trees_per_packet=1)
    assert [[t["tree"] for t in p] for p in packets] == [["T1"], ["T2"]]
    t1 = packets[0][0]
    assert [(l["id"], l["actor"], l["stage"]) for l in t1["lines"]] == [("T1|P|1", "Anna", ["seufzt"]), ("T1|P|2", "Bob", [])]
    assert t1["speakers"] == {"anna": {"gender": "f", "age": "mittel", "note": "ruhig"}}


def test_import_llm_emotions_rules():
    existing = {"T|P|1": EmotionTag("sad", 0.5, source="manual"), "T|P|2": EmotionTag("angry", 0.6, source="stage"),
                "T|P|3": EmotionTag("tender", 0.4, source="llm")}
    rows = [{"id": "T|P|1", "emotion": "joyful", "intensity": 0.7},
            {"id": "T|P|2", "emotion": "joyful", "intensity": 0.7},
            {"id": "T|P|3", "emotion": "stern", "intensity": 0.5, "source": "manual"},
            {"id": "T|P|4", "emotion": "excited", "intensity": 0.8, "events": [{"tag": "laugh", "pos": 3}]},
            {"id": "T|P|9", "emotion": "joyful", "intensity": 0.7},
            {"id": "T|P|5", "emotion": "wütend", "intensity": 0.7}]
    r = import_llm_emotions(existing, rows, {"T|P|1", "T|P|2", "T|P|3", "T|P|4", "T|P|5"})
    assert r.merged["T|P|1"].source == "manual" and r.merged["T|P|2"].source == "stage"
    assert r.merged["T|P|3"].emotion == "stern" and r.merged["T|P|3"].source == "llm"
    assert r.merged["T|P|4"].events[0].tag == "laugh" and r.merged["T|P|4"].source == "llm"
    assert (r.imported, r.kept) == (2, 2) and len(r.errors) == 2
    assert any("T|P|9" in e for e in r.errors) and any("T|P|5" in e for e in r.errors)
