from pathlib import Path

from drova_voice.loc import loc_rel_path, parse_loc, read_loc_file


def test_single_line_entries_with_blank_lines():
    res = parse_loc("Tst_5 { Erster Satz Alpha! Zweiter Satz Alpha. }\n\nTst_7 { Beta Gamma. }\n")
    assert [(e.key, e.text, e.line) for e in res.entries] == [
        ("Tst_5", "Erster Satz Alpha! Zweiter Satz Alpha.", 1),
        ("Tst_7", "Beta Gamma.", 3),
    ]
    assert res.errors == ()


def test_crlf_and_bom(tmp_path):
    f = tmp_path / "NPC_X_de.loc"
    f.write_bytes("﻿Plh_1 { Grüß dich. }\r\n\r\nPlh_2 { Na? }\r\n".encode("utf-8"))
    res = read_loc_file(f)
    assert [(e.key, e.text) for e in res.entries] == [("Plh_1", "Grüß dich."), ("Plh_2", "Na?")]


def test_key_with_spaces_and_braces_in_text():
    res = parse_loc("Test Item_name { Testgegenstand {selten} }\n")
    assert res.entries[0].key == "Test Item_name"
    assert res.entries[0].text == "Testgegenstand {selten}"


def test_multiline_entry():
    content = "Letter_1 { Liebe Mara,\nich komme bald.\nDein Jero }\n\nPlh_2 { Ok. }\n"
    res = parse_loc(content)
    assert res.entries[0].key == "Letter_1"
    assert res.entries[0].text == "Liebe Mara,\nich komme bald.\nDein Jero"
    assert res.entries[1].key == "Plh_2"
    assert res.entries[1].line == 5


def test_empty_text():
    res = parse_loc("Plh_9 {  }\nPlh_10 {}\n")
    assert [(e.key, e.text) for e in res.entries] == [("Plh_9", ""), ("Plh_10", "")]


def test_garbage_line_is_reported_not_fatal():
    res = parse_loc("das ist kein Eintrag\nPlh_1 { Ja. }\n")
    assert res.errors == (1,)
    assert res.entries[0].key == "Plh_1"


def test_unterminated_multiline_is_reported():
    res = parse_loc("Plh_1 { Anfang\nohne Ende\n")
    assert res.entries == ()
    assert res.errors == (1,)


def test_key_on_own_line_with_brace_on_next_line():
    content = "Lockpick_Title \n{\nEin Schloss.\nZweite Zeile.\n}\n\nPlh_2 { Ok. }\n"
    res = parse_loc(content)
    assert res.errors == ()
    assert [(e.key, e.text, e.line) for e in res.entries] == [
        ("Lockpick_Title", "Ein Schloss.\nZweite Zeile.", 1),
        ("Plh_2", "Ok.", 7),
    ]


def test_loc_rel_path(tmp_path):
    lang_dir = tmp_path / "de"
    f = lang_dir / "Dialog" / "NPC_Adela_de.loc"
    assert loc_rel_path(lang_dir, f, "de") == "Dialog/NPC_Adela"
