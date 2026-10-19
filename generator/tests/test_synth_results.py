from drova_voice.jsonl import append_jsonl, read_jsonl
from drova_voice.pipeline import record_synth_results


def _row(row_id="a", key="k", wav="a.wav", ok=True, attempts=1):
    return {"id": row_id, "key": key, "wav": wav, "ok": ok, "attempts": attempts}


def test_unchanged_cache_hits_are_not_appended(tmp_path):
    path = tmp_path / "results.jsonl"
    row = _row()
    record_synth_results(path, [row])
    before = path.read_bytes()
    record_synth_results(path, [_row(attempts=0), _row(attempts=0)])
    assert path.read_bytes() == before
    assert read_jsonl(path) == [row]


def test_a_bloated_file_shrinks_to_one_row_per_id(tmp_path):
    path = tmp_path / "results.jsonl"
    first, second = _row("a"), _row("b", key="k2", wav="b.wav")
    for _ in range(2):
        append_jsonl(path, first)
        append_jsonl(path, second)
    record_synth_results(path, [_row("a", attempts=0), _row("b", key="k2", wav="b.wav", attempts=0)])
    assert read_jsonl(path) == [first, second]


def test_a_changed_key_replaces_the_row(tmp_path):
    path = tmp_path / "results.jsonl"
    record_synth_results(path, [_row()])
    changed = _row(key="k2", wav="a2.wav", attempts=2)
    record_synth_results(path, [changed])
    assert read_jsonl(path) == [changed]


def test_an_empty_batch_leaves_the_file_alone(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text('{"id": "a"}\n', encoding="utf-8")
    before = path.read_bytes()
    record_synth_results(path, [])
    assert path.read_bytes() == before
