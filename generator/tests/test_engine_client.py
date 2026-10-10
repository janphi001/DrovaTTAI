import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest

import drova_voice.engines.client as client_mod
from drova_voice.engines.client import EngineClient, EngineError, worker_command
from drova_voice.engines.protocol import SynthRequest

WORKERS = Path(__file__).resolve().parents[1] / "workers"
COMMON = WORKERS / "_common"
FAKE = [sys.executable, str(WORKERS / "fake" / "worker.py")]


def test_handshake_and_synth(tmp_path, guarded):
    out = tmp_path / "a.wav"
    with guarded(lambda: EngineClient(FAKE)) as client:
        assert (client.engine, client.model) == ("fake", "sine-1")
        resp = guarded(lambda: client.synth(SynthRequest(id="1", text="Grüß dich, Wanderer.", out_path=str(out))))
    assert resp.ok and resp.id == "1"
    assert resp.duration == pytest.approx(1.0, abs=0.01)
    with wave.open(str(out)) as w:
        assert w.getframerate() == 22050


def test_failure_is_reported_and_worker_survives(tmp_path, guarded):
    with guarded(lambda: EngineClient(FAKE)) as client:
        bad = guarded(lambda: client.synth(SynthRequest(id="x", text="FAIL", out_path=str(tmp_path / "x.wav"))))
        good = guarded(lambda: client.synth(SynthRequest(id="y", text="Hallo", out_path=str(tmp_path / "y.wav"))))
    assert not bad.ok and "absichtlicher Fehler" in bad.error
    assert good.ok


def test_dead_worker_raises(guarded):
    with pytest.raises(EngineError):
        guarded(lambda: EngineClient([sys.executable, "-c", "import sys; sys.exit(3)"]))


def test_worker_command_for_stdlib_worker_uses_current_python():
    assert worker_command(WORKERS, "fake") == [sys.executable, str(WORKERS / "fake" / "worker.py")]


def test_worker_command_unknown_engine():
    with pytest.raises(EngineError, match="Unbekannte Engine"):
        worker_command(WORKERS, "nope")


def test_worker_command_missing_venv(tmp_path):
    wdir = tmp_path / "heavy"
    wdir.mkdir()
    (wdir / "worker.py").write_text("")
    (wdir / "requirements.txt").write_text("torch\n")
    with pytest.raises(EngineError, match="venv"):
        worker_command(tmp_path, "heavy")


# --- Lärmende Worker: Protokoll muss trotz Ausgaben auf stdout (auch nativ/C-Ebene) funktionieren ---

def _stub(tmp_path, body: str) -> list[str]:
    path = tmp_path / "stub_worker.py"
    path.write_text(body, encoding="utf-8")
    return [sys.executable, str(path)]


def _serve_header() -> str:
    return f"import os, sys\nsys.path.insert(0, {str(COMMON)!r})\nfrom worker_loop import serve\n"


NATIVE_NOISY_BODY = '''
def load():
    os.write(1, b"native noise before ready\\n")
    return None

def synth(_state, req):
    os.write(1, b"native noise during synth\\n")
    os.write(1, b"{broken json\\n")
    os.write(1, b'{"progress": 0.5}\\n')
    with open(req["out_path"], "wb") as f:
        f.write(b"RIFF")
    return 22050, 0.1

serve("noisy", "stub-1", load, synth)
'''


UTF8_ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


def _assert_protocol_only(stdout: str) -> None:
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert lines, "kein Protokoll auf stdout"
    for line in lines:
        obj = json.loads(line)  # jede Zeile muss gültiges JSON sein
        assert isinstance(obj, dict) and ("ready" in obj or "ok" in obj), line


