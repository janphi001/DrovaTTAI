import pytest

from drova_voice.emotions import EmotionTag, Event, from_stage_directions
from drova_voice.speech_text import StageDirection


def test_defaults_are_neutral():
    t = EmotionTag()
    assert (t.emotion, t.intensity, t.events, t.source) == ("neutral", 0.0, [], "default")


@pytest.mark.parametrize("kwargs", [
    {"emotion": "furious"},
    {"intensity": 1.5},
    {"events": [Event("cough", 0)]},
    {"source": "guess"},
])
def test_validation(kwargs):
    with pytest.raises(ValueError):
        EmotionTag(**kwargs)


def test_roundtrip_dict():
    t = EmotionTag("stern", 0.6, [Event("sigh", 3)], ["nie"], ["whisper"], "llm")
    assert EmotionTag.from_dict(t.to_dict()) == t


def test_sigh_becomes_event():
    t = from_stage_directions([StageDirection("seufzt", 0)])
    assert t.events == [Event("sigh", 0)]
    assert t.emotion == "neutral"
    assert t.source == "stage"


def test_strongest_emotion_wins_and_events_collect():
    t = from_stage_directions([StageDirection("grinst", 0), StageDirection("knurrt leise", 5)])
    assert (t.emotion, t.intensity) == ("angry", 0.5)
    assert t.events == [Event("growl", 5)]


def test_notes_for_whisper_and_drunk():
    t = from_stage_directions([StageDirection("flüstert", 0), StageDirection("hick", 4)])
    assert t.notes == ["whisper", "drunk"]


def test_word_start_matching_avoids_false_hits():
    t = from_stage_directions([StageDirection("schickt dich weg", 0)])
    assert t.notes == []
    assert t.source == "default"


def test_unknown_direction_keeps_default():
    t = from_stage_directions([StageDirection("tanzt", 0)])
    assert t == EmotionTag()
