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
                headers = dict(extra[0]) if extra else {}
                headers.setdefault("Content-Length", str(len(payload)))  # eigener Wert erlaubt: kurzer Body
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
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
    # Angepasst: Nicht-ASCII-Schlüssel scheitern jetzt schon beim Start (vorher erst beim Header-Aufbau in http.client).
    key = "sk-€geheim-123"  # invented
    with FakeFish([]) as fake:
        with pytest.raises(EngineError, match="nur ASCII erlaubt") as info:
            _client(guarded, fake, FISH_API_KEY=key)
    text = str(info.value)
    assert "geheim" not in text and "sk-" not in text and not fake.requests


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


@pytest.mark.parametrize("retry_after", ["-5", "bald", "nan"])
def test_odd_retry_after_values_do_not_break_the_retry(tmp_path, guarded, retry_after):
    # Negativ wird zu 0 geklemmt, nicht-numerisch fällt auf den Backoff zurück; beides darf die Wiederholung nicht abbrechen.
    with FakeFish([(429, b"zu viele", {"Retry-After": retry_after}), (200, _wav_bytes())]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert resp.ok and len(fake.requests) == 2


def test_truncated_body_is_retried_like_a_connection_error(tmp_path, guarded):
    full = _wav_bytes()
    # Content-Length größer als der Body: der Server schließt früh, http.client meldet IncompleteRead.
    with FakeFish([(200, full[:30], {"Content-Length": str(len(full))}), (200, full)]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert resp.ok and len(fake.requests) == 2 and (tmp_path / "a.wav").stat().st_size == len(full)


def test_truncated_body_on_every_attempt_gives_up_with_the_exception_name(tmp_path, guarded):
    full = _wav_bytes()
    short = (200, full[:30], {"Content-Length": str(len(full))})
    with FakeFish([short] * 3) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "nicht erreichbar nach 3 Versuchen" in resp.error
    assert "(zuletzt IncompleteRead)" in resp.error and len(fake.requests) == 3


def test_redirect_is_reported_and_not_followed_so_the_key_is_not_forwarded(tmp_path, guarded):
    # Die zweite Antwort wäre ein Erfolg: würde umgeleitet, gäbe es zwei Anfragen statt einer.
    with FakeFish([(302, b"", {"Location": "/v1/tts-umgeleitet"}), (200, _wav_bytes())]) as fake:
        client = _client(guarded, fake)
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "Fish leitet um (HTTP 302); nicht gefolgt" in resp.error
    assert KEY not in resp.error and len(fake.requests) == 1


def test_zero_max_attempts_is_clamped_to_one_attempt(tmp_path, guarded):
    with FakeFish([(503, b"busy")] * 3) as fake:
        client = _client(guarded, fake, FISH_MAX_ATTEMPTS="0")
        try:
            resp = guarded(lambda: client.synth(_req(tmp_path)))
        finally:
            client.close()
    assert not resp.ok and "nach 1 Versuchen" in resp.error and len(fake.requests) == 1


@pytest.mark.parametrize("name, value", [("FISH_MAX_ATTEMPTS", "drei"), ("FISH_BACKOFF_S", "schnell"),
                                         ("FISH_BACKOFF_S", "nan"), ("FISH_BACKOFF_S", "-1")])
def test_invalid_numbers_fail_at_startup_naming_the_variable(tmp_path, guarded, name, value):
    with FakeFish([]) as fake:
        with pytest.raises(EngineError, match=name) as info:
            _client(guarded, fake, **{name: value})
    assert KEY not in str(info.value) and not fake.requests
