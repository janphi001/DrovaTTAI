from pathlib import Path

import pytest

from drova_voice.bakeoff import VoiceSpec, load_voice_specs
from drova_voice.fish_voices import FishVoice, load_catalog, load_fish_voices, resolve_fish_voice

REAL_TABLE = Path(__file__).resolve().parents[2] / "casting" / "fish_voices.yaml"
ID_A = "a" * 32
ID_B = "b" * 32


def _table(tmp_path, body):
    p = tmp_path / "fish_voices.yaml"
    p.write_text(body, encoding="utf-8")
    return load_fish_voices(p)


def test_real_table_has_the_eight_official_voices_plus_selected_library_voices():
    table = load_fish_voices(REAL_TABLE)
    assert len(table) >= 8 and {"lena", "leon", "melanie", "lukas", "emma", "elin", "jonas", "valentina"} <= set(table)
    assert all(len(v.id) == 32 and v.gender in ("m", "f") for v in table.values())
    assert len({v.id for v in table.values()}) == len(table)


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


def test_real_variants_point_to_existing_voices_with_sane_factors():
    import yaml

    raw = yaml.safe_load(REAL_TABLE.read_text(encoding="utf-8"))
    table = load_fish_voices(REAL_TABLE)
    assert raw["variants"]
    for key, v in raw["variants"].items():
        assert v["base"] in table, key
        assert v["gender"] in ("m", "f")
        assert all(0.5 <= v[f] <= 1.6 for f in ("pitch", "formant", "tempo")), key


VARIANTS_BODY = (
    f"voices:\n"
    f"  lena: {{id: '{ID_A}', label: Lena, gender: f, region: de, age: mittel}}\n"
    f"  leon: {{id: '{ID_B}', label: Leon, gender: m, region: de}}\n"
    "variants:\n"
    "  riese: {base: leon, label: Riese, gender: m, age: mittel, type: riese, pitch: 0.75, formant: 0.85, tempo: 0.93}\n"
)


def _catalog(tmp_path, body):
    p = tmp_path / "fish_voices.yaml"
    p.write_text(body, encoding="utf-8")
    return load_catalog(p)


def test_catalog_reads_voices_variants_and_synth_table(tmp_path):
    c = _catalog(tmp_path, VARIANTS_BODY)
    assert c.voices["lena"].age == "mittel" and c.voices["leon"].age is None
    v = c.variants["riese"]
    assert (v.base, v.gender, v.age, v.type, v.pitch, v.formant, v.tempo) == ("leon", "m", "mittel", "riese", 0.75, 0.85, 0.93)
    assert c.synth_table()["riese"].id == ID_B  # Variante wird mit der Basisstimme erzeugt
    assert set(c.known()) == {"lena", "leon", "riese"}
    assert [(x.key, x.variant) for x in c.candidates()] == [("lena", False), ("leon", False), ("riese", True)]


@pytest.mark.parametrize("variant, message", [
    ("{base: nix, label: X, gender: m, pitch: 1, formant: 1, tempo: 1}", "Basis"),
    ("{base: leon, label: X, gender: q, pitch: 1, formant: 1, tempo: 1}", "gender"),
    ("{base: leon, label: X, gender: m, type: fee, pitch: 1, formant: 1, tempo: 1}", "type"),
    ("{base: leon, label: X, gender: m, age: uralt, pitch: 1, formant: 1, tempo: 1}", "age"),
    ("{base: leon, label: X, gender: m, pitch: 0, formant: 1, tempo: 1}", "pitch"),
    ("{base: leon, label: X, gender: m, pitch: 1, formant: 1}", "tempo"),
])
def test_invalid_variants_are_rejected_in_german(tmp_path, variant, message):
    body = (f"voices:\n  leon: {{id: '{ID_B}', label: Leon, gender: m, region: de}}\nvariants:\n  v: {variant}\n")
    with pytest.raises(ValueError, match=message):
        _catalog(tmp_path, body)


def test_variant_key_must_not_clash_with_a_voice(tmp_path):
    body = (f"voices:\n  leon: {{id: '{ID_B}', label: Leon, gender: m, region: de}}\n"
            "variants:\n  leon: {base: leon, label: X, gender: m, pitch: 1, formant: 1, tempo: 1}\n")
    with pytest.raises(ValueError, match="doppelt"):
        _catalog(tmp_path, body)


def test_invalid_voice_age_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="age"):
        _table(tmp_path, f"voices:\n  x: {{id: '{ID_A}', label: X, gender: f, region: de, age: uralt}}\n")


def test_real_table_variants_carry_age_and_type():
    c = load_catalog(REAL_TABLE)
    assert set(c.variants) == {"alte_frau_rau", "alte_frau", "riese", "zwerg", "schurke_hell", "jugendlicher", "knabe"}
    assert c.variants["knabe"].age == "kind" and c.variants["riese"].type == "riese" and c.variants["zwerg"].type == "zwerg"
    assert c.variants["alte_frau"].gender == "f" and c.variants["alte_frau"].age == "alt"
    assert c.voices["kind_von_oben_578878"].age == "kind"
