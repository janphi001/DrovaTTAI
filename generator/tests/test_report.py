from drova_voice.casting import Casting
from drova_voice.lines import Line
from drova_voice.report import (
    build_report,
    build_speaker_report,
    format_report,
    format_speaker_report,
)

CASTING = Casting("leon", {"mira": "lena"})


def line(key, actor="Mira", category="dialog", skip=None):
    return Line(
        id=f"T|P|{key}",
        tree="T",
        loca_path="P",
        loca_key=key,
        node_type="statement",
        choice_index=None,
        actor=actor,
        category=category,
        generic=False,
        raw="x",
        speech="" if skip else "x",
        stage=(),
        skip=skip,
    )


def test_statuses_follow_the_pipeline_order():
    lines = [
        line("Plh_1"),
        line("Plh_2"),
        line("Plh_3"),
        line("Plh_4"),
        line("Plh_5"),
        line("Plh_6", skip="gvar"),
        line("Plh_7", actor="Fremder"),
        line("Plh_8", actor="Player", category="player"),
    ]
    synth = {
        "T|P|Plh_1": {"ok": True, "flagged": False},
        "T|P|Plh_2": {"ok": True, "flagged": True},
        "T|P|Plh_3": {"ok": True, "flagged": False},
        "T|P|Plh_4": {"ok": False, "flagged": False},
    }
    encoded = {"T|P|Plh_1": {}, "T|P|Plh_2": {}}
    index = {"T|P|Plh_1": {}}
    report = build_report(lines, CASTING, synth, encoded, index)
    assert report["dialog"].counts == {
        "installiert": 1,
        "kodiert": 1,
        "erzeugt": 1,
        "fehler": 1,
        "offen": 1,
        "übersprungen: gvar": 1,
        "übersprungen: no_voice": 1,
    }
    assert report["dialog"].flagged == 1
    assert report["player"].counts == {"offen": 1}


def test_format_report_lists_categories_and_totals():
    text = format_report(
        build_report([line("Plh_1"), line("Plh_2", skip="gvar")], CASTING, {}, {}, {})
    )
    assert (
        "dialog" in text
        and "2 Zeilen" in text
        and "übersprungen: gvar: 1" in text
        and "offen: 1" in text
    )


def test_speaker_report_counts_per_speaker_and_lists_gaps():
    lines = [
        line("Plh_1"),
        line("Plh_2"),
        line("Plh_3", skip="gvar"),
        line("Plh_4", actor="Fremder"),
        line("Plh_5", actor="Player", category="player"),
        line("Plh_6", category="bark"),
    ]
    index = {"T|P|Plh_1": {}}
    report = build_speaker_report(lines, CASTING, {}, {}, index)
    assert report["Mira"] == {"installiert": 1, "offen": 1, "übersprungen: gvar": 1}
    assert report["Fremder"] == {"übersprungen: no_voice": 1}
    assert report["(Spieler)"] == {"offen": 1}
    assert "Plh_6" not in str(report) and len(report) == 3
    text = format_speaker_report(report, CASTING)
    assert "Mira (lena): 3 Zeilen" in text and "1 installiert" in text and "1 offen" in text
    assert "Lücken: 3 Zeilen bei 3 Sprechern" in text  # Fremder ohne Stimme zählt als Lücke


def test_skipped_line_does_not_count_a_stale_flagged_synth_row():
    lines = [line("Plh_1", skip="gvar_name")]
    synth = {"T|P|Plh_1": {"ok": True, "flagged": True}}
    report = build_report(lines, CASTING, synth, {}, {})
    assert report["dialog"].flagged == 0
    assert format_report(report) == "dialog: 1 Zeilen -> übersprungen: gvar_name: 1"


def test_speaker_without_a_voice_counts_as_a_gap_but_legit_skips_do_not():
    lines = [
        line("Plh_1", actor="Fremder"),
        line("Plh_2", actor="Fremder"),
        line("Plh_3", skip="gvar"),
        line("Plh_4", skip="unspeakable"),
        line("Plh_5", skip="id_mismatch"),
    ]
    index = {l.id: {} for l in lines if l.actor == "Mira" and not l.skip}
    text = format_speaker_report(build_speaker_report(lines, CASTING, {}, {}, index), CASTING)
    assert "Fremder (keine Stimme): 2 Zeilen -> 2 übersprungen: no_voice" in text
    assert "Lücken: 2 Zeilen bei 1 Sprechern" in text
