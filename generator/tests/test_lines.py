from drova_voice.ids import choice_id, statement_id
from drova_voice.lines import (SKIP_GVAR, SKIP_ID_MISMATCH, SKIP_UNSPEAKABLE, Line, build_lines, load_lexicon,
                               load_loc_texts, read_lines, select_npc, write_lines)

TREE, PATH = "DT_Test_NPC_Mira", "Dialog/NPC_Mira"


def mline(key, **over):
    d = {"id": statement_id(TREE, PATH, key), "tree": TREE, "nodeId": 1, "nodeType": "statement",
         "actorName": "Mira", "category": "dialog", "generic": False, "locaPath": PATH, "locaKey": key,
         "text": "Text aus dem Manifest.", "gvars": []}
    d.update(over)
    return d


def manifest(*lines):
    return {"version": 1, "language": "de", "lines": list(lines)}


def test_loc_text_wins_over_manifest_text():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Text aus der Loc."})
    assert line.raw == "Text aus der Loc." and line.speech == "Text aus der Loc." and line.skip is None


def test_falls_back_to_manifest_text_without_loc_entry():
    (line,) = build_lines(manifest(mline("Plh_1")), {})
    assert line.speech == "Text aus dem Manifest."


def test_stage_directions_are_split_off():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "*seufzt* Das ist lange her."})
    assert line.speech == "Das ist lange her."
    assert line.stage[0]["text"] == "seufzt" and line.stage[0]["pos"] == 0


def test_lexicon_is_applied():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Willkommen in Zorgrad."}, {"Zorgrad": "Sorgrad"})
    assert line.speech == "Willkommen in Sorgrad."


def test_gvar_lines_are_skipped_not_spoken():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Hallo $GVAR:EVars_Player.Name$!"})
    assert line.skip == SKIP_GVAR and line.speech == ""


def test_unspeakable_lines_are_skipped():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_2")), {(PATH, "Plh_1"): "*seufzt*", (PATH, "Plh_2"): "…"})
    assert [l.skip for l in lines] == [SKIP_UNSPEAKABLE, SKIP_UNSPEAKABLE]


def test_id_mismatch_is_skipped():
    (line,) = build_lines(manifest(mline("Plh_1", id="Falsch|Pfad|Plh_1")), {})
    assert line.skip == SKIP_ID_MISMATCH and line.speech == ""


def test_choice_line_id_uses_the_index():
    row = mline("Plh_3", nodeType="choice", choiceIndex=2, actorName="Player", category="player",
                id=choice_id(TREE, PATH, "Plh_3", 2))
    (line,) = build_lines(manifest(row), {(PATH, "Plh_3"): "Zum Brunnen, bitte."})
    assert line.skip is None and line.choice_index == 2 and line.id.endswith("|c2")


def test_duplicate_ids_keep_the_first():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_1", text="Zweite Fassung.")), {})
    assert len(lines) == 1 and lines[0].speech == "Text aus dem Manifest."


def test_select_npc_keeps_whole_trees():
    other = mline("Plh_9", tree="DT_Anders", id=statement_id("DT_Anders", PATH, "Plh_9"), actorName="Bart")
    player = mline("Plh_3", nodeType="choice", choiceIndex=0, actorName="Player", category="player",
                   id=choice_id(TREE, PATH, "Plh_3", 0))
    lines = build_lines(manifest(mline("Plh_1"), player, other), {})
    assert [l.actor for l in select_npc(lines, "mira")] == ["Mira", "Player"]
    assert select_npc(lines, "Nobody") == []


def test_roundtrip_and_loc_loading(tmp_path):
    loc_dir = tmp_path / "loc"
    (loc_dir / "Dialog").mkdir(parents=True)
    (loc_dir / "Dialog" / "NPC_Mira_de.loc").write_text("Plh_1 { Hallo }\n", encoding="utf-8")
    texts = load_loc_texts(loc_dir, "de")
    assert texts == {("Dialog/NPC_Mira", "Plh_1"): "Hallo"}
    lines = build_lines(manifest(mline("Plh_1")), texts)
    write_lines(tmp_path / "lines.jsonl", lines)
    assert read_lines(tmp_path / "lines.jsonl") == lines
    assert isinstance(lines[0], Line)


def test_load_lexicon_missing_or_empty(tmp_path):
    assert load_lexicon(tmp_path / "nix.yaml") == {}
    (tmp_path / "lex.yaml").write_text("# nur Kommentar\n", encoding="utf-8")
    assert load_lexicon(tmp_path / "lex.yaml") == {}
    (tmp_path / "lex.yaml").write_text("Zorgrad: Sorgrad\n", encoding="utf-8")
    assert load_lexicon(tmp_path / "lex.yaml") == {"Zorgrad": "Sorgrad"}


def test_valid_line_wins_over_an_earlier_mismatched_duplicate_id():
    good_id = statement_id(TREE, PATH, "Plh_1")
    bad = mline("Plh_1", id=good_id, locaKey="Plh_9")  # Schlüssel passt nicht zur ID
    lines = build_lines(manifest(bad, mline("Plh_1")), {})
    assert len(lines) == 1 and lines[0].skip is None and lines[0].loca_key == "Plh_1"
