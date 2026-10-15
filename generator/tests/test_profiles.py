import pytest

from drova_voice.lines import Line
from drova_voice.profiles import Profile, merge_import, prepare_packets, read_profiles, write_profiles


def line(key, actor="Anna", speech="Hallo.", tree="T1", category="dialog", generic=False, skip=None):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=generic, raw=speech, speech=speech, stage=(), skip=skip)


def prof(speaker="anna", source="llm", **kw):
    d = {"speaker": speaker, "gender": "f", "age": "mittel", "type": "", "confidence": 0.9, "note": "ruhig", "source": source}
    return Profile.from_dict({**d, **kw})


@pytest.mark.parametrize("bad, message", [
    ({"gender": "x"}, "gender"), ({"age": "uralt"}, "age"), ({"type": "fee"}, "type"),
    ({"confidence": 2}, "confidence"), ({"confidence": "viel"}, "confidence"), ({"speaker": " "}, "speaker"),
    ({"source": "orakel"}, "source"),
])
def test_invalid_profiles_are_rejected_in_german(bad, message):
    with pytest.raises(ValueError, match=message):
        prof(**bad)


def test_profile_normalizes_speaker_type_and_truncates_the_note():
    p = prof(speaker=" Anna ", type=None, note="x" * 500)
    assert p.speaker == "anna" and p.type is None and len(p.note) == 200


def test_roundtrip_and_sorting(tmp_path):
    path = tmp_path / "profiles.jsonl"
    write_profiles(path, [prof("zoe"), prof("anna", type="riese")])
    loaded = read_profiles(path)
    assert list(loaded) == ["anna", "zoe"] and loaded["anna"].type == "riese"
    assert read_profiles(tmp_path / "nix.jsonl") == {}


def test_read_profiles_names_the_bad_line(tmp_path):
    path = tmp_path / "profiles.jsonl"
    path.write_text('{"speaker": "a", "gender": "q", "age": "jung"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Zeile 1"):
        read_profiles(path)


def test_merge_import_rules():
    existing = {"anna": prof("anna", source="manual", gender="m"), "bob": prof("bob", source="llm", gender="m")}
    rows = [{"speaker": "Anna", "gender": "f", "age": "jung"},          # manual bleibt
            {"speaker": "bob", "gender": "f", "age": "alt", "source": "manual", "confidence": 0.7},  # llm wird ersetzt, Quelle erzwungen
            {"speaker": "cy", "gender": "m", "age": "kind"},
            {"speaker": "unbekannt", "gender": "m", "age": "kind"},
            {"speaker": "dee", "gender": "q", "age": "kind"}]
    merged, errors = merge_import(existing, rows, known={"anna", "bob", "cy", "dee"})
    assert merged["anna"].gender == "m" and merged["anna"].source == "manual"
    assert merged["bob"].gender == "f" and merged["bob"].source == "llm"
    assert merged["cy"].age == "kind" and "dee" not in merged and "unbekannt" not in merged
    assert len(errors) == 2 and any("unbekannt" in e for e in errors) and any("dee" in e for e in errors)


def test_prepare_packets_only_missing_named_speakers_with_mentions():
    lines = ([line(f"a{i}", "Anna", f"Anna sagt Nummer {i}.") for i in range(5)]
             + [line("b1", "Bob", "Frag doch Anna, sie weiß es."), line("b2", "Bob", "Anna-Maria ist nicht gemeint? Doch.")]
             + [line("n", "NPC", "Anna!", generic=True), line("p", "Player", "Anna?", category="player"),
                line("g", "Cy", "Anna", skip="gvar")])
    packets = prepare_packets(lines, {}, size=1, max_own=3, max_mentions=5)
    assert [[e["speaker"] for e in p] for p in packets] == [["anna"], ["bob"]]
    anna = packets[0][0]
    assert anna["display"] == "Anna" and anna["lines"] == 5 and len(anna["own"]) == 3
    assert {m["by"] for m in anna["mentions"]} == {"Bob"} and len(anna["mentions"]) == 2
    assert [e["speaker"] for p in prepare_packets(lines, {"anna": prof("anna")}, size=5) for e in p] == ["bob"]
    assert [e["speaker"] for p in prepare_packets(lines, {"anna": prof("anna")}, size=5, include_known=True) for e in p] == ["anna", "bob"]
