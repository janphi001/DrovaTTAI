from drova_voice.speech_text import StageDirection, apply_lexicon, build_speech_text


def test_line_with_stage_direction_and_config_gvar():
    raw = ("*blinzelt langsam* Die Brücke aus Holz trägt noch gut. "
           "Der $GVAR:QuestVars_Beispiel_Config.Betrag$ Betrag passt mir gut.")
    st = build_speech_text(raw, {"QuestVars_Beispiel_Config.Betrag": "150"})
    assert st.text == "Die Brücke aus Holz trägt noch gut. Der einhundertfünfzig Betrag passt mir gut."
    assert st.stage == (StageDirection("blinzelt langsam", 0),)
    assert st.unresolved_gvars == ()


def test_stage_direction_in_the_middle_keeps_punctuation_clean():
    st = build_speech_text("Fein *seufzt*, dann eben.")
    assert st.text == "Fein, dann eben."
    assert st.stage == (StageDirection("seufzt", 4),)


def test_unresolved_gvar_is_removed_and_reported():
    st = build_speech_text("Mir fehlen $GVAR:EVars_Beispiel.SilberMenge$ Kisten.")
    assert st.text == "Mir fehlen Kisten."
    assert st.unresolved_gvars == ("EVars_Beispiel.SilberMenge",)


def test_br_becomes_sentence_break_or_space():
    assert build_speech_text("Stern<br>Wer da?").text == "Stern. Wer da?"
    assert build_speech_text("Stern!<br><br>Wer da?").text == "Stern! Wer da?"


def test_rich_text_tags_are_removed():
    assert build_speech_text("Nimm die <color=#ff0000>Kupferlampe</color>.").text == "Nimm die Kupferlampe."


def test_only_stage_direction_is_not_speakable():
    st = build_speech_text("*grinst*")
    assert st.text == ""
    assert not st.is_speakable


def test_ellipsis_only_is_not_speakable():
    assert not build_speech_text("...").is_speakable


def test_numbers_to_german_words():
    assert build_speech_text("Das kostet 25 Bronzeplatten.").text == "Das kostet fünfundzwanzig Bronzeplatten."


def test_lexicon_whole_words_only():
    assert apply_lexicon("Zorvana und Zorvanaia", {"Zorvana": "Zorvanna"}) == "Zorvanna und Zorvanaia"
