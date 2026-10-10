import pytest

from drova_voice.emotions import EmotionTag, Event
from drova_voice.render import chatterbox_params, render_kitten, render_request


def test_kitten_emotion_prefix_and_event():
    tag = EmotionTag("stern", 0.3, [Event("sigh", 0)])
    assert render_kitten("Na gut, dann eben.", tag) == "[stern] <sigh> Na gut, dann eben."


def test_kitten_event_in_the_middle():
    tag = EmotionTag(events=[Event("laugh", 6)])
    assert render_kitten("Hallo! Du hier?", tag) == "Hallo! <laugh> Du hier?"


def test_kitten_low_intensity_has_no_prefix():
    assert render_kitten("Schön.", EmotionTag("joyful", 0.2)) == "Schön."


def test_kitten_neutral_plain():
    assert render_kitten("Hallo.", EmotionTag()) == "Hallo."


def test_kitten_emphasis_first_occurrence_whole_word():
    tag = EmotionTag(emphasis=["nie"])
    assert render_kitten("Das mache ich nie wieder, nie.", tag) == "Das mache ich (((nie))) wieder, nie."
    assert render_kitten("Niemand.", EmotionTag(emphasis=["nie"])) == "Niemand."


def test_kitten_emphasis_skips_inserted_event_tag():
    tag = EmotionTag(events=[Event("um", 0)], emphasis=["um"])
    assert render_kitten("Das ist um was", tag) == "<um> Das ist (((um))) was"


@pytest.mark.parametrize("word", ["laugh", "sigh", "pause"])
def test_kitten_emphasis_never_inside_event_tag(word):
    tag = EmotionTag(events=[Event(word, 0)], emphasis=[word])
    assert render_kitten(f"Das ist {word} was", tag) == f"<{word}> Das ist (((" + word + "))) was"


def test_kitten_event_positions_clamped_to_original_text():
    tag = EmotionTag(events=[Event("sigh", 10), Event("laugh", 20)])
    assert render_kitten("Hallo", tag) == "Hallo <sigh> <laugh>"


@pytest.mark.parametrize("tag, expected", [
    (EmotionTag(), {"exaggeration": 0.5, "cfg_weight": 0.5}),
    (EmotionTag("angry", 1.0), {"exaggeration": 0.9, "cfg_weight": 0.3}),
    (EmotionTag("sad", 0.5), {"exaggeration": 0.4, "cfg_weight": 0.5}),
])
def test_chatterbox_params(tag, expected):
    assert chatterbox_params(tag) == expected


def test_render_request_dispatch():
    tag = EmotionTag("angry", 1.0, [Event("growl", 0)])
    assert render_request("kitten", "Raus!", tag) == ("[angry] <growl> Raus!", {})
    assert render_request("chatterbox", "Raus!", tag) == ("Raus!", {"exaggeration": 0.9, "cfg_weight": 0.3})
    assert render_request("xtts", "Raus!", tag) == ("Raus!", {})
    assert render_request("fake", "Raus!", tag) == ("Raus!", {})
    with pytest.raises(ValueError):
        render_request("unknown", "Raus!", tag)