def test_native_stdout_noise_does_not_break_handshake_or_synth(tmp_path, guarded):
    with guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + NATIVE_NOISY_BODY))) as client:
        assert (client.engine, client.model) == ("noisy", "stub-1")
        for i, text in enumerate(["Silberne Fuchsbrücke", "Leiser Wind", "Dritter Satz"]):
            out = str(tmp_path / f"n{i}.wav")
            resp = guarded(lambda: client.synth(SynthRequest(id=f"n{i}", text=text, out_path=out)))
            assert resp.ok and resp.id == f"n{i}"
            assert resp.out_path == out and resp.sample_rate == 22050
            assert resp.duration == pytest.approx(0.1)


def test_worker_stdout_carries_only_protocol_lines_with_native_noise(tmp_path, guarded):
    req = SynthRequest(id="r1", text="Stiller Teich", out_path=str(tmp_path / "r1.wav"))
    proc = guarded(lambda: subprocess.run(
        _stub(tmp_path, _serve_header() + NATIVE_NOISY_BODY),
        input=req.to_json() + "\n", capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=UTF8_ENV,
    ))
    assert proc.returncode == 0
    _assert_protocol_only(proc.stdout)


def test_fake_worker_stdout_carries_only_protocol_lines(tmp_path, guarded):
    req = SynthRequest(id="p1", text="Stille Fuchsbrücke", out_path=str(tmp_path / "p1.wav"))
    proc = guarded(lambda: subprocess.run(
        FAKE, input=req.to_json() + "\n", capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=UTF8_ENV,
    ))
    assert proc.returncode == 0
    _assert_protocol_only(proc.stdout)
    assert "fake: lade Modell" in proc.stderr  # der Lärm ist da, landet aber auf stderr


RAW_STUB = '''
import json, os, sys

def out(s):
    os.write(1, (s + "\\n").encode("utf-8"))

out('{"progress": 0.5}')
out('{broken json')
out(json.dumps({"ready": True, "engine": "raw", "model": "stub-raw"}))
for line in sys.stdin:
    req = json.loads(line)
    out('{"progress": 1.0}')
    out(json.dumps({"id": req["id"], "ok": True, "out_path": req["out_path"],
                    "sample_rate": 22050, "duration": 0.1}))
'''


def test_client_skips_json_without_protocol_keys(tmp_path, guarded):
    with guarded(lambda: EngineClient(_stub(tmp_path, RAW_STUB))) as client:
        assert (client.engine, client.model) == ("raw", "stub-raw")
        resp = guarded(lambda: client.synth(SynthRequest(id="k1", text="Kiesweg am Bach", out_path=str(tmp_path / "k1.wav"))))
    assert resp.ok and resp.id == "k1"


def test_client_tolerates_undecodable_stdout_bytes(tmp_path, guarded):
    body = 'import os\nos.write(1, b"\\xff\\xfe noise\\n")\n' + RAW_STUB
    with guarded(lambda: EngineClient(_stub(tmp_path, body))) as client:
        resp = guarded(lambda: client.synth(SynthRequest(id="b1", text="Roter Mohn", out_path=str(tmp_path / "b1.wav"))))
    assert resp.ok and resp.id == "b1"


DIES_AFTER_READY = '''
import json, os
os.write(1, (json.dumps({"ready": True, "engine": "dying", "model": "stub-dead"}) + "\\n").encode("utf-8"))
'''


def test_synth_after_worker_died_raises_engine_error(tmp_path, guarded):
    client = guarded(lambda: EngineClient(_stub(tmp_path, DIES_AFTER_READY)))
    try:
        client._proc.wait(timeout=30)  # Worker ist beendet, bevor die Anfrage kommt
        with pytest.raises(EngineError):
            guarded(lambda: client.synth(SynthRequest(id="d1", text="Kurzer Satz", out_path=str(tmp_path / "d1.wav"))))
    finally:
        client.close()


FLOOD_STUB = '''
import sys
for i in range(LIMIT):
    sys.stdout.write("flood " + str(i) + "\\n")
sys.stdout.flush()
for _ in sys.stdin:
    pass
'''


