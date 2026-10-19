import pytest

from drova_voice.casting import load_casting
from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line, emotion_id
from drova_voice.pools import expand_pool_lines, expand_teacher_lines, load_pools, load_teachers

VOICES = {
    "lena": FishVoice("lena", "a" * 32, "Lena", "f", "de"),
    "leon": FishVoice("leon", "b" * 32, "Leon", "m", "de"),
    "jonas": FishVoice("jonas", "c" * 32, "Jonas", "m", "de"),
}


def line(key="Plh_1", actor="NPC", category="bark", generic=True, skip=None, variant=None):
    base = f"DT_W|Dialog/W|{key}"
    return Line(
        id=base + (f"#{variant}" if variant else ""),
        tree="DT_W",
        loca_path="Dialog/W",
        loca_key=key,
        node_type="statement",
        choice_index=None,
        actor=actor,
        category=category,
        generic=generic,
        raw="x",
        speech="Hallo",
        stage=(),
        skip=skip,
    )


def write(tmp_path, text):
    path = tmp_path / "pools.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_pools_names_tags_by_gender_and_position(tmp_path):
    pools = load_pools(write(tmp_path, "pools:\n  m: [leon, jonas]\n  w: [lena]\n"), VOICES)
    assert pools == {"vm1": "leon", "vm2": "jonas", "vw1": "lena"}


def test_missing_pools_file_is_an_empty_pool(tmp_path):
    assert load_pools(tmp_path / "gibtsnicht.yaml", VOICES) == {}


def test_a_single_voice_instead_of_a_list_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Liste") as caught:
        load_pools(write(tmp_path, "pools:\n  m: leon\n"), VOICES)
    assert "l" not in str(caught.value).split("Liste")[-1]


def test_unknown_voice_and_bad_gender_are_clear_errors(tmp_path):
    with pytest.raises(ValueError, match="gibtsnicht"):
        load_pools(write(tmp_path, "pools:\n  m: [gibtsnicht]\n"), VOICES)
    with pytest.raises(ValueError, match="x"):
        load_pools(write(tmp_path, "pools:\n  x: [leon]\n"), VOICES)


def test_generic_lines_are_replaced_by_one_line_per_pool_voice():
    pools = {"vm1": "leon", "vw1": "lena"}
    out = expand_pool_lines([line()], pools)
    assert [l.id for l in out] == ["DT_W|Dialog/W|Plh_1#vm1", "DT_W|Dialog/W|Plh_1#vw1"]
    assert [l.pool for l in out] == ["vm1", "vw1"]
    assert all(l.speech == "Hallo" and l.category == "bark" for l in out)


def test_named_skipped_and_variant_lines_stay_as_they_are():
    pools = {"vm1": "leon"}
    named = line("Plh_2", actor="Tadhg", generic=False)
    skipped = line("Plh_3", skip="unspeakable")
    neutral = line("Plh_4", variant="neutral")
    assert expand_pool_lines([named, skipped, neutral], pools) == [named, skipped, neutral]


def test_empty_pool_changes_nothing():
    lines = [line()]
    assert expand_pool_lines(lines, {}) == lines


def test_pool_line_gets_its_voice_from_the_pool(tmp_path):
    (tmp_path / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    pools = load_pools(write(tmp_path, "pools:\n  m: [jonas]\n"), VOICES)
    casting = load_casting(tmp_path / "casting.yaml", VOICES, pools_path=tmp_path / "pools.yaml")
    pool_line = expand_pool_lines([line()], pools)[0]
    assert casting.voice_for(pool_line) == "jonas"
    assert (
        casting.voice_for(line()) is None
    )  # ohne Erweiterung bleibt der generische Sprecher unbesetzt


def test_emotion_id_is_the_base_id_for_pool_lines():
    pool_line = expand_pool_lines([line()], {"vm1": "leon"})[0]
    assert emotion_id(pool_line) == "DT_W|Dialog/W|Plh_1"
    assert emotion_id(line("Plh_9", variant="neutral")) == "DT_W|Dialog/W|Plh_9#neutral"


def write_teachers(tmp_path, text):
    path = tmp_path / "teachers.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_teachers_lowercases_and_drops_duplicates(tmp_path):
    assert load_teachers(write_teachers(tmp_path, "teachers: [Mira, tadhg, mira]\n")) == ["mira", "tadhg"]


def test_missing_teachers_file_means_no_teachers(tmp_path):
    assert load_teachers(tmp_path / "gibtsnicht.yaml") == []


def test_a_teacher_name_with_a_separator_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="a#b"):
        load_teachers(write_teachers(tmp_path, "teachers: ['a#b']\n"))


def test_teacher_lines_get_one_variant_per_teacher_next_to_the_pool_variants():
    teach = line("Plh_5", actor="Teacher", category="dialog")
    other = line("Plh_6", actor="NPC", category="dialog")
    out = expand_teacher_lines(expand_pool_lines([teach, other], {"vw1": "lena"}), [teach, other], ["mira", "tadhg"])
    assert [l.id for l in out] == [
        "DT_W|Dialog/W|Plh_5#vw1", "DT_W|Dialog/W|Plh_6#vw1",
        "DT_W|Dialog/W|Plh_5#t_mira", "DT_W|Dialog/W|Plh_5#t_tadhg",
    ]
    assert out[2].pool == "t_mira"


def test_named_and_skipped_teacher_lines_get_no_teacher_variants():
    named = line("Plh_7", actor="Teacher", generic=False)
    skipped = line("Plh_8", actor="Teacher", skip="unspeakable")
    assert expand_teacher_lines([named, skipped], [named, skipped], ["mira"]) == [named, skipped]


def test_teacher_variant_speaks_with_the_teachers_own_voice(tmp_path):
    (tmp_path / "casting.yaml").write_text("default_player: leon\nspeakers:\n  mira: {voice: lena}\n", encoding="utf-8")
    casting = load_casting(tmp_path / "casting.yaml", VOICES)
    teach = line("Plh_5", actor="Teacher", category="dialog")
    mira, ghost = expand_teacher_lines([], [teach], ["mira", "ghost"])
    assert casting.voice_for(mira) == "lena"
    assert casting.voice_for(ghost) is None   # Lehrer ohne Besetzung: Lücke wie bei jedem unbesetzten Sprecher
    assert emotion_id(mira) == "DT_W|Dialog/W|Plh_5"
