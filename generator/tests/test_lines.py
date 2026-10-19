import pytest

from drova_voice.ids import choice_id, statement_id
from drova_voice.lines import (SKIP_GVAR_NAME, SKIP_GVAR_VALUE, SKIP_ID_MISMATCH, SKIP_PLAYER_CHOICE, SKIP_UNSPEAKABLE, Line, build_lines, load_lexicon,
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


def test_lexicon_replaces_each_listed_word_once():
    (line,) = build_lines(manifest(mline("Plh_1")), {}, {"Zorgrad": "Sorgrad", "Sorgrad": "Torgrad"})
    assert line.speech == "Text aus dem Manifest."
    (line,) = build_lines(
        manifest(mline("Plh_1", text="Zorgrad und Sorgrad bleiben stehen.")),
        {},
        {"Zorgrad": "Sorgrad", "Sorgrad": "Torgrad"},
    )
    assert line.speech == "Sorgrad und Torgrad bleiben stehen."


def test_empty_lexicon_key_is_rejected_before_lines_are_built():
    with pytest.raises(ValueError, match="leer"):
        build_lines(manifest(mline("Plh_1")), {}, {"": "Sorgrad"})


NAME = "$GVAR:EVars_Player.Name$"


def test_name_line_becomes_a_neutral_variant():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"Hallo {NAME}!"})
    assert line.id == statement_id(TREE, PATH, "Plh_1") + "#neutral"
    assert line.speech == "Hallo!" and line.raw == f"Hallo {NAME}!" and line.skip is None


def test_name_line_keeps_stage_directions_in_the_neutral_variant():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"*lacht* Hallo {NAME}!"})
    assert line.speech == "Hallo!" and line.stage[0]["text"] == "lacht" and line.id.endswith("#neutral")


def test_name_line_without_neutral_version_is_skipped_as_gvar_name():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"Komm mit {NAME} zum Brunnen."})
    assert line.skip == SKIP_GVAR_NAME and line.speech == "" and line.id == statement_id(TREE, PATH, "Plh_1")


def test_name_line_with_only_the_name_is_skipped_as_gvar_name():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"*seufzt* {NAME}!"})
    assert line.skip == SKIP_GVAR_NAME and line.speech == ""


def test_name_after_a_comma_is_dropped_in_the_neutral_variant():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"*grinst* Danke, {NAME}."})
    assert line.skip is None and line.speech == "Danke." and line.id.endswith("#neutral")


def test_value_placeholder_is_skipped_as_gvar_value():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): "Heute sind $GVAR:QuestVars_Beispiel_Config.Preis$ Münzen."})
    assert line.skip == SKIP_GVAR_VALUE and line.speech == ""


def test_name_together_with_a_value_is_skipped_as_gvar_value():
    (line,) = build_lines(manifest(mline("Plh_1")), {(PATH, "Plh_1"): f"Hallo {NAME}, das kostet $GVAR:A.B$ Münzen."})
    assert line.skip == SKIP_GVAR_VALUE and not line.id.endswith("#neutral")


def test_neutral_duplicate_ids_still_keep_the_first():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_1", text="Zweite Fassung.")), {(PATH, "Plh_1"): f"Hallo {NAME}!"})
    assert len(lines) == 1 and lines[0].id.endswith("#neutral")


def test_unspeakable_lines_are_skipped():
    lines = build_lines(manifest(mline("Plh_1"), mline("Plh_2")), {(PATH, "Plh_1"): "*seufzt*", (PATH, "Plh_2"): "…"})
    assert [l.skip for l in lines] == [SKIP_UNSPEAKABLE, SKIP_UNSPEAKABLE]


def test_id_mismatch_is_skipped():
    (line,) = build_lines(manifest(mline("Plh_1", id="Falsch|Pfad|Plh_1")), {})
    assert line.skip == SKIP_ID_MISMATCH and line.speech == ""


def test_choice_line_id_uses_the_index_but_is_not_spoken():
    # Das Spiel spricht Auswahloptionen nicht (Nutzerentscheidung 2026-10-15): ID und Index bleiben, der Text wird nicht vertont.
    row = mline("Plh_3", nodeType="choice", choiceIndex=2, actorName="Player", category="player",
                id=choice_id(TREE, PATH, "Plh_3", 2))
    (line,) = build_lines(manifest(row), {(PATH, "Plh_3"): "Zum Brunnen, bitte."})
    assert line.skip == SKIP_PLAYER_CHOICE and line.speech == "" and line.choice_index == 2 and line.id.endswith("|c2")


def test_player_statements_are_still_spoken():
    row = mline("Plh_4", actorName="Player", category="player")
    (line,) = build_lines(manifest(row), {(PATH, "Plh_4"): "Ich komme von weit her."})
    assert line.skip is None and line.speech == "Ich komme von weit her."


def test_choice_with_bad_id_reports_the_id_problem_first():
    row = mline("Plh_3", nodeType="choice", choiceIndex=2, actorName="Player", category="player", id="Falsch|Pfad|Plh_3")
    (line,) = build_lines(manifest(row), {})
    assert line.skip == SKIP_ID_MISMATCH


def test_boolean_choice_index_is_an_id_mismatch():
    row = mline("Plh_3", nodeType="choice", choiceIndex=True, actorName="Player", category="player",
                id=choice_id(TREE, PATH, "Plh_3", 1))
    (line,) = build_lines(manifest(row), {(PATH, "Plh_3"): "Zum Brunnen."})
    assert line.skip == SKIP_ID_MISMATCH


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
    (tmp_path / "lex.yaml").write_text('"": Sorgrad\n', encoding="utf-8")
    with pytest.raises(ValueError, match="leer"):
        load_lexicon(tmp_path / "lex.yaml")


def test_valid_line_wins_over_an_earlier_mismatched_duplicate_id():
    good_id = statement_id(TREE, PATH, "Plh_1")
    bad = mline("Plh_1", id=good_id, locaKey="Plh_9")  # Schlüssel passt nicht zur ID
    lines = build_lines(manifest(bad, mline("Plh_1")), {})
    assert len(lines) == 1 and lines[0].skip is None and lines[0].loca_key == "Plh_1"
