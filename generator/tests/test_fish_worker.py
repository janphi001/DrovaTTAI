import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from drova_voice.engines.client import EngineClient, EngineError, worker_command
from drova_voice.engines.protocol import SynthRequest

WORKERS = Path(__file__).resolve().parents[1] / "workers"
KEY = "sk-test-geheim-123"


def _wav_bytes(seconds: float = 0.5, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


class FakeFish:
    """Lokaler Server: spielt eine Liste von Antworten ab und merkt sich die Anfragen."""

    def __init__(self, responses):
        self.responses = list(responses)  # Einträge: (status, body_bytes) oder (status, body, {"Retry-After": "0"})
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                status, payload, *extra = outer.responses.pop(0) if outer.responses else (503, b"leer")
                self.send_response(status)
                for k, v in (extra[0] if extra else {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1/tts"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def _client(guarded, fake, **env):
    base = {"FISH_API_KEY": KEY, "FISH_API_URL": fake.url, "FISH_BACKOFF_S": "0.01", "FISH_MAX_ATTEMPTS": "3"}
    base.update(env)
    return guarded(lambda: EngineClient(worker_command(WORKERS, "fish"), env=base))


def _req(tmp_path, text="[sad] Hallo.", voice="abc123", **kw):
    return SynthRequest(id="t1", text=text, out_path=str(tmp_path / "a.wav"), voice=voice, **kw)


def test_success_writes_wav_and_sends_voice_text_and_headers(tmp_path, guarded):
    with FakeFish([(200, _wav_bytes(0.5))]) as fake:
        client = _client(guarded, fake, FISH_MODEL="s2.1-pro-free")
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert resp.ok and resp.sample_rate == 22050 and resp.duration == pytest.approx(0.5, abs=0.01)
    assert (tmp_path / "a.wav").stat().st_size > 44
    sent = fake.requests[0]
    # urllib schreibt Header-Namen groß ("Model"); HTTP-Header sind ohnehin nicht groß-/kleinschreibungsabhängig.
    assert sent["headers"]["authorization"] == f"Bearer {KEY}" and sent["headers"]["model"] == "s2.1-pro-free"
    assert sent["body"]["text"] == "[sad] Hallo." and sent["body"]["reference_id"] == "abc123" and sent["body"]["format"] == "wav"


def test_busy_server_is_retried_with_backoff_until_it_succeeds(tmp_path, guarded):
    with FakeFish([(429, b"zu viele", {"Retry-After": "0"}), (503, b"busy"), (200, _wav_bytes())]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert resp.ok and len(fake.requests) == 3


def test_gives_up_after_the_attempt_limit_with_a_german_error(tmp_path, guarded):
    with FakeFish([(503, b"busy")] * 5) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "nicht erreichbar" in resp.error and "503" in resp.error
    assert len(fake.requests) == 3
    assert not (tmp_path / "a.wav").exists()


@pytest.mark.parametrize("status", [401, 402, 400])
def test_client_errors_are_not_retried_and_never_leak_the_key(tmp_path, guarded, status):
    with FakeFish([(status, f"abgelehnt mit {KEY}".encode())] * 3) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and str(status) in resp.error
    assert KEY not in resp.error and len(fake.requests) == 1


def test_missing_key_reports_the_reason_at_startup(tmp_path, guarded):
    with FakeFish([]) as fake:
        with pytest.raises(EngineError, match="FISH_API_KEY"):
            _client(guarded, fake, FISH_API_KEY="")


def test_local_reference_wav_is_rejected_because_fish_uses_voice_ids(tmp_path, guarded):
    with FakeFish([(200, _wav_bytes())]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path, reference="ref.wav")))
        finally:
            client.close()
    assert not resp.ok and "reference_id" in resp.error and not fake.requests


def test_broken_audio_answer_is_an_error_not_a_success(tmp_path, guarded):
    with FakeFish([(200, b"das ist kein wav")]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok


def test_key_with_whitespace_or_control_chars_fails_at_startup_without_leaking(tmp_path, guarded):
    with FakeFish([]) as fake:
        with pytest.raises(EngineError, match="FISH_API_KEY") as info:
            _client(guarded, fake, FISH_API_KEY="sk-ab\ncd")
    text = str(info.value)
    assert "sk-ab" not in text and "cd" not in text


def test_unencodable_key_error_is_wrapped_and_does_not_leak(tmp_path, guarded):
    key = "sk-€geheim-123"  # invented; nicht latin-1, daher scheitert der Header-Aufbau in http.client
    with FakeFish([(200, _wav_bytes())]) as fake:
        client = _client(guarded, fake, FISH_API_KEY=key)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "Fish-Anfrage fehlgeschlagen" in resp.error
    assert "geheim" not in resp.error and "sk-" not in resp.error


def test_key_straddling_the_error_body_cut_is_masked_before_truncation(tmp_path, guarded):
    body = b"x" * 190 + KEY.encode() + b"tail"  # Schlüssel überschreitet die 200-Byte-Grenze
    with FakeFish([(400, body)]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "***" in resp.error
    assert KEY not in resp.error and "sk-test" not in resp.error and "geheim" not in resp.error
