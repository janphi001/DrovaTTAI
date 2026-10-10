from drova_voice.jsonl import read_jsonl, write_jsonl


def test_roundtrip_keeps_unicode_line_separators_inside_rows(tmp_path):
    rows = [
        {"a": "x y", "b": "x y", "c": "x\u0085y"},
        {"text": "Grüße, Ärger & Öl ß"},
    ]
    path = tmp_path / "rows.jsonl"
    write_jsonl(path, rows)
    assert read_jsonl(path) == rows


def test_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"a": 1}\n\n   \n{"a": 2}\n', encoding="utf-8")
    assert read_jsonl(path) == [{"a": 1}, {"a": 2}]
