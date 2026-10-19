import pytest

from drova_voice.emotions import EmotionTag, Event
from drova_voice.render import chatterbox_params, render_fish, render_kitten, render_request


def test_kitten_emotion_prefix_without_vocal_event():
    # Hörtest 2026-10-10: Kitten liest <sigh>/<laugh> auf Deutsch laut vor, Laut-Tags werden daher nicht gerendert.
    tag = EmotionTag("stern", 0.3, [Event("sigh", 0)])
    assert render_kitten("Na gut, dann eben.", tag) == "[stern] Na gut, dann eben."


@pytest.mark.parametrize("name", ["sigh", "laugh", "gasp", "pause", "um", "growl"])
def test_kitten_never_renders_vocal_events(name):
    tag = EmotionTag(events=[Event(name, 6)])
    assert render_kitten("Hallo! Du hier?", tag) == "Hallo! Du hier?"


def test_kitten_low_intensity_has_no_prefix():
    assert render_kitten("Schön.", EmotionTag("joyful", 0.2)) == "Schön."


def test_kitten_neutral_plain():
    assert render_kitten("Hallo.", EmotionTag()) == "Hallo."


def test_kitten_emphasis_first_occurrence_whole_word():
    tag = EmotionTag(emphasis=["nie"])
    assert (
        render_kitten("Das mache ich nie wieder, nie.", tag)
        == "Das mache ich (((nie))) wieder, nie."
    )
    assert render_kitten("Niemand.", EmotionTag(emphasis=["nie"])) == "Niemand."


def test_kitten_emphasis_still_works_next_to_dropped_events():
    tag = EmotionTag(events=[Event("um", 0)], emphasis=["um"])
    assert render_kitten("Das ist um was", tag) == "Das ist (((um))) was"


@pytest.mark.parametrize(
    "tag, expected",
    [
        (EmotionTag(), {"exaggeration": 0.5, "cfg_weight": 0.5}),
        (EmotionTag("angry", 1.0), {"exaggeration": 0.9, "cfg_weight": 0.3}),
        (EmotionTag("sad", 0.5), {"exaggeration": 0.4, "cfg_weight": 0.5}),
    ],
)
def test_chatterbox_params(tag, expected):
    assert chatterbox_params(tag) == expected


def test_render_request_dispatch():
    tag = EmotionTag("angry", 1.0, [Event("growl", 0)])
    assert render_request("kitten", "Raus!", tag) == ("[angry] Raus!", {"preset": "expressive"})
    assert render_request("chatterbox", "Raus!", tag) == (
        "Raus!",
        {"exaggeration": 0.9, "cfg_weight": 0.3},
    )
    assert render_request("xtts", "Raus!", tag) == ("Raus!", {})
    assert render_request("fake", "Raus!", tag) == ("Raus!", {})
    with pytest.raises(ValueError):
        render_request("unknown", "Raus!", tag)


@pytest.mark.parametrize("engine", ["kitten", "chatterbox", "xtts", "fake"])
@pytest.mark.parametrize("text", ["", "   ", "...", "?!"])
def test_render_request_rejects_text_without_alphanumeric_characters(engine, text):
    with pytest.raises(ValueError, match="sprechbar"):
        render_request(engine, text, EmotionTag())


def test_kitten_uses_the_expressive_preset_only_when_tags_are_rendered():
    _, params = render_request("kitten", "Na gut.", EmotionTag("stern", 0.8))
    assert params == {"preset": "expressive"}
    assert (
        render_request("kitten", "Na gut.", EmotionTag("neutral", 0.0, events=[Event("sigh", 3)]))[
            1
        ]
        == {}
    )
    assert render_request("kitten", "Na gut.", EmotionTag())[1] == {}
    assert render_request("kitten", "Schön.", EmotionTag("joyful", 0.2))[1] == {}


def test_fish_neutral_text_is_plain():
    assert render_fish("Hallo,   Welt.", EmotionTag()) == "Hallo, Welt."


@pytest.mark.parametrize(
    "emotion, intensity, expected",
    [
        ("angry", 0.5, "[angry] Raus!"),
        ("angry", 0.9, "[very angry] Raus!"),
        ("joyful", 0.5, "[happy] Raus!"),
        ("contemplative", 0.5, "[thoughtful] Raus!"),
        ("sad", 0.3, "[sad] Raus!"),
        ("sad", 0.29, "Raus!"),
        ("mundane", 0.9, "Raus!"),
        ("neutral", 0.9, "Raus!"),
    ],
)
def test_fish_emotion_prefix(emotion, intensity, expected):
    assert render_fish("Raus!", EmotionTag(emotion, intensity)) == expected


def test_fish_events_are_inserted_at_their_position_and_unknown_ones_dropped():
    tag = EmotionTag(events=[Event("sigh", 6), Event("gasp", 0), Event("um", 3)])
    assert render_fish("Hallo! Du hier?", tag) == "Hallo! [sighing] Du hier?"
    assert (
        render_fish("Na gut.", EmotionTag(events=[Event("pause", 0), Event("laugh", 99)]))
        == "[break] Na gut. [laughing]"
    )


def test_fish_emphasis_marks_the_first_whole_word_but_never_inside_a_cue():
    tag = EmotionTag(emphasis=["nie"])
    assert (
        render_fish("Das mache ich nie wieder, nie.", tag)
        == "Das mache ich [emphasis] nie wieder, nie."
    )
    assert render_fish("Niemand.", tag) == "Niemand."
    tag = EmotionTag(events=[Event("pause", 0)], emphasis=["break"])
    assert render_fish("Ein break hier", tag) == "[break] Ein [emphasis] break hier"


def test_render_request_for_fish_has_no_params_and_rejects_unspeakable_text():
    tag = EmotionTag("angry", 1.0, [Event("sigh", 0)])
    assert render_request("fish", "Raus!", tag) == ("[very angry] [sighing] Raus!", {})
    with pytest.raises(ValueError, match="nicht sprechbar"):
        render_request("fish", "... *", EmotionTag())
