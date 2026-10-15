from collections import Counter

from drova_voice.assign import assign, mismatch
from drova_voice.fish_voices import Candidate
from drova_voice.profiles import Profile
from drova_voice.selection import SpeakerStat


def S(name, lines, *trees):
    return SpeakerStat(name, name.title(), lines, lines * 40, frozenset(trees or {f"t_{name}"}))


def P(name, gender="m", age="mittel", type=None, conf=0.9):
    return Profile(name, gender, age, type, conf, "", "llm")


ANNA = Candidate("anna", "f", "mittel", None, False)
BERTA = Candidate("berta", "f", "alt", None, False)
CARL = Candidate("carl", "m", "mittel", None, False)
CARL2 = Candidate("carl2", "m", "mittel", None, False)
DIRK = Candidate("dirk", "m", "jung", None, False)
RIESE = Candidate("riese", "m", "mittel", "riese", True)
KNABE = Candidate("knabe", "m", "kind", None, True)
ALL = [ANNA, BERTA, CARL, CARL2, DIRK, RIESE, KNABE]


def test_gender_is_a_hard_filter_and_age_decides_among_the_rest():
    r = assign([S("x", 10)], {"x": P("x", "f", "alt")}, ALL, {})
    assert r.voices == {"x": "berta"} and r.open == [] and r.emergency == {}


def test_type_match_wins_and_plain_speakers_avoid_special_variants():
    r = assign([S("giant", 20), S("plain", 10)], {"giant": P("giant", type="riese"), "plain": P("plain")}, ALL, {})
    assert r.voices["giant"] == "riese" and r.voices["plain"] == "carl"


def test_child_voices_are_reserved_for_children():
    r = assign([S("lad", 10)], {"lad": P("lad", age="jung")}, [DIRK, KNABE], {})
    assert r.voices["lad"] == "dirk"
    r = assign([S("kid", 10)], {"kid": P("kid", age="kind")}, [DIRK, KNABE], {})
    assert r.voices["kid"] == "knabe" and r.emergency == {}


def test_load_is_spread_over_equal_voices():
    stats = [S("a", 40), S("b", 30), S("c", 20), S("d", 10)]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL, CARL2], {})
    assert Counter(r.voices.values()) == {"carl": 2, "carl2": 2}


def test_speakers_sharing_a_tree_get_different_voices_when_possible():
    stats = [S("p", 20, "t1", "t2"), S("q", 10, "t2"), S("r", 5, "t9")]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL, CARL2], {})
    assert r.voices["p"] != r.voices["q"]


def test_a_single_voice_is_shared_instead_of_failing():
    stats = [S("p", 20, "t1"), S("q", 10, "t1")]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL], {})
    assert r.voices == {"p": "carl", "q": "carl"}


def test_pinned_speakers_stay_out_of_the_result_but_count_for_conflicts():
    stats = [S("p", 20, "t1"), S("q", 10, "t1")]
    r = assign(stats, {s.name: P(s.name) for s in stats}, [CARL, CARL2], {"p": "carl"})
    assert r.voices == {"q": "carl2"}


def test_speaker_without_a_profile_stays_open_and_nobody_else_is_affected():
    stats = [S("ghost", 50), S("x", 10)]
    r = assign(stats, {"x": P("x")}, [CARL], {})
    assert r.open == ["ghost"] and r.voices == {"x": "carl"}


def test_emergency_reports_missing_type_and_missing_child_voice():
    r = assign([S("dwarf", 9), S("girl", 8)], {"dwarf": P("dwarf", type="zwerg"), "girl": P("girl", "f", "kind")}, [CARL, ANNA], {})
    assert r.emergency == {"dwarf": "Typ 'zwerg' ohne passende Stimme", "girl": "Kind ohne Kinderstimme"}
    assert mismatch(P("o", "f", "jung"), BERTA) == "Alter weicht stark ab"
    assert mismatch(P("o", "f", "alt"), BERTA) is None


def test_type_variant_for_a_plain_figure_is_flagged_as_mismatch():
    assert mismatch(P("o", "m"), RIESE) == "Typ-Variante für gewöhnliche Figur"
    assert mismatch(P("o", "m", type="riese"), RIESE) is None
    assert mismatch(P("o", "m"), CARL) is None


def test_assignment_is_deterministic():
    stats = [S("a", 5), S("b", 5), S("c", 5)]
    profiles = {s.name: P(s.name) for s in stats}
    assert assign(stats, profiles, ALL, {}) == assign(list(reversed(stats)), profiles, ALL, {})
