import sys
import wave
from pathlib import Path

import pytest

from drova_voice.engines.client import EngineClient, EngineError, worker_command
from drova_voice.engines.protocol import SynthRequest

WORKERS = Path(__file__).resolve().parents[1] / "workers"
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
