import pytest

from drova_voice.casting import cast_report, load_casting, tree_conflicts, voice_speakers, write_auto_casting
from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line

VOICES = {
    "lena": FishVoice("lena", "a" * 32, "Lena", "f", "de"),
    "leon": FishVoice("leon", "b" * 32, "Leon", "m", "de"),
}


def line(actor, category="dialog", skip=None, key="Plh_1"):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw="x", speech="x", stage=(), skip=skip)


def write(tmp_path, text):
    path = tmp_path / "casting.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_voice_for_speaker_and_player(tmp_path):
    c = load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  Mira: {voice: lena}\n"), VOICES)
    assert c.voice_for(line("Mira")) == "lena"
    assert c.voice_for(line("MIRA")) == "lena"  # Groß-/Kleinschreibung egal
    assert c.voice_for(line("Player", category="player")) == "leon"
    assert c.voice_for(line("Fremder")) is None


def test_unknown_voice_is_a_clear_error(tmp_path):
    path = write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: gibtsnicht}\n")
    with pytest.raises(ValueError, match="gibtsnicht.*mira"):
        load_casting(path, VOICES)


def test_unknown_default_player_and_missing_default(tmp_path):
    with pytest.raises(ValueError, match="default_player"):
        load_casting(write(tmp_path, "default_player: nix\nspeakers: {}\n"), VOICES)
    with pytest.raises(ValueError, match="default_player"):
        load_casting(write(tmp_path, "speakers: {}\n"), VOICES)


def test_duplicate_speaker_after_lowercasing(tmp_path):
    path = write(tmp_path, "default_player: leon\nspeakers:\n  Mira: {voice: lena}\n  mira: {voice: leon}\n")
    with pytest.raises(ValueError, match="doppelt"):
        load_casting(path, VOICES)


def test_cast_report_counts_missing_and_usage(tmp_path):
    c = load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: lena}\n"), VOICES)
    lines = [line("Mira", key="Plh_1"), line("Mira", key="Plh_2"), line("Fremder", key="Plh_3"),
             line("Player", "player", key="Plh_4"), line("Fremder", skip="gvar", key="Plh_5")]
    report = cast_report(lines, c)
    assert report.missing == {"Fremder": 1}
    assert report.usage == {"lena": 2, "leon": 1}


def test_short_form_speaker_entry_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="mira.*voice"):
        load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  mira: lena\n"), VOICES)


def test_auto_file_is_overridden_by_manual(tmp_path):
    manual = write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: leon}\n")
    auto = tmp_path / "casting_auto.yaml"
    auto.write_text("speakers:\n  mira: {voice: lena}\n  bo: {voice: leon}\n", encoding="utf-8")
    c = load_casting(manual, VOICES, auto)
    assert c.speakers == {"bo": "leon", "mira": "leon"}
    assert c.auto == frozenset({"bo"})


def test_missing_auto_file_is_fine(tmp_path):
    manual = write(tmp_path, "default_player: leon\nspeakers: {}\n")
    c = load_casting(manual, VOICES, tmp_path / "gibt_es_nicht.yaml")
    assert c.speakers == {} and c.auto == frozenset()


def test_auto_file_with_unknown_voice_names_the_file(tmp_path):
    manual = write(tmp_path, "default_player: leon\nspeakers: {}\n")
    auto = tmp_path / "casting_auto.yaml"
    auto.write_text("speakers:\n  mira: {voice: gibtsnicht}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="casting_auto.yaml.*gibtsnicht"):
        load_casting(manual, VOICES, auto)


def test_auto_file_roundtrip_with_special_names(tmp_path):
    names = {"herr müller": "lena", 'o"brien': "leon", "a b": "lena", "yes": "leon"}
    manual = write(tmp_path, "default_player: leon\nspeakers: {}\n")
    auto = tmp_path / "casting_auto.yaml"
    write_auto_casting(auto, names)
    assert load_casting(manual, VOICES, auto).speakers == names


def tline(key, actor, tree="T1", skip=None, category="dialog"):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw="x", speech="x", stage=(), skip=skip)


def test_voice_speakers_and_tree_conflicts(tmp_path):
    c = load_casting(write(tmp_path, "default_player: leon\nspeakers:\n  mira: {voice: lena}\n  bo: {voice: lena}\n  cy: {voice: leon}\n"), VOICES)
    lines = [tline("1", "Mira"), tline("2", "Bo"), tline("3", "Cy"), tline("4", "Mira", tree="T2"), tline("5", "Bo", tree="T3"),
             tline("6", "Mira", tree="T4", skip="gvar"), tline("7", "Fremder")]
    assert voice_speakers(lines, c) == {"lena": {"mira", "bo"}, "leon": {"cy"}}
    assert tree_conflicts(lines, c) == [("T1", "lena", ["bo", "mira"])]