def test_failed_handshake_kills_worker(tmp_path, workers, guarded):
    body = FLOOD_STUB.replace("LIMIT", str(client_mod._MAX_NOISE_LINES + 1))
    with pytest.raises(EngineError, match="kein gültiges Protokoll"):
        guarded(lambda: EngineClient(_stub(tmp_path, body)))
    assert workers and workers[0].poll() is not None


# --- W3: Fremdtext ohne Zeilenende direkt vor der Ready-Zeile darf den Handshake nicht blockieren ---

SERVE_BODY_WITHOUT_EOL = '''
def load():
    return None

def synth(_state, req):
    with open(req["out_path"], "wb") as f:
        f.write(b"RIFF")
    return 22050, 0.1

serve("eolless", "stub-eol", load, synth)
'''

RAW_GLUED_READY_STUB = '''
import json, os, sys

os.write(1, b"loading..." + json.dumps({"ready": True, "engine": "glued", "model": "stub-glued"}).encode("utf-8") + b"\\n")
for line in sys.stdin:
    req = json.loads(line)
    with open(req["out_path"], "wb") as f:
        f.write(b"RIFF")
    os.write(1, (json.dumps({"id": req["id"], "ok": True, "out_path": req["out_path"],
                             "sample_rate": 22050, "duration": 0.1}) + "\\n").encode("utf-8"))
'''


def test_noise_without_newline_before_serve_does_not_block_handshake(tmp_path, guarded, capsys):
    cmd = _stub(tmp_path, _serve_header() + 'os.write(1, b"loading...")\n' + SERVE_BODY_WITHOUT_EOL)
    client = guarded(lambda: EngineClient(cmd))
    try:
        assert (client.engine, client.model) == ("eolless", "stub-eol")
        out = str(tmp_path / "e1.wav")
        resp = guarded(lambda: client.synth(SynthRequest(id="e1", text="Stiller Bach", out_path=out)))
    finally:
        client.close()
    assert resp.ok and resp.id == "e1"
    assert "loading..." in capsys.readouterr().err


def test_ready_line_glued_to_foreign_text_is_found_without_serve(tmp_path, guarded, capsys):
    cmd = _stub(tmp_path, RAW_GLUED_READY_STUB)
    client = guarded(lambda: EngineClient(cmd))
    try:
        assert (client.engine, client.model) == ("glued", "stub-glued")
        resp = guarded(lambda: client.synth(SynthRequest(id="g1", text="Kalter Wind", out_path=str(tmp_path / "g1.wav"))))
    finally:
        client.close()
    assert resp.ok and resp.id == "g1"
    assert "loading..." in capsys.readouterr().err


# --- G2: close() schließt Pipes immer, auch bei bereits beendetem oder hängendem Worker ---

def test_close_releases_pipes_of_crashed_worker(tmp_path, guarded):
    client = guarded(lambda: EngineClient(_stub(tmp_path, DIES_AFTER_READY)))
    client._proc.wait(timeout=30)  # Worker ist schon beendet
    client.close()
    assert client._proc.stdin.closed and client._proc.stdout.closed


def test_close_is_idempotent_and_releases_pipes_of_live_worker(guarded):
    client = guarded(lambda: EngineClient(FAKE))
    client.close()
    client.close()
    assert client._proc.stdin.closed and client._proc.stdout.closed
    assert client._proc.returncode == 0


STUCK_AFTER_READY = '''
import json, os, time
os.write(1, (json.dumps({"ready": True, "engine": "stuck", "model": "stub-stuck"}) + "\\n").encode("utf-8"))
time.sleep(600)  # ignoriert das Dateiende auf stdin
'''


def test_close_kills_worker_that_ignores_end_of_input(tmp_path, guarded, monkeypatch):
    monkeypatch.setattr(client_mod, "_CLOSE_TIMEOUT_S", 1)
    client = guarded(lambda: EngineClient(_stub(tmp_path, STUCK_AFTER_READY)))
    client.close()
    assert client._proc.poll() is not None
    assert client._proc.stdin.closed and client._proc.stdout.closed


