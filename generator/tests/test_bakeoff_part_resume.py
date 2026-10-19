"""Bakeoff nimmt eine fertige Part-Datei nach einem Absturz wieder auf, ohne neu anzufragen."""

import io
import wave
from pathlib import Path

import drova_voice.bakeoff as bakeoff_mod
from drova_voice.bakeoff import Sample, VoiceSpec, run_bakeoff, write_sheet
from drova_voice.engines.protocol import SynthResponse


def _wav(frames: bytes, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)
    return buf.getvalue()


def _sample(sample_id: str, text: str) -> Sample:
    return Sample(sample_id, "NPC_A_de", "K1", "raw", text, {}, "short")


class _Fake:
    def __init__(self):
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def synth(self, req):
        self.requests.append(req)
        Path(req.out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(req.out_path).write_bytes(_wav(b"\x11\x22" * 4))
        return SynthResponse(
            id=req.id, ok=True, out_path=req.out_path, sample_rate=8000, duration=0.01
        )


def _run(tmp_path, samples, client=None):
    opened = []
    holder = client if client is not None else _Fake()

    def factory(engine):
        opened.append(engine)
        return holder

    results = run_bakeoff(samples, [VoiceSpec("fake")], factory, tmp_path)
    return results, holder, opened


def _place(root: Path, name: str, data: bytes) -> Path:
    path = root / "fake" / "default" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_finished_part_without_sidecar_is_adopted_without_a_request(tmp_path):
    sample = _sample("short_00", "Ping.")
    audio = _wav(b"\x01\x02" * 8)
    part = _place(tmp_path, "short_00.part.wav", audio)
    results, client, opened = _run(tmp_path, [sample])
    wav = tmp_path / "fake" / "default" / "short_00.wav"
    assert opened == [] and client.requests == []
    assert len(results) == 1 and results[0].ok and results[0].seconds == 0.0
    assert results[0].wav == str(wav)
    assert wav.read_bytes() == audio
    assert not part.exists()
    assert wav.with_suffix(".txt").read_bytes() == b"Ping."
    page = write_sheet([sample], results, tmp_path).read_text(encoding="utf-8")
    assert 'src="fake/default/short_00.wav"' in page

    again, client2, opened2 = _run(tmp_path, [sample])
    assert opened2 == [] and client2.requests == []
    assert again[0].ok and again[0].seconds == 0.0


def test_truncated_part_is_requested_again(tmp_path):
    sample = _sample("short_00", "Ping.")
    _place(tmp_path, "short_00.part.wav", _wav(b"\x01\x02" * 8)[:-3])
    results, client, opened = _run(tmp_path, [sample])
    assert opened == ["fake"]
    assert [req.id for req in client.requests] == ["fake/default/short_00"]
    assert results[0].ok
    assert (tmp_path / "fake" / "default" / "short_00.wav").is_file()


def test_zero_duration_part_is_requested_again(tmp_path):
    sample = _sample("short_00", "Ping.")
    _place(tmp_path, "short_00.part.wav", _wav(b""))
    _results, client, opened = _run(tmp_path, [sample])
    assert opened == ["fake"]
    assert [req.text for req in client.requests] == ["Ping."]


def test_garbage_part_is_requested_again(tmp_path):
    sample = _sample("short_00", "Ping.")
    _place(tmp_path, "short_00.part.wav", b"halb")
    _results, client, _opened = _run(tmp_path, [sample])
    assert [req.id for req in client.requests] == ["fake/default/short_00"]


def test_finished_wav_without_sidecar_is_adopted_without_a_request(tmp_path):
    sample = _sample("short_00", "Ping.")
    audio = _wav(b"\x05\x06" * 4)
    wav = _place(tmp_path, "short_00.wav", audio)
    results, client, opened = _run(tmp_path, [sample])
    assert opened == [] and client.requests == []
    assert results[0].ok and results[0].seconds == 0.0
    assert wav.read_bytes() == audio
    assert wav.with_suffix(".txt").read_bytes() == b"Ping."


def test_finished_part_replaces_wav_when_sidecar_is_missing(tmp_path):
    sample = _sample("short_00", "Ping.")
    _place(tmp_path, "short_00.wav", _wav(b"\x01\x02" * 4))
    audio = _wav(b"\x03\x04" * 8)
    part = _place(tmp_path, "short_00.part.wav", audio)
    _results, client, opened = _run(tmp_path, [sample])
    wav = tmp_path / "fake" / "default" / "short_00.wav"
    assert opened == [] and client.requests == []
    assert wav.read_bytes() == audio
    assert not part.exists()
    assert wav.with_suffix(".txt").read_bytes() == b"Ping."


def test_matching_sidecar_adopts_part_when_wav_is_missing(tmp_path):
    sample = _sample("short_00", "Ping.")
    audio = _wav(b"\x07\x08" * 4)
    part = _place(tmp_path, "short_00.part.wav", audio)
    side = part.with_name("short_00.txt")
    side.write_bytes(b"Ping.")
    _results, client, opened = _run(tmp_path, [sample])
    wav = tmp_path / "fake" / "default" / "short_00.wav"
    assert opened == [] and client.requests == []
    assert wav.read_bytes() == audio
    assert not part.exists()
    assert side.read_bytes() == b"Ping."


def test_mismatched_sidecar_requests_again_even_if_part_is_finished(tmp_path):
    sample = _sample("short_00", "Neu.")
    wav = _place(tmp_path, "short_00.wav", _wav(b"\x01\x02" * 4))
    wav.with_suffix(".txt").write_bytes(b"Alt.")
    _place(tmp_path, "short_00.part.wav", _wav(b"\x03\x04" * 8))
    results, client, opened = _run(tmp_path, [sample])
    assert opened == ["fake"]
    assert [req.text for req in client.requests] == ["Neu."]
    assert results[0].ok
    assert wav.with_suffix(".txt").read_bytes() == b"Neu."


def test_rename_failure_keeps_the_part_and_does_not_request_it(tmp_path, monkeypatch):
    real = bakeoff_mod.replace_with_retry

    def wrapped(src, dst, attempts=40, delay=0.25):
        if Path(src).name.startswith("short_00"):
            raise PermissionError(13, "Zugriff verweigert")
        return real(src, dst, attempts=attempts, delay=delay)

    monkeypatch.setattr(bakeoff_mod, "replace_with_retry", wrapped)
    kept = _wav(b"\x01\x02" * 8)
    part = _place(tmp_path, "short_00.part.wav", kept)
    samples = [_sample("short_00", "Ping."), _sample("stage_01", "Tone.")]
    results, client, opened = _run(tmp_path, samples)
    assert [r.sample_id for r in results] == ["short_00", "stage_01"]
    assert not results[0].ok
    assert "short_00.part.wav" in results[0].error
    assert "Zugriff verweigert" in results[0].error
    assert part.read_bytes() == kept
    assert not (tmp_path / "fake" / "default" / "short_00.wav").exists()
    assert opened == ["fake"]
    assert [req.id for req in client.requests] == ["fake/default/stage_01"]
    assert (tmp_path / "fake" / "default" / "stage_01.wav").is_file()
