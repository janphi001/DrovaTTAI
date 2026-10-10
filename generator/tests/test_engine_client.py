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


def test_handshake_and_synth(tmp_path):
    out = tmp_path / "a.wav"
    with EngineClient(FAKE) as client:
        assert (client.engine, client.model) == ("fake", "sine-1")
        resp = client.synth(SynthRequest(id="1", text="Grüß dich, Wanderer.", out_path=str(out)))
    assert resp.ok and resp.id == "1"
    assert resp.duration == pytest.approx(1.0, abs=0.01)
    with wave.open(str(out)) as w:
        assert w.getframerate() == 22050


def test_failure_is_reported_and_worker_survives(tmp_path):
    with EngineClient(FAKE) as client:
        bad = client.synth(SynthRequest(id="x", text="FAIL", out_path=str(tmp_path / "x.wav")))
        good = client.synth(SynthRequest(id="y", text="Hallo", out_path=str(tmp_path / "y.wav")))
    assert not bad.ok and "absichtlicher Fehler" in bad.error
    assert good.ok


def test_dead_worker_raises():
    with pytest.raises(EngineError):
        EngineClient([sys.executable, "-c", "import sys; sys.exit(3)"])


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


def test_native_stdout_noise_does_not_break_handshake_or_synth(tmp_path):
    with EngineClient(_stub(tmp_path, _serve_header() + NATIVE_NOISY_BODY)) as client:
        assert (client.engine, client.model) == ("noisy", "stub-1")
        for i, text in enumerate(["Silberne Fuchsbrücke", "Leiser Wind", "Dritter Satz"]):
            out = str(tmp_path / f"n{i}.wav")
            resp = client.synth(SynthRequest(id=f"n{i}", text=text, out_path=out))
            assert resp.ok and resp.id == f"n{i}"
            assert resp.out_path == out and resp.sample_rate == 22050
            assert resp.duration == pytest.approx(0.1)


def test_worker_stdout_carries_only_protocol_lines_with_native_noise(tmp_path):
    req = SynthRequest(id="r1", text="Stiller Teich", out_path=str(tmp_path / "r1.wav"))
    proc = subprocess.run(
        _stub(tmp_path, _serve_header() + NATIVE_NOISY_BODY),
        input=req.to_json() + "\n", capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=UTF8_ENV,
    )
    assert proc.returncode == 0
    _assert_protocol_only(proc.stdout)


def test_fake_worker_stdout_carries_only_protocol_lines(tmp_path):
    req = SynthRequest(id="p1", text="Stille Fuchsbrücke", out_path=str(tmp_path / "p1.wav"))
    proc = subprocess.run(
        FAKE, input=req.to_json() + "\n", capture_output=True, text=True, encoding="utf-8", timeout=30,
        env=UTF8_ENV,
    )
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


def test_client_skips_json_without_protocol_keys(tmp_path):
    with EngineClient(_stub(tmp_path, RAW_STUB)) as client:
        assert (client.engine, client.model) == ("raw", "stub-raw")
        resp = client.synth(SynthRequest(id="k1", text="Kiesweg am Bach", out_path=str(tmp_path / "k1.wav")))
    assert resp.ok and resp.id == "k1"


def test_client_tolerates_undecodable_stdout_bytes(tmp_path):
    body = 'import os\nos.write(1, b"\\xff\\xfe noise\\n")\n' + RAW_STUB
    with EngineClient(_stub(tmp_path, body)) as client:
        resp = client.synth(SynthRequest(id="b1", text="Roter Mohn", out_path=str(tmp_path / "b1.wav")))
    assert resp.ok and resp.id == "b1"


DIES_AFTER_READY = '''
import json, os
os.write(1, (json.dumps({"ready": True, "engine": "dying", "model": "stub-dead"}) + "\\n").encode("utf-8"))
'''


def test_synth_after_worker_died_raises_engine_error(tmp_path):
    client = EngineClient(_stub(tmp_path, DIES_AFTER_READY))
    try:
        client._proc.wait(timeout=30)  # Worker ist beendet, bevor die Anfrage kommt
        with pytest.raises(EngineError):
            client.synth(SynthRequest(id="d1", text="Kurzer Satz", out_path=str(tmp_path / "d1.wav")))
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


def test_failed_handshake_kills_worker(tmp_path, monkeypatch):
    started = []
    real_popen = subprocess.Popen

    def capturing_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr(client_mod.subprocess, "Popen", capturing_popen)
    body = FLOOD_STUB.replace("LIMIT", str(client_mod._MAX_NOISE_LINES + 1))
    try:
        with pytest.raises(EngineError, match="kein gültiges Protokoll"):
            EngineClient(_stub(tmp_path, body))
        assert started and started[0].poll() is not None
    finally:
        for proc in started:
            if proc.poll() is None:
                proc.kill()
