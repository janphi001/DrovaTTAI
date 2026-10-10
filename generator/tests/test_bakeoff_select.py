from drova_voice.bakeoff import Sample, classify, select_samples
from drova_voice.jsonl import read_jsonl, write_jsonl
from drova_voice.player_name import NAME_TOKEN

LOC = "\n\n".join([
    "Plh_1 { Hmpf. }",
    "Plh_2 { " + "Dies ist ein recht langer Testsatz. " * 8 + "}",
    "Plh_3 { *seufzt* Na gut, dann eben. }",
    f"Plh_4 {{ Danke, {NAME_TOKEN}. Bis bald. }}",
    "Plh_5 { Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen. }",
    "Plh_6 { Wem gehört dieser Hof eigentlich? }",
    "Plh_7 { Verschwinde sofort von hier! }",
    "Plh_8 { Ich habe heute viel zu tun gehabt. }",
    "Plh_9 { *grinst* }",
    "Plh_10 { Der Weg ist lang und staubig. }",
    "Plh_11 { *tanzt* Hallo, wie nett, dich hier zu treffen. }",
]) + "\n"


def make_loc_dir(tmp_path):
    d = tmp_path / "de" / "Dialog"
    d.mkdir(parents=True)
    (d / "NPC_Test_de.loc").write_text(LOC, encoding="utf-8")
    return tmp_path / "de"


def test_classify():
    assert classify("Hmpf.") == "short"
    assert classify(f"Hallo {NAME_TOKEN}!") == "player_name"
    assert classify("Hier $GVAR:A.B$ Münzen.") == "gvar"
    assert classify("*seufzt* Ja.") == "stage"
    assert classify("Was ist hier eigentlich los?") == "question"
    assert classify("Verschwinde sofort von hier!") == "exclaim"
    assert classify("Ich habe heute viel zu tun.") == "normal"


def test_select_one_per_bucket_with_prepared_text(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=1)
    by_bucket = {s.bucket: s for s in samples}
    assert set(by_bucket) == {"short", "long", "stage", "emotion", "player_name", "gvar", "question", "exclaim", "normal"}
    assert by_bucket["player_name"].text == "Danke, Arden. Bis bald."
    assert by_bucket["gvar"].text == "Heute sind zehn Münzen."
    assert by_bucket["stage"].text == "Na gut, dann eben."
    assert by_bucket["stage"].emotion["events"] == [{"tag": "sigh", "pos": 0}]
    assert all(s.text.strip() for s in samples)


def test_stage_bucket_only_holds_lines_with_a_matching_rule(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=10)
    stage = [s for s in samples if s.bucket == "stage"]
    assert stage
    assert all(s.emotion["source"] != "default" for s in stage)
    assert all("tanzt" not in s.raw for s in samples)


def test_emotion_bucket_holds_neutral_lines_with_manual_tags(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=10)
    emotion = [s for s in samples if s.bucket == "emotion"]
    assert len(emotion) == 2
    assert all(s.emotion["emotion"] != "neutral" and s.emotion["source"] == "manual" for s in emotion)
    assert {s.key for s in emotion}.isdisjoint({s.key for s in samples if s.bucket == "normal"})


def test_emotion_tags_cycle_through_fixed_presets(tmp_path):
    loc = "\n\n".join(f"Plh_{i} {{ Der Weg Nummer {i} ist lang. }}" for i in range(1, 6)) + "\n"
    d = tmp_path / "de" / "Dialog"
    d.mkdir(parents=True)
    (d / "NPC_Test_de.loc").write_text(loc, encoding="utf-8")
    samples = select_samples(tmp_path / "de", per_bucket=5)
    emotion = [s for s in samples if s.bucket == "emotion"]
    assert [(s.emotion["emotion"], s.emotion["intensity"], s.emotion["events"]) for s in emotion] == [
        ("angry", 0.8, []),
        ("sad", 0.7, []),
        ("joyful", 0.6, [{"tag": "laugh", "pos": 0}]),
        ("stern", 0.5, [{"tag": "sigh", "pos": 0}]),
        ("angry", 0.8, []),
    ]
    assert all(s.emotion["source"] == "manual" for s in emotion)


def test_stage_only_line_is_never_selected(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=10)
    assert all(s.key != "Plh_9" for s in samples)


def test_selection_is_deterministic(tmp_path):
    d = make_loc_dir(tmp_path)
    assert select_samples(d, per_bucket=1) == select_samples(d, per_bucket=1)


def test_jsonl_roundtrip(tmp_path):
    samples = select_samples(make_loc_dir(tmp_path), per_bucket=1)
    path = tmp_path / "out" / "samples.jsonl"
    write_jsonl(path, (s.to_dict() for s in samples))
    assert [Sample.from_dict(d) for d in read_jsonl(path)] == samples
