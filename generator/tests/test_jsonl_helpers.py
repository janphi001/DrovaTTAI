from drova_voice.jsonl import append_jsonl, latest_by_id, read_jsonl_lenient


def test_append_and_read(tmp_path):
    path = tmp_path / "sub" / "r.jsonl"
    append_jsonl(path, {"id": "a", "v": 1})
    append_jsonl(path, {"id": "b", "v": "Bär"})
    assert read_jsonl_lenient(path) == [{"id": "a", "v": 1}, {"id": "b", "v": "Bär"}]


def test_lenient_skips_truncated_last_line_and_missing_file(tmp_path):
    assert read_jsonl_lenient(tmp_path / "gibt-es-nicht.jsonl") == []
    path = tmp_path / "r.jsonl"
    path.write_text(
        '{"id": "a"}\n{"id": "b", "v": [1, 2', encoding="utf-8"
    )  # Abbruch beim Schreiben
    assert read_jsonl_lenient(path) == [{"id": "a"}]


def test_latest_by_id_last_row_wins():
    rows = [{"id": "a", "n": 1}, {"id": "b", "n": 1}, {"id": "a", "n": 2}]
    assert latest_by_id(rows) == {"a": {"id": "a", "n": 2}, "b": {"id": "b", "n": 1}}


def test_lenient_skips_line_cut_inside_a_multibyte_character(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_bytes(b'{"id": "a"}\n{"id": "b", "v": "kein Worker verf' + "ü".encode()[:1])
    assert read_jsonl_lenient(path) == [{"id": "a"}]


def test_append_after_a_truncated_line_keeps_the_new_rows(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text('{"id": "a"}\n{"id": "b", "v": [1', encoding="utf-8")
    append_jsonl(path, {"id": "c"})
    append_jsonl(path, {"id": "d"})
    assert [r["id"] for r in read_jsonl_lenient(path)] == ["a", "c", "d"]
