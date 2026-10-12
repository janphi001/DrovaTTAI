from pathlib import Path

import pytest

from drova_voice.bakeoff import VoiceSpec, load_voice_specs
from drova_voice.fish_voices import FishVoice, load_fish_voices, resolve_fish_voice

REAL_TABLE = Path(__file__).resolve().parents[2] / "casting" / "fish_voices.yaml"
ID_A = "a" * 32
ID_B = "b" * 32


def _table(tmp_path, body):
    p = tmp_path / "fish_voices.yaml"
    p.write_text(body, encoding="utf-8")
    return load_fish_voices(p)


def test_real_table_has_the_eight_official_voices_with_valid_ids():
    table = load_fish_voices(REAL_TABLE)
    assert len(table) == 8 and {"lena", "leon", "valentina"} <= set(table)
    assert all(len(v.id) == 32 and v.gender in ("m", "f") for v in table.values())


def test_resolve_by_name_ignores_case_and_passes_ids_through(tmp_path):
    table = _table(tmp_path, f"voices:\n  lena: {{id: '{ID_A}', label: Lena, gender: f, region: de}}\n")
    assert resolve_fish_voice(table, "LENA").id == ID_A
    assert resolve_fish_voice(table, ID_B).id == ID_B
    with pytest.raises(ValueError, match="Unbekannte Fish-Stimme 'nope'"):
        resolve_fish_voice(table, "nope")


@pytest.mark.parametrize("body, message", [
    ("voices:\n  x: {id: 'zu-kurz', label: X, gender: f, region: de}\n", "ID"),
    (f"voices:\n  x: {{id: '{ID_A}', label: X, gender: q, region: de}}\n", "gender"),
    ("nichts: 1\n", "voices"),
])
def test_invalid_tables_are_rejected_in_german(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        _table(tmp_path, body)


def test_voice_specs_resolve_fish_names_and_get_a_readable_slug(tmp_path):
    (tmp_path / "casting").mkdir()
    (tmp_path / "casting" / "fish_voices.yaml").write_text(
        f"voices:\n  lena: {{id: '{ID_A}', label: Lena, gender: f, region: de}}\n", encoding="utf-8")
    voices = tmp_path / "voices.yaml"
    voices.write_text("- {engine: fish, voice: lena}\n- {engine: kitten, voice: German}\n", encoding="utf-8")
    fish, kitten = load_voice_specs(voices, tmp_path)
    assert fish.voice == ID_A and fish.slug == "lena" and kitten.slug == "german"


def test_label_beats_voice_for_the_slug():
    assert VoiceSpec("fish", voice="x" * 32, label="Lena").slug == "lena"