# --- G3: ok nur mit geschriebener, nicht leerer Audiodatei ---

SYNTH_WRITES_NOTHING = '''
def load():
    return None

def synth(_state, req):
    return 22050, 0.1

serve("silent", "stub-silent", load, synth)
'''

SYNTH_WRITES_EMPTY_FILE = '''
def load():
    return None

def synth(_state, req):
    open(req["out_path"], "wb").close()
    return 22050, 0.1

serve("hollow", "stub-hollow", load, synth)
'''


@pytest.mark.parametrize("body", [SYNTH_WRITES_NOTHING, SYNTH_WRITES_EMPTY_FILE], ids=["keine-datei", "leere-datei"])
def test_ok_requires_a_non_empty_audio_file(tmp_path, guarded, body):
    client = guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + body)))
    out = str(tmp_path / "leer.wav")
    try:
        resp = guarded(lambda: client.synth(SynthRequest(id="s1", text="Kalte Luft", out_path=out)))
    finally:
        client.close()
    assert not resp.ok and resp.id == "s1"
    assert resp.error == f"Keine Audiodatei geschrieben: {out}"


# --- G4: Anfragen, die kein JSON-Objekt sind, beenden die Schleife nicht ---

def test_non_object_requests_are_rejected_and_loop_continues(tmp_path, guarded):
    lines = "\n".join([
        "[1, 2]",
        "5",
        '"x"',
        SynthRequest(id="n1", text="Leiser Regen", out_path=str(tmp_path / "n1.wav")).to_json(),
    ]) + "\n"
    proc = guarded(lambda: subprocess.run(
        FAKE, input=lines, capture_output=True, text=True, encoding="utf-8", env=UTF8_ENV,
    ))
    assert proc.returncode == 0
    replies = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()][1:]  # erste Zeile: Ready
    assert replies[:3] == [{"id": None, "ok": False, "error": "Anfrage ist kein JSON-Objekt"}] * 3
    assert replies[3]["id"] == "n1" and replies[3]["ok"] is True


# --- Veraltete Ausgabedatei (z. B. aus einem abgebrochenen Lauf) darf kein ok vortäuschen ---

def test_stale_output_file_is_removed_before_synth(tmp_path, guarded):
    out = tmp_path / "alt.part.wav"
    out.write_bytes(b"alte Bytes")
    client = guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + SYNTH_WRITES_NOTHING)))
    try:
        resp = guarded(lambda: client.synth(SynthRequest(id="a1", text="Alter Rest", out_path=str(out))))
    finally:
        client.close()
    assert not resp.ok and resp.id == "a1"
    assert resp.error == f"Keine Audiodatei geschrieben: {out}"
    assert not out.exists()


def test_stale_output_that_cannot_be_removed_is_reported_without_synth(tmp_path, guarded):
    out = tmp_path / "gesperrt.part.wav"
    out.mkdir()  # ein Verzeichnis lässt sich nicht als Datei entfernen
    (out / "inhalt.txt").write_bytes(b"x")
    client = guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + SYNTH_WRITES_NOTHING)))
    try:
        resp = guarded(lambda: client.synth(SynthRequest(id="a2", text="Gesperrt", out_path=str(out))))
    finally:
        client.close()
    assert not resp.ok and resp.id == "a2"
    assert "konnte nicht entfernt werden" in resp.error
    assert out.is_dir()


# --- Lärm, der selbst mit "{" beginnt, vor der Ready-Zeile auf derselben Zeile ---

