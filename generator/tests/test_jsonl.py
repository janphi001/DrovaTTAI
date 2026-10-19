import os

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
    path.write_bytes(b"\xef\xbb\xbf" + '{"a": "Grüße"}\n{"a": 2}\n'.encode())
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


def test_write_retries_when_another_program_briefly_holds_the_target_open(tmp_path, monkeypatch):
    import os

    import drova_voice.jsonl as jsonl_mod

    real_replace, failures = os.replace, []

    def flaky_replace(src, dst):
        if len(failures) < 2:
            failures.append(1)
            raise PermissionError(5, "Zugriff verweigert")
        real_replace(src, dst)

    monkeypatch.setattr(jsonl_mod.os, "replace", flaky_replace)
    monkeypatch.setattr(jsonl_mod.time, "sleep", lambda _s: None)
    path = tmp_path / "r.jsonl"
    write_jsonl(path, [{"a": 1}])
    assert len(failures) == 2 and read_jsonl(path) == [{"a": 1}]


def test_write_gives_up_after_the_retries_and_keeps_the_old_file(tmp_path, monkeypatch):
    import drova_voice.jsonl as jsonl_mod

    path = tmp_path / "r.jsonl"
    write_jsonl(path, [{"alt": True}])

    def locked(src, dst):
        raise PermissionError(5, "Zugriff verweigert")

    monkeypatch.setattr(jsonl_mod.os, "replace", locked)
    monkeypatch.setattr(jsonl_mod.time, "sleep", lambda _s: None)
    with pytest.raises(PermissionError):
        write_jsonl(path, [{"neu": True}])
    assert read_jsonl(path) == [{"alt": True}] and not list(tmp_path.glob("*.tmp"))


def test_write_fsyncs_the_temp_file_before_replacing(tmp_path, monkeypatch):
    import drova_voice.jsonl as jsonl_mod

    order = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(fd):
        order.append("fsync")
        return real_fsync(fd)

    def replace(src, dst):
        order.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(jsonl_mod.os, "fsync", fsync)
    monkeypatch.setattr(jsonl_mod.os, "replace", replace)
    path = tmp_path / "r.jsonl"
    write_jsonl(path, [{"a": "Grüße"}])
    assert order == ["fsync", "replace"]
    assert read_jsonl(path) == [{"a": "Grüße"}]


def test_fsync_failure_keeps_the_old_file_and_removes_the_temp_file(tmp_path, monkeypatch):
    import drova_voice.jsonl as jsonl_mod

    path = tmp_path / "r.jsonl"
    write_jsonl(path, [{"alt": True}])

    def fail(_fd):
        raise OSError("Platte voll")

    monkeypatch.setattr(jsonl_mod.os, "fsync", fail)
    with pytest.raises(OSError, match="Platte voll"):
        write_jsonl(path, [{"neu": True}])
    assert read_jsonl(path) == [{"alt": True}] and not list(tmp_path.glob("*.tmp"))
