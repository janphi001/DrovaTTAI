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
    f.write_bytes("﻿Tst_1 { Äußerst Kappa Lambda. }\r\n\r\nTst_2 { Noch Iota? }\r\n".encode("utf-8"))
    res = read_loc_file(f)
    assert [(e.key, e.text) for e in res.entries] == [
        ("Tst_1", "Äußerst Kappa Lambda."),
        ("Tst_2", "Noch Iota?"),
    ]


def test_key_with_spaces_and_braces_in_text():
    res = parse_loc("Test Key_name { Ersatzteil {selten} Omega }\n")
    assert res.entries[0].key == "Test Key_name"
    assert res.entries[0].text == "Ersatzteil {selten} Omega"


def test_multiline_entry():
    content = "Brief_1 { Liebe Mu,\nich komme bald Sigma.\nDein Rho }\n\nTst_2 { Kurz Tau. }\n"
    res = parse_loc(content)
    assert res.entries[0].key == "Brief_1"
    assert res.entries[0].text == "Liebe Mu,\nich komme bald Sigma.\nDein Rho"
    assert res.entries[1].key == "Tst_2"
    assert res.entries[1].line == 5


def test_multiline_body_lines_are_stripped():
    content = "Kopf Titel Eta \n{\n\tErste Zeile Theta.\n\tZweite Zeile Iota.\n}\n"
    res = parse_loc(content)
    assert res.errors == ()
    assert [(e.key, e.text) for e in res.entries] == [
        ("Kopf Titel Eta", "Erste Zeile Theta.\nZweite Zeile Iota."),
    ]


def test_empty_text():
    res = parse_loc("Tst_9 {  }\nTst_10 {}\n")
    assert [(e.key, e.text) for e in res.entries] == [("Tst_9", ""), ("Tst_10", "")]


def test_garbage_line_is_reported_not_fatal():
    res = parse_loc("kein Eintrag Upsilon\nTst_1 { Ja Phi. }\n")
    assert res.errors == (1,)
    assert res.entries[0].key == "Tst_1"


def test_garbage_followed_by_brace_prefixed_line_is_reported():
    res = parse_loc("kein Eintrag Chi\n{ Tst_1 Psi. }\n")
    assert res.entries == ()
    assert 1 in res.errors


def test_unterminated_multiline_is_reported():
    res = parse_loc("Tst_1 { Anfang Omega\nZeile Nu ohne Abschluss\n")
    assert res.entries == ()
    assert res.errors == (1,)


def test_unterminated_entry_does_not_swallow_next_entry():
    res = parse_loc("Tst_1 { Anfang Alpha\n\nTst_2 { Ende Beta. }\n")
    assert res.errors == (1,)
    assert [(e.key, e.text, e.line) for e in res.entries] == [("Tst_2", "Ende Beta.", 3)]


def test_key_on_own_line_with_brace_on_next_line():
    content = "Kopf Titel Gamma \n{\nEin Block Delta.\nZweite Zeile Epsilon.\n}\n\nTst_2 { Kurz Zeta. }\n"
    res = parse_loc(content)
    assert res.errors == ()
    assert [(e.key, e.text, e.line) for e in res.entries] == [
        ("Kopf Titel Gamma", "Ein Block Delta.\nZweite Zeile Epsilon.", 1),
        ("Tst_2", "Kurz Zeta.", 7),
    ]


def test_loc_rel_path(tmp_path):
    lang_dir = tmp_path / "de"
    f = lang_dir / "Testdir" / "NPC_Testfigur_de.loc"
    assert loc_rel_path(lang_dir, f, "de") == "Testdir/NPC_Testfigur"
