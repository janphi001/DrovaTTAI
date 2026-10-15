from drova_voice.lines import Line
from drova_voice.selection import (Batch, batch_lines, plan_batches, read_batches, sample_lines, speaker_stats,
                                   write_batches)


def line(key, actor="Anna", speech="x" * 40, tree="T1", category="dialog", generic=False, skip=None):
    return Line(id=f"{tree}|P|{key}", tree=tree, loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=generic, raw=speech, speech="" if skip else speech, stage=(), skip=skip)


def test_speaker_stats_count_named_dialog_only_and_ignore_case():
    lines = [line("1", "Anna"), line("2", "ANNA", tree="T2"), line("3", "Bob"), line("4", "NPC", generic=True),
             line("5", "Cy", category="bark"), line("6", "Player", category="player"), line("7", "Dee", skip="gvar")]
    stats = speaker_stats(lines)
    assert [(s.name, s.display, s.lines, s.chars) for s in stats] == [("anna", "Anna", 2, 80), ("bob", "Bob", 1, 40)]
    assert stats[0].trees == frozenset({"T1", "T2"})


def test_sample_lines_pick_one_per_speaker_closest_to_80_characters():
    lines = [line("1", "Anna", "k" * 10), line("2", "Anna", "m" * 75), line("3", "Anna", "l" * 200),
             line("4", "Bob", "b" * 30), line("5", "NPC", generic=True)]
    assert [l.id for l in sample_lines(lines)] == ["T1|P|2", "T1|P|4"]


def test_plan_batches_pack_by_characters_and_put_the_player_in_the_last_one():
    lines = ([line(f"a{i}", "Anna") for i in range(3)] + [line(f"b{i}", "Bob") for i in range(2)] + [line("c", "Cy")]
             + [line("p", "Player", category="player")])
    batches = plan_batches(lines, max_chars=150)
    assert [(b.n, b.speakers, b.lines, b.chars, b.player) for b in batches] == [
        (1, ("anna",), 3, 120, False), (2, ("bob", "cy"), 3 + 1, 120 + 40, True)]


def test_plan_batches_without_lines_is_empty():
    assert plan_batches([]) == []


def test_batch_lines_select_the_speakers_lines_and_the_player_only_when_marked():
    lines = [line("1", "Anna"), line("2", "Bob"), line("3", "NPC", generic=True), line("4", "Player", category="player")]
    assert [l.id for l in batch_lines(lines, Batch(1, ("anna",), 1, 40, False))] == ["T1|P|1"]
    assert [l.id for l in batch_lines(lines, Batch(2, ("bob",), 1, 40, True))] == ["T1|P|2", "T1|P|4"]


def test_batches_roundtrip(tmp_path):
    batches = [Batch(1, ("anna", "bob"), 5, 200, False), Batch(2, ("cy",), 1, 40, True)]
    write_batches(tmp_path / "data" / "batches.json", batches, 150)
    assert read_batches(tmp_path / "data" / "batches.json") == batches
