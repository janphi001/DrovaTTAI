from drova_voice.casting import Casting
from drova_voice.lines import Line
from drova_voice.report import build_report, format_report

CASTING = Casting("leon", {"mira": "lena"})


def line(key, actor="Mira", category="dialog", skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw="x", speech="" if skip else "x", stage=(), skip=skip)


def test_statuses_follow_the_pipeline_order():
    lines = [line("Plh_1"), line("Plh_2"), line("Plh_3"), line("Plh_4"), line("Plh_5"), line("Plh_6", skip="gvar"),
             line("Plh_7", actor="Fremder"), line("Plh_8", actor="Player", category="player")]
    synth = {"T|P|Plh_1": {"ok": True, "flagged": False}, "T|P|Plh_2": {"ok": True, "flagged": True},
             "T|P|Plh_3": {"ok": True, "flagged": False}, "T|P|Plh_4": {"ok": False, "flagged": False}}
    encoded = {"T|P|Plh_1": {}, "T|P|Plh_2": {}}
    index = {"T|P|Plh_1": {}}
    report = build_report(lines, CASTING, synth, encoded, index)
    assert report["dialog"].counts == {"installiert": 1, "kodiert": 1, "erzeugt": 1, "fehler": 1, "offen": 1,
                                       "übersprungen: gvar": 1, "übersprungen: no_voice": 1}
    assert report["dialog"].flagged == 1
    assert report["player"].counts == {"offen": 1}


def test_format_report_lists_categories_and_totals():
    text = format_report(build_report([line("Plh_1"), line("Plh_2", skip="gvar")], CASTING, {}, {}, {}))
    assert "dialog" in text and "2 Zeilen" in text and "übersprungen: gvar: 1" in text and "offen: 1" in text
