import pytest

from drova_voice.jsonl import read_jsonl, write_jsonl


def test_roundtrip_keeps_unicode_line_separators_inside_rows(tmp_path):
    rows = [
        {"a": "x\u2028y", "b": "x\u2029y", "c": "x\u0085y"},
        {"text": "Grüße, Ärger & Öl ß"},
    ]
    path = tmp_path / "rows.jsonl"
    write_jsonl(path, rows)
    assert read_jsonl(path) == rows


def test_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"a": 1}\n\n   \n{"a": 2}\n', encoding="utf-8")
    assert read_jsonl(path) == [{"a": 1}, {"a": 2}]


def test_read_tolerates_utf8_bom(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_bytes(b"\xef\xbb\xbf" + '{"a": "Grüße"}\n{"a": 2}\n'.encode("utf-8"))
    assert read_jsonl(path) == [{"a": "Grüße"}, {"a": 2}]


def test_failed_write_keeps_old_file_and_leaves_no_tmp(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"alt": true}\n', encoding="utf-8")

    def broken_rows():
        yield {"neu": 1}
        raise RuntimeError("kaputt")

    with pytest.raises(RuntimeError):
        write_jsonl(path, broken_rows())
    assert path.read_text(encoding="utf-8") == '{"alt": true}\n'
    assert not path.with_name(path.name + ".tmp").exists()
