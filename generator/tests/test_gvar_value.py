import pytest

from drova_voice.gvar_value import (
    Kind,
    build_inventory,
    format_inventory,
    neutralize_values,
    variable_kind,
)

PRICE = "$GVAR:QuestVars_Beispiel_Config.Preis$"
ROUNDS = "$GVAR:EVars_Arena.Runden$"
NAME = "$GVAR:EVars_Player.Name$"


@pytest.mark.parametrize(
    ("raw", "spoken", "kind"),
    [
        (f"Das kostet {PRICE} Münzen.", "Das kostet ein paar Münzen.", Kind.CURRENCY),
        (f"Für {PRICE} Gold gehört es dir.", "Für etwas Gold gehört es dir.", Kind.CURRENCY),
        (
            f"{PRICE} Goldmünzen, keine weniger.",
            "Ein paar Goldmünzen, keine weniger.",
            Kind.CURRENCY,
        ),
        (f"*zählt* {PRICE} Münzen.", "*zählt* Ein paar Münzen.", Kind.CURRENCY),
        (f"Das kostet *hustet* {PRICE} Gold.", "Das kostet *hustet* etwas Gold.", Kind.CURRENCY),
        (
            f"Du hast {ROUNDS} Runden überstanden.",
            "Du hast ein paar Runden überstanden.",
            Kind.COUNT,
        ),
        (f"Mit {ROUNDS} Gegnern?", "Mit ein paar Gegnern?", Kind.COUNT),
    ],
)
def test_clean_templates_replace_the_value(raw, spoken, kind):
    result = neutralize_values(raw)
    assert result is not None and result.neutral == spoken and result.kind is kind


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        (f"Das macht {PRICE}.", Kind.BARE),  # kein Nomen danach
        (f"Hier ist {PRICE} Münze.", Kind.BARE),  # Einzahl: "ein paar Münze" wäre falsch
        (f"Du bist der {ROUNDS}. Teilnehmer.", Kind.BARE),  # Ordnungszahl
        (f"Das kostet {PRICE} Münzen-Beutel.", Kind.BARE),
        ("Das kostet $GVAR:QuestVars_Beispiel_Config.Wert$ Münzen.", Kind.UNKNOWN),
        ("Frag $GVAR:QuestVars_Beispiel_Config.HaendlerName$ nach Gold.", Kind.NAME),
        (f"Von {ROUNDS} auf {PRICE} Münzen.", Kind.BARE),  # erster Wert ohne Nomen
    ],
)
def test_unclean_lines_stay_silent(raw, kind):
    result = neutralize_values(raw)
    assert result is not None and result.neutral is None and result.kind is kind


@pytest.mark.parametrize(
    ("raw", "spoken"),
    [
        (f"Gib mir deine {PRICE} Münzen.", "Gib mir ein paar Münzen."),
        (f"Etwa {PRICE} Münzen.", "Ein paar Münzen."),
        (f"Hier sind die {PRICE} Münzen.", "Hier sind ein paar Münzen."),
        (f"Nimm das {PRICE} Gold und geh.", "Nimm etwas Gold und geh."),
        (f"Das ist der Lohn: ein {PRICE} Goldstücke.", "Das ist der Lohn: ein paar Goldstücke."),
        (f"Meine {PRICE} Goldmünzen gehören mir!", "Ein paar Goldmünzen gehören mir!"),
        (f"Du willst ungefähr {PRICE} Gold?", "Du willst etwas Gold?"),
        (f"Gib mir die etwa {PRICE} Münzen.", "Gib mir ein paar Münzen."),  # mehrere Vorwörter
        (f"*zählt* deine {PRICE} Münzen.", "*zählt* Ein paar Münzen."),
        (f"Gebt ihr eure {PRICE} Münzen.", "Gebt ihr ein paar Münzen."),  # Pronomen "ihr" bleibt
    ],
)
def test_currency_drops_the_determiner_before_the_value(raw, spoken):
    result = neutralize_values(raw)
    assert result is not None and result.neutral == spoken and result.kind is Kind.CURRENCY


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        (f"Du hast die {ROUNDS} Runden überstanden.", Kind.COUNT),
        (f"Etwa {ROUNDS} Gegner warten.", Kind.COUNT),
        (f"Gebt ihr {PRICE} Gold.", Kind.CURRENCY),  # "ihr" kann Pronomen sein
    ],
)
def test_count_and_ambiguous_words_before_the_value_stay_silent(raw, kind):
    result = neutralize_values(raw)
    assert result is not None and result.neutral is None and result.kind is kind


def test_text_without_value_placeholder_is_not_handled_here():
    assert neutralize_values(f"Hallo {NAME}!") is None
    assert neutralize_values("Ein Satz ohne Platzhalter.") is None


def test_value_with_a_removable_name_is_voiced_without_both():
    result = neutralize_values(f"Das kostet {PRICE} Münzen, {NAME}.")
    assert (
        result is not None
        and result.neutral == "Das kostet ein paar Münzen."
        and result.player_name
    )


def test_value_with_a_name_mid_sentence_stays_silent():
    result = neutralize_values(f"Gib {NAME} {PRICE} Münzen.")
    assert result is not None and result.neutral is None and result.player_name


def test_variable_kinds():
    assert variable_kind("QuestVars_Laden_Config.PackagePrice") is Kind.BARE
    assert variable_kind("EVars_Arena.ParticipantsCount") is Kind.BARE
    assert variable_kind("EVars_Arena.Gegner1Name") is Kind.NAME
    assert variable_kind("QuestVars_Laden_Config.Flag") is Kind.UNKNOWN


def test_inventory_counts_classes_and_lists_silent_placeholders():
    inv = build_inventory(
        [
            (f"Das kostet {PRICE} Münzen.", True),
            (f"Das macht {PRICE}.", False),
            (f"Gib {NAME} {PRICE} Münzen.", False),
            ("Kein Wert hier.", False),
        ]
    )
    assert inv.total == 3
    assert inv.voiced == {Kind.CURRENCY: 1}
    assert inv.silent == {Kind.BARE: 1, Kind.CURRENCY: 1}
    text = format_inventory(inv)
    assert "Zeilen mit Quest- oder Geldwerten: 3 (gesprochen 1, stumm 2)" in text
    assert "currency: gesprochen 1, stumm 1; davon mit Spielername 1" in text
    assert "1x QuestVars_Beispiel_Config.Preis [bare]" in text


def test_empty_inventory():
    assert format_inventory(build_inventory([])) == "keine Zeilen mit Quest- oder Geldwerten"
