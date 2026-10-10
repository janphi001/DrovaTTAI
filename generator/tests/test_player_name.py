import pytest

from drova_voice.player_name import NAME_TOKEN, has_player_name, make_name_variants

N = NAME_TOKEN


@pytest.mark.parametrize("raw, neutral", [
    (f"Danke, {N}. Der Vogt Zerinda wartet am Brunnen.", "Danke. Der Vogt Zerinda wartet am Brunnen."),
    (f"Hallo {N}! Der Wald riecht nach Regen.", "Hallo! Der Wald riecht nach Regen."),
    (f"Hallo {N}, der Wald riecht nach Regen.", "Hallo, der Wald riecht nach Regen."),
    (f"Nun zu dir, {N} ... Pass auf die Brücke auf.", "Nun zu dir ... Pass auf die Brücke auf."),
    (f"Tarro! {N}!", "Tarro!"),
    (f"{N}, komm mal her.", "Komm mal her."),
])
def test_vocative_is_removed(raw, neutral):
    v = make_name_variants(raw)
    assert v.neutral == neutral
    assert not v.needs_review


@pytest.mark.parametrize("raw", [
    f"Man nennt mich {N}.",
    f"Vorsicht, Pamph. {N} schafft das bestimmt.",
    f"Nett, dass du kommst {N} ... Der Tee ist noch warm.",
    f"Pass auf. {N} ... Der Tee ist noch warm.",
    f"{N}!",
])
def test_name_inside_sentence_needs_review(raw):
    v = make_name_variants(raw)
    assert v.neutral is None
    assert v.needs_review


def test_arden_variant():
    assert make_name_variants(f"Man nennt mich {N}.").arden == "Man nennt mich Arden."


def test_has_player_name():
    assert has_player_name(f"Hallo {N}!")
    assert not has_player_name("Hallo!")