PREFIXED_READY_STUB = '''
import json, os, sys
ready = json.dumps({"ready": True, "engine": "braced", "model": "stub-braced"})
os.write(1, ("{noise " + ready + "\\n").encode("utf-8"))
for line in sys.stdin:
    req = json.loads(line)
    with open(req["out_path"], "wb") as f:
        f.write(b"RIFF")
    os.write(1, (json.dumps({"id": req["id"], "ok": True, "out_path": req["out_path"],
                             "sample_rate": 22050, "duration": 0.1}) + "\\n").encode("utf-8"))
'''


def test_ready_line_after_brace_noise_on_same_line_completes_handshake(tmp_path, guarded, capsys):
    client = guarded(lambda: EngineClient(_stub(tmp_path, PREFIXED_READY_STUB)))
    try:
        assert (client.engine, client.model) == ("braced", "stub-braced")
        resp = guarded(lambda: client.synth(SynthRequest(id="c1", text="Brauner Krug", out_path=str(tmp_path / "c1.wav"))))
    finally:
        client.close()
    assert resp.ok and resp.id == "c1"
    err = capsys.readouterr().err
    assert err.count("{noise") == 1  # der Präfix wird genau einmal weitergeleitet


# --- Opus-Review Task 12: Ladefehler sichtbar machen, leeres Audio nicht als Erfolg melden ---

LOAD_FAILS = '''
def load():
    raise RuntimeError("CPML nicht bestätigt")

def synth(_state, req):
    return 22050, 0.1

serve("broken", "stub-broken", load, synth)
'''

SYNTH_WRITES_HEADER_ONLY = '''
def load():
    return None

def synth(_state, req):
    with open(req["out_path"], "wb") as f:
        f.write(b"RIFF" + bytes(40))
    return 22050, 0.0

serve("hollow", "stub-header-only", load, synth)
'''


def test_load_failure_reaches_the_client_with_its_reason(tmp_path, guarded):
    with pytest.raises(EngineError, match="RuntimeError: CPML nicht bestätigt"):
        guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + LOAD_FAILS)))


def test_zero_duration_audio_is_not_reported_as_success(tmp_path, guarded):
    client = guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + SYNTH_WRITES_HEADER_ONLY)))
    out = str(tmp_path / "stumm.wav")
    try:
        resp = guarded(lambda: client.synth(SynthRequest(id="s1", text="Kalte Luft", out_path=out)))
    finally:
        client.close()
    assert not resp.ok and resp.id == "s1"
    assert resp.error == f"Leeres Audio (Dauer 0): {out}"


# --- Opus-Review Task 12: Modell-Caches gehören aufs Projektlaufwerk, nicht nach C: ---

def test_cache_env_points_model_caches_into_the_project_cache(tmp_path):
    env = client_mod.cache_env(tmp_path / "cache", base={})
    assert env == {"HF_HOME": str(tmp_path / "cache" / "hf"), "TTS_HOME": str(tmp_path / "cache" / "tts"),
                   "PKUSEG_HOME": str(tmp_path / "cache" / "pkuseg")}


def test_cache_env_does_not_override_values_the_user_already_set(tmp_path):
    env = client_mod.cache_env(tmp_path / "cache", base={"HF_HOME": "E:/mein-hf"})
    assert "HF_HOME" not in env and "TTS_HOME" in env


ECHO_ENV = '''
def load():
    return None

def synth(_state, req):
    with open(req["out_path"], "wb") as f:
        f.write(os.environ.get("HF_HOME", "ungesetzt").encode() + bytes(60))
    return 22050, 0.1

serve("env", "stub-env", load, synth)
'''


def test_client_passes_extra_env_to_the_worker(tmp_path, guarded):
    client = guarded(lambda: EngineClient(_stub(tmp_path, _serve_header() + ECHO_ENV), env={"HF_HOME": "D:/cache/hf"}))
    out = tmp_path / "e.wav"
    try:
        resp = guarded(lambda: client.synth(SynthRequest(id="e1", text="Kalte Luft", out_path=str(out))))
    finally:
        client.close()
    assert resp.ok and out.read_bytes().startswith(b"D:/cache/hf")
