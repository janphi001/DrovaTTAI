import contextlib
import threading
import wave

import pytest

from drova_voice.casting import Casting
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineError
from drova_voice.engines.protocol import SynthResponse
from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line
from drova_voice.synth import (SKIP_NO_VOICE, SynthJob, build_jobs, make_key, plausible, run_synth, wav_duration)

FISH = {"lena": FishVoice("lena", "a" * 32, "Lena", "f", "de"), "leon": FishVoice("leon", "b" * 32, "Leon", "m", "de")}
CASTING = Casting("leon", {"mira": "lena"})


def line(key, speech="Der Weg nach Norden ist weit.", actor="Mira", category="dialog", skip=None):
    return Line(id=f"T|P|{key}", tree="T", loca_path="P", loca_key=key, node_type="statement", choice_index=None,
                actor=actor, category=category, generic=False, raw=speech, speech=speech, stage=(), skip=skip)


class StubClient:
    """Schreibt eine WAV-Datei mit fester Dauer; zählt Aufrufe."""
    model = "stub-1"

    def __init__(self, calls, seconds=2.0, fail_on=None, die_on=None):
        self.calls, self.seconds, self.fail_on, self.die_on = calls, seconds, fail_on, die_on
        self.lock = threading.Lock()

    def synth(self, req):
        with self.lock:
            self.calls.append(req.id)
        if self.die_on and self.die_on in req.text:
            raise EngineError("Worker beendet")
        if self.fail_on and self.fail_on in req.text:
            return SynthResponse(req.id, False, error="HTTP 500")
        rate = 8000
        with wave.open(req.out_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"\x00\x00" * int(rate * self.seconds))
        return SynthResponse(req.id, True, req.out_path, rate, self.seconds)


def factory(calls, **kw):
    return lambda engine: contextlib.nullcontext(StubClient(calls, **kw))


def job(id_, text="Der Weg nach Norden ist weit.", voice=None):
    return SynthJob(id_, text, len(text), voice, {})


def test_build_jobs_skips_and_maps_voices():
    lines = [line("Plh_1"), line("Plh_2", skip="gvar", speech=""), line("Plh_3", actor="Fremder"),
             line("Plh_4", actor="Player", category="player"), line("Plh_5", speech="…")]
    jobs, skipped = build_jobs(lines, CASTING, FISH, {}, "fish")
    assert [(j.id, j.voice) for j in jobs] == [("T|P|Plh_1", "a" * 32), ("T|P|Plh_4", "b" * 32)]
    assert skipped == {"T|P|Plh_2": "gvar", "T|P|Plh_3": SKIP_NO_VOICE, "T|P|Plh_5": "unspeakable"}


def test_build_jobs_renders_emotion_for_fish_and_ignores_voice_for_fake():
    emotions = {"T|P|Plh_1": EmotionTag("sad", 0.5, source="llm")}
    (j,), _ = build_jobs([line("Plh_1")], CASTING, FISH, emotions, "fish")
    assert j.text.startswith("[sad] ")
    (j2,), _ = build_jobs([line("Plh_1")], CASTING, FISH, emotions, "fake")
    assert j2.voice is None and j2.text == "Der Weg nach Norden ist weit."


def test_make_key_depends_on_every_input():
    base = make_key("fish", "m1", "v1", "Text", {})
    assert base == make_key("fish", "m1", "v1", "Text", {})
    assert len({base, make_key("fake", "m1", "v1", "Text", {}), make_key("fish", "m2", "v1", "Text", {}),
                make_key("fish", "m1", "v2", "Text", {}), make_key("fish", "m1", "v1", "Anderer", {}),
                make_key("fish", "m1", "v1", "Text", {"x": 1})}) == 6


def test_plausible_bounds():
    assert plausible(2.0, 34)  # 34 Zeichen ~ 2 s
    assert not plausible(0.1, 34) and not plausible(None, 34)
    assert not plausible(30.0, 34)  # viel zu lang (Halluzination)
    assert plausible(0.6, 5) and not plausible(9.0, 5)  # sehr kurze Zeilen: nur Obergrenze


