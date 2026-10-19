"""Worker-stdout: geteilte Mehrbyte-Zeichen werden nicht zu U+FFFD im JSON."""
import io

import drova_voice.engines.client as client_mod
from drova_voice.engines.client import EngineClient
from drova_voice.engines.protocol import SynthRequest


class _Chunks(io.RawIOBase):
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    def readable(self) -> bool:
        return True

    def readinto(self, buf) -> int:
        if not self._chunks:
            return 0
        part = self._chunks.pop(0)
        count = min(len(buf), len(part))
        buf[:count] = part[:count]
        if count < len(part):
            self._chunks.insert(0, part[count:])
        return count


class _Proc:
    def __init__(self, chunks: list[bytes]):
        self.stdout = _Chunks(chunks)
        self.stdin = io.BytesIO()
        self.stderr = None

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def kill(self):
        return None


def _open(monkeypatch, chunks: list[bytes]) -> tuple[_Proc, dict]:
    proc = _Proc(chunks)
    seen: dict = {}

    def popen(_cmd, **kwargs):
        seen.update(kwargs)
        return proc

    monkeypatch.setattr(client_mod.subprocess, "Popen", popen)
    return proc, seen


def _bytes(payload: bytes) -> list[bytes]:
    return [payload[i:i + 1] for i in range(len(payload))]


def test_split_multibyte_character_is_preserved_and_invalid_utf8_is_not_parsed(monkeypatch):
    euro = "€".encode("utf-8")
    ready = b'{"ready": true, "engine": "split", "model": "' + euro + b'"}\n'
    # Unvollständiges é vor dem Zeilenende: errors="replace" ergäbe gültiges JSON mit U+FFFD.
    bad = b'{"id": "s1", "ok": true, "error": "caf' + bytes([0xC3]) + b'"}\n'
    acute = "é".encode("utf-8")
    reply = b'{"id": "s1", "ok": false, "error": "' + acute + b'"}\n'
    proc, seen = _open(monkeypatch, _bytes(ready) + [bad] + _bytes(reply))
    with EngineClient(["unused"]) as client:
        assert (client.engine, client.model) == ("split", "€")
        assert "\ufffd" not in client.model
        resp = client.synth(SynthRequest(id="s1", text="Café.", out_path="out.wav"))
        sent = proc.stdin.getvalue()
    assert not resp.ok and resp.error == "é"
    assert "\ufffd" not in (resp.error or "")
    assert "Café.".encode("utf-8") in sent
    assert seen["bufsize"] == 0
    assert not seen.get("text")
    assert not seen.get("encoding")
    assert not seen.get("errors")
    assert not seen.get("universal_newlines")


def test_invalid_bytes_glued_to_the_ready_line_still_complete_the_handshake(monkeypatch, capsys):
    ready = b'{"ready": true, "engine": "glued", "model": "m"}\n'
    _proc, _seen = _open(monkeypatch, [b"\xff\xfe", ready])
    with EngineClient(["unused"]) as client:
        assert (client.engine, client.model) == ("glued", "m")
    err = capsys.readouterr().err
    assert "\\xff\\xfe" in err
    assert "\ufffd" not in err


def test_undecodable_noise_line_is_skipped_and_the_next_line_is_parsed(monkeypatch):
    ready = b'{"ready": true, "engine": "raw", "model": "stub"}\n'
    reply = b'{"id": "b1", "ok": true, "out_path": "x.wav", "sample_rate": 8000, "duration": 0.1}\n'
    _proc, _seen = _open(monkeypatch, [b"\xff\xfe noise\n", ready, reply])
    with EngineClient(["unused"]) as client:
        resp = client.synth(SynthRequest(id="b1", text="Ping.", out_path="x.wav"))
    assert (client.engine, client.model) == ("raw", "stub")
    assert resp.ok and resp.id == "b1"
    assert resp.error is None
