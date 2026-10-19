from drova_voice.speech_text import StageDirection, apply_lexicon, build_speech_text


def test_line_with_stage_direction_and_config_gvar():
    raw = (
        "*blinzelt langsam* Die Brücke aus Holz trägt noch gut. "
        "Der $GVAR:QuestVars_Beispiel_Config.Betrag$ Betrag passt mir gut."
    )
    st = build_speech_text(raw, {"QuestVars_Beispiel_Config.Betrag": "150"})
    assert (
        st.text == "Die Brücke aus Holz trägt noch gut. Der einhundertfünfzig Betrag passt mir gut."
    )
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
    assert (
        build_speech_text("Nimm die <color=#ff0000>Kupferlampe</color>.").text
        == "Nimm die Kupferlampe."
    )


def test_only_stage_direction_is_not_speakable():
    st = build_speech_text("*grinst*")
    assert st.text == ""
    assert not st.is_speakable


def test_ellipsis_only_is_not_speakable():
    assert not build_speech_text("...").is_speakable


def test_numbers_to_german_words():
    assert (
        build_speech_text("Das kostet 25 Bronzeplatten.").text
        == "Das kostet fünfundzwanzig Bronzeplatten."
    )


def test_lexicon_whole_words_only():
    assert (
        apply_lexicon("Zorvana und Zorvanaia", {"Zorvana": "Zorvanna"}) == "Zorvanna und Zorvanaia"
    )


def test_lexicon_does_not_rescan_a_pronunciation():
    assert (
        apply_lexicon("Zorgrad und Sorgrad", {"Zorgrad": "Sorgrad", "Sorgrad": "Torgrad"})
        == "Sorgrad und Torgrad"
    )


def _filler(n: int) -> str:
    # Invented words, exactly n characters, ends on a letter (no edge whitespace).
    return ("ruhig und still " * 40)[:n]


def test_long_stage_direction_at_start_is_removed_and_recorded():
    long_dir = _filler(200)
    st = build_speech_text(f"*{long_dir}* Die Antwort ist klar.")
    assert st.text == "Die Antwort ist klar."
    assert st.stage == (StageDirection(long_dir, 0),)


def test_long_stage_direction_in_the_middle_is_removed_with_correct_pos():
    long_dir = _filler(200)
    st = build_speech_text(f"Na gut *{long_dir}*, dann eben.")
    assert st.text == "Na gut, dann eben."
    assert st.stage == (StageDirection(long_dir, 6),)


def test_stage_direction_of_exactly_300_chars_is_removed():
    long_dir = _filler(300)
    st = build_speech_text(f"*{long_dir}* Ende.")
    assert st.text == "Ende."
    assert st.stage == (StageDirection(long_dir, 0),)


def test_lexicon_replacement_keeps_backslash_literal():
    assert (
        apply_lexicon("Das Zorvana ist hier", {"Zorvana": "Zor\\vana"}) == "Das Zor\\vana ist hier"
    )