def test_run_synth_writes_cache_and_second_run_makes_no_calls(tmp_path):
    calls = []
    results = run_synth([job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory(calls), tmp_path, workers=2)
    assert sorted(r.id for r in results) == ["a", "b"] and all(r.ok and not r.flagged for r in results)
    assert all(wav_duration(r.wav) == pytest.approx(2.0, abs=0.01) for r in results)
    assert len(calls) == 2
    again = run_synth([job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory(calls), tmp_path, workers=2)
    assert len(calls) == 2 and all(r.ok and r.attempts == 0 for r in again)


def test_identical_text_is_synthesized_once(tmp_path):
    calls = []
    results = run_synth([job("a"), job("b")], "fake", factory(calls), tmp_path, workers=2)
    assert len(calls) == 1 and {r.id for r in results} == {"a", "b"} and all(r.ok for r in results)


def test_stale_part_file_is_ignored_and_no_part_files_remain(tmp_path):
    key = make_key("fake", "stub-1", None, "Der Weg nach Norden ist weit.", {})
    (tmp_path / f"{key}.part.wav").write_bytes(b"halbe Datei")  # Rest eines abgebrochenen Laufs
    (r,) = run_synth([job("a")], "fake", factory([]), tmp_path)
    assert r.ok and wav_duration(r.wav) == pytest.approx(2.0, abs=0.01)
    assert list(tmp_path.glob("*.part.wav")) == []


def test_implausible_duration_is_retried_then_flagged(tmp_path):
    calls = []
    (r,) = run_synth([job("a")], "fake", factory(calls, seconds=40.0), tmp_path)
    assert r.ok and r.flagged and r.attempts == 3 and len(calls) == 3


def test_api_error_is_reported_without_wav(tmp_path):
    (r,) = run_synth([job("a", "Das schlägt FEHL.")], "fake", factory([], fail_on="FEHL"), tmp_path)
    assert not r.ok and "HTTP 500" in r.error and r.wav is None
    assert list(tmp_path.glob("*.wav")) == []


def test_dead_worker_fails_remaining_jobs_instead_of_hanging(tmp_path):
    jobs = [job("a", "Das ist STOPP hier."), job("b", "Danach kommt noch etwas."), job("c", "Und noch etwas anderes.")]
    results = run_synth(jobs, "fake", factory([], die_on="STOPP"), tmp_path, workers=1)
    by_id = {r.id: r for r in results}
    assert not by_id["a"].ok and "Worker beendet" in by_id["a"].error
    assert not by_id["b"].ok and not by_id["c"].ok


def test_on_result_is_called_for_each_job(tmp_path):
    seen = []
    run_synth([job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory([]), tmp_path, workers=2, on_result=seen.append)
    assert sorted(r.id for r in seen) == ["a", "b"]


class BoomClient(StubClient):
    """Wirft für bestimmten Text eine unerwartete Ausnahme (kein EngineError)."""

    def synth(self, req):
        if "BOOM" in req.text:
            raise RuntimeError("kaputt")
        return super().synth(req)


def test_unexpected_exception_fails_only_that_job_and_does_not_hang(tmp_path):
    jobs = [job("a", "Das ist BOOM hier."), job("b", "Danach kommt noch etwas.")]
    results = run_synth(jobs, "fake", lambda engine: contextlib.nullcontext(BoomClient([])), tmp_path, workers=1)
    by_id = {r.id: r for r in results}
    assert not by_id["a"].ok and "RuntimeError" in by_id["a"].error
    assert by_id["b"].ok  # der Worker bleibt benutzbar


def test_cached_lines_are_not_reported_as_errors_when_all_workers_are_dead(tmp_path):
    run_synth([job("b", "Danach kommt noch etwas.")], "fake", factory([]), tmp_path)
    jobs = [job("a", "Das ist STOPP hier."), job("b", "Danach kommt noch etwas.")]
    results = run_synth(jobs, "fake", factory([], die_on="STOPP"), tmp_path, workers=1)
    by_id = {r.id: r for r in results}
    assert not by_id["a"].ok and by_id["b"].ok and by_id["b"].attempts == 0


class ThenFailClient(StubClient):
    """Erster Versuch liefert unplausibel langen Ton, alle weiteren scheitern."""

    def __init__(self, calls):
        super().__init__(calls, seconds=40.0)
        self.n = 0

    def synth(self, req):
        self.n += 1
        if self.n > 1:
            return SynthResponse(req.id, False, error="HTTP 500")
        return super().synth(req)


def test_usable_audio_is_kept_when_a_later_attempt_fails(tmp_path):
    (r,) = run_synth([job("a")], "fake", lambda engine: contextlib.nullcontext(ThenFailClient([])), tmp_path)
    assert r.ok and r.flagged and wav_duration(r.wav) == pytest.approx(40.0, abs=0.1)
    assert list(tmp_path.glob("*.part.wav")) == []


def test_corrupt_cache_file_is_replaced(tmp_path):
    key = make_key("fake", "stub-1", None, "Der Weg nach Norden ist weit.", {})
    (tmp_path / f"{key}.wav").write_bytes(b"kein WAV")
    (r,) = run_synth([job("a")], "fake", factory([]), tmp_path)
    assert r.ok and r.attempts == 1 and wav_duration(r.wav) == pytest.approx(2.0, abs=0.01)
