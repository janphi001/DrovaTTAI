import contextlib
import io
import threading
import wave

import pytest

from drova_voice.casting import Casting
from drova_voice.emotions import EmotionTag
from drova_voice.engines.client import EngineError
from drova_voice.engines.protocol import SynthResponse
from drova_voice.fish_voices import FishVoice
from drova_voice.lines import Line
from drova_voice.synth import (
    ABORT_AFTER,
    BUDGET_REACHED,
    MAX_ATTEMPTS,
    SKIP_NO_VOICE,
    SynthJob,
    SynthStatus,
    build_jobs,
    fatal_reason,
    make_key,
    plausible,
    run_synth,
    synth_one,
    wav_duration,
)

FISH = {
    "lena": FishVoice("lena", "a" * 32, "Lena", "f", "de"),
    "leon": FishVoice("leon", "b" * 32, "Leon", "m", "de"),
}
CASTING = Casting("leon", {"mira": "lena"})


def line(key, speech="Der Weg nach Norden ist weit.", actor="Mira", category="dialog", skip=None):
    return Line(
        id=f"T|P|{key}",
        tree="T",
        loca_path="P",
        loca_key=key,
        node_type="statement",
        choice_index=None,
        actor=actor,
        category=category,
        generic=False,
        raw=speech,
        speech=speech,
        stage=(),
        skip=skip,
    )


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
    lines = [
        line("Plh_1"),
        line("Plh_2", skip="gvar", speech=""),
        line("Plh_3", actor="Fremder"),
        line("Plh_4", actor="Player", category="player"),
        line("Plh_5", speech="…"),
    ]
    jobs, skipped = build_jobs(lines, CASTING, FISH, {}, "fish")
    assert [(j.id, j.voice) for j in jobs] == [("T|P|Plh_1", "a" * 32), ("T|P|Plh_4", "b" * 32)]
    assert skipped == {"T|P|Plh_2": "gvar", "T|P|Plh_3": SKIP_NO_VOICE, "T|P|Plh_5": "unspeakable"}


def test_build_jobs_renders_emotion_for_fish_and_ignores_voice_for_fake():
    emotions = {"T|P|Plh_1": EmotionTag("sad", 0.5, source="llm")}
    (j,), _ = build_jobs([line("Plh_1")], CASTING, FISH, emotions, "fish")
    assert j.text.startswith("[sad] ")
    (j2,), _ = build_jobs([line("Plh_1")], CASTING, FISH, emotions, "fake")
    assert j2.voice is None and j2.text == "Der Weg nach Norden ist weit."


def test_worker_posts_are_counted_and_a_given_up_worker_is_not_called_again(tmp_path):
    calls = []

    class Client:
        model = "stub-1"

        def synth(self, req):
            calls.append(req.id)
            return SynthResponse(
                req.id,
                False,
                error="Fish nicht erreichbar nach 2 Versuchen (zuletzt HTTP 500)",
                http_attempts=2,
            )

    (r,) = run_synth([job("a")], "fish", lambda engine: contextlib.nullcontext(Client()), tmp_path)
    assert calls == ["a"] and r.attempts == 2 and not r.ok


def test_sampling_and_language_change_the_cache_key():
    base = {"language": "de", "latency": "normal", "temperature": 0.7, "top_p": 0.7}
    key = make_key("fish", "fish-audio/s2.1-pro-free", "v", "Text", base)
    assert key != make_key(
        "fish", "fish-audio/s2.1-pro-free", "v", "Text", {**base, "temperature": 0.5}
    )
    assert key != make_key(
        "fish", "fish-audio/s2.1-pro-free", "v", "Text", {**base, "language": "en"}
    )


def test_make_key_depends_on_every_input():
    base = make_key("fish", "m1", "v1", "Text", {})
    assert base == make_key("fish", "m1", "v1", "Text", {})
    assert (
        len(
            {
                base,
                make_key("fake", "m1", "v1", "Text", {}),
                make_key("fish", "m2", "v1", "Text", {}),
                make_key("fish", "m1", "v2", "Text", {}),
                make_key("fish", "m1", "v1", "Anderer", {}),
                make_key("fish", "m1", "v1", "Text", {"x": 1}),
            }
        )
        == 6
    )


def test_plausible_bounds():
    assert plausible(2.0, 34)  # 34 Zeichen ~ 2 s
    assert not plausible(0.1, 34) and not plausible(None, 34)
    assert not plausible(30.0, 34)  # viel zu lang (Halluzination)
    assert plausible(0.6, 5) and not plausible(9.0, 5)  # sehr kurze Zeilen: nur Obergrenze


def test_run_synth_writes_cache_and_second_run_makes_no_calls(tmp_path):
    calls = []
    results = run_synth(
        [job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory(calls), tmp_path, workers=2
    )
    assert sorted(r.id for r in results) == ["a", "b"] and all(
        r.ok and not r.flagged for r in results
    )
    assert all(wav_duration(r.wav) == pytest.approx(2.0, abs=0.01) for r in results)
    assert len(calls) == 2
    again = run_synth(
        [job("a"), job("b", "Zum Brunnen, bitte.")], "fake", factory(calls), tmp_path, workers=2
    )
    assert len(calls) == 2 and all(r.ok and r.attempts == 0 for r in again)


def test_identical_text_is_synthesized_once(tmp_path):
    calls = []
    results = run_synth([job("a"), job("b")], "fake", factory(calls), tmp_path, workers=2)
    assert len(calls) == 1 and {r.id for r in results} == {"a", "b"} and all(r.ok for r in results)


def _wav_bytes(seconds=2.0, rate=8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def test_stale_part_file_is_ignored_and_no_part_files_remain(tmp_path):
    key = make_key("fake", "stub-1", None, "Der Weg nach Norden ist weit.", {})
    (tmp_path / f"{key}.part.wav").write_bytes(b"halbe Datei")  # Rest eines abgebrochenen Laufs
    (r,) = run_synth([job("a")], "fake", factory([]), tmp_path)
    assert r.ok and wav_duration(r.wav) == pytest.approx(2.0, abs=0.01)
    assert list(tmp_path.glob("*.part.wav")) == []


def test_complete_part_file_is_adopted_without_a_new_request(tmp_path):
    text = "Der Weg nach Norden ist weit."
    key = make_key("fake", "stub-1", None, text, {})
    (tmp_path / f"{key}.part.wav").write_bytes(_wav_bytes())
    calls = []
    (r,) = run_synth([job("a", text)], "fake", factory(calls), tmp_path)
    assert calls == [] and r.ok and r.attempts == 0
    assert wav_duration(r.wav) == pytest.approx(2.0, abs=0.01)
    assert list(tmp_path.glob("*.part.wav")) == []


def test_truncated_part_file_is_synthesized_again(tmp_path):
    text = "Der Weg nach Norden ist weit."
    key = make_key("fake", "stub-1", None, text, {})
    raw = _wav_bytes()
    (tmp_path / f"{key}.part.wav").write_bytes(raw[: len(raw) // 2])
    calls = []
    (r,) = run_synth([job("a", text)], "fake", factory(calls), tmp_path)
    assert len(calls) == 1 and r.ok and r.attempts == 1
    assert list(tmp_path.glob("*.part.wav")) == []


def test_failed_rename_keeps_the_paid_wav_for_the_next_run(tmp_path, monkeypatch):
    import drova_voice.synth as synth_mod

    calls = []
    real = synth_mod.replace_with_retry
    state = {"fail": True}

    def flaky(src, dst):
        if state["fail"]:
            raise PermissionError(5, "Zugriff verweigert")
        real(src, dst)

    monkeypatch.setattr(synth_mod, "replace_with_retry", flaky)
    status = SynthStatus()
    (r,) = run_synth([job("a")], "fake", factory(calls), tmp_path, status=status)
    assert not r.ok and "PermissionError" in (r.error or "")
    assert status.sent_requests == 1 and len(list(tmp_path.glob("*.part.wav"))) == 1
    state["fail"] = False
    again = SynthStatus()
    (r2,) = run_synth([job("a")], "fake", factory(calls), tmp_path, status=again)
    assert r2.ok and r2.attempts == 0 and len(calls) == 1 and again.sent_requests == 0


def test_implausible_duration_is_retried_then_flagged(tmp_path):
    calls = []
    (r,) = run_synth([job("a")], "fake", factory(calls, seconds=40.0), tmp_path)
    assert r.ok and r.flagged and r.attempts == 3 and len(calls) == 3


def test_api_error_is_reported_without_wav(tmp_path):
    (r,) = run_synth([job("a", "Das schlägt FEHL.")], "fake", factory([], fail_on="FEHL"), tmp_path)
    assert not r.ok and "HTTP 500" in r.error and r.wav is None
    assert list(tmp_path.glob("*.wav")) == []


def test_dead_worker_fails_remaining_jobs_instead_of_hanging(tmp_path):
    jobs = [
        job("a", "Das ist STOPP hier."),
        job("b", "Danach kommt noch etwas."),
        job("c", "Und noch etwas anderes."),
    ]
    results = run_synth(jobs, "fake", factory([], die_on="STOPP"), tmp_path, workers=1)
    by_id = {r.id: r for r in results}
    assert not by_id["a"].ok and "Worker beendet" in by_id["a"].error
    assert not by_id["b"].ok and not by_id["c"].ok


def test_on_result_is_called_for_each_job(tmp_path):
    seen = []
    run_synth(
        [job("a"), job("b", "Zum Brunnen, bitte.")],
        "fake",
        factory([]),
        tmp_path,
        workers=2,
        on_result=seen.append,
    )
    assert sorted(r.id for r in seen) == ["a", "b"]


class BoomClient(StubClient):
    """Wirft für bestimmten Text eine unerwartete Ausnahme (kein EngineError)."""

    def synth(self, req):
        if "BOOM" in req.text:
            raise RuntimeError("kaputt")
        return super().synth(req)


def test_unexpected_exception_fails_only_that_job_and_does_not_hang(tmp_path):
    jobs = [job("a", "Das ist BOOM hier."), job("b", "Danach kommt noch etwas.")]
    results = run_synth(
        jobs, "fake", lambda engine: contextlib.nullcontext(BoomClient([])), tmp_path, workers=1
    )
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
    (r,) = run_synth(
        [job("a")], "fake", lambda engine: contextlib.nullcontext(ThenFailClient([])), tmp_path
    )
    assert r.ok and r.flagged and wav_duration(r.wav) == pytest.approx(40.0, abs=0.1)
    assert list(tmp_path.glob("*.part.wav")) == []


def test_corrupt_cache_file_is_replaced(tmp_path):
    key = make_key("fake", "stub-1", None, "Der Weg nach Norden ist weit.", {})
    (tmp_path / f"{key}.wav").write_bytes(b"kein WAV")
    (r,) = run_synth([job("a")], "fake", factory([]), tmp_path)
    assert r.ok and r.attempts == 1 and wav_duration(r.wav) == pytest.approx(2.0, abs=0.01)


class QuotaClient(StubClient):
    """Wie StubClient, aber Texte mit 'quota' scheitern wie bei leerem Fish-Guthaben."""

    def synth(self, req):
        if "quota" in req.text:
            with self.lock:
                self.calls.append(req.id)
            return SynthResponse(
                req.id, False, error="Fish lehnt die Anfrage ab (HTTP 402): Payment Required"
            )
        return super().synth(req)


def quota_factory(calls):
    return lambda engine: contextlib.nullcontext(QuotaClient(calls))


def test_fatal_reason():
    assert fatal_reason("Fish lehnt die Anfrage ab (HTTP 402): x") == "Guthaben aufgebraucht"
    assert fatal_reason("Fish lehnt die Anfrage ab (HTTP 401): x").startswith("Anmeldung")
    assert (
        fatal_reason("Fish nicht erreichbar nach 5 Versuchen (zuletzt HTTP 429)")
        == "Ratenlimit erreicht"
    )
    assert (
        fatal_reason("Fish nicht erreichbar nach 5 Versuchen (zuletzt TimeoutError)")
        == "Dienst nicht erreichbar"
    )
    assert fatal_reason("HTTP 500") is None and fatal_reason(None) is None


def test_run_synth_aborts_after_repeated_fatal_errors_and_leaves_the_rest_untouched(tmp_path):
    calls, got, status = [], [], SynthStatus()
    jobs = [job(f"T|P|{i}", f"quota Nummer {i}.") for i in range(12)]
    results = run_synth(
        jobs, "fish", quota_factory(calls), tmp_path, workers=1, on_result=got.append, status=status
    )
    assert len(results) == ABORT_AFTER == len(got) and not any(r.ok for r in results)
    assert status.aborted == "Guthaben aufgebraucht" and status.not_run == 12 - ABORT_AFTER
    assert {r.id for r in results} == {
        f"T|P|{i}" for i in range(ABORT_AFTER)
    }  # für nicht gestartete Aufträge gibt es keine Zeilen


def test_a_success_resets_the_fatal_streak(tmp_path):
    texts = [
        "quota 1",
        "quota 2",
        "quota 3",
        "quota 4",
        "gut",
        "quota 5",
        "quota 6",
        "quota 7",
        "quota 8",
    ]
    jobs = [job(f"T|P|{i}", t) for i, t in enumerate(texts)]
    status = SynthStatus()
    results = run_synth(jobs, "fish", quota_factory([]), tmp_path, workers=1, status=status)
    assert len(results) == len(texts) and status.aborted is None and status.not_run == 0


def test_synth_one_reports_every_attempt_including_a_raise(tmp_path):
    sent = []

    class RaiseOnce:
        def synth(self, req):
            raise EngineError("Worker beendet")

    with pytest.raises(EngineError):
        synth_one(RaiseOnce(), job("a", "Grüße."), "k", tmp_path, on_sent=sent.append)
    assert sent == ["Grüße."]


def test_synth_one_reports_each_failed_attempt(tmp_path):
    sent = []

    class AlwaysFail:
        def synth(self, req):
            return SynthResponse(req.id, False, error="HTTP 500")

    result = synth_one(AlwaysFail(), job("a", "Grüße."), "k", tmp_path, on_sent=sent.append)
    assert not result.ok and result.attempts == MAX_ATTEMPTS and sent == ["Grüße."] * MAX_ATTEMPTS


def test_sent_usage_counts_retries_of_implausible_audio_in_utf8_bytes(tmp_path):
    text = "Grüße."
    status = SynthStatus()
    (result,) = run_synth(
        [job("a", text)], "fake", factory([], seconds=40.0), tmp_path, status=status
    )
    assert result.ok and result.flagged and result.attempts == MAX_ATTEMPTS
    assert status.sent_requests == MAX_ATTEMPTS
    assert status.sent_chars == MAX_ATTEMPTS * len(text)
    assert status.sent_bytes == MAX_ATTEMPTS * len(text.encode("utf-8"))
    assert status.sent_bytes > status.sent_chars


def test_sent_usage_counts_failed_requests(tmp_path):
    text = "Das schlägt FEHL."
    status = SynthStatus()
    (result,) = run_synth(
        [job("a", text)], "fake", factory([], fail_on="FEHL"), tmp_path, status=status
    )
    assert not result.ok and result.attempts == MAX_ATTEMPTS
    assert status.sent_requests == MAX_ATTEMPTS
    assert status.sent_chars == MAX_ATTEMPTS * len(text)
    assert status.sent_bytes == MAX_ATTEMPTS * len(text.encode("utf-8")) > status.sent_chars


def test_sent_usage_ignores_cache_hits_and_duplicate_text(tmp_path):
    text = "Gleicher Satz."
    status = SynthStatus()
    run_synth(
        [job("a", text), job("b", text)], "fake", factory([]), tmp_path, workers=2, status=status
    )
    assert (
        status.sent_requests == 1
        and status.sent_chars == len(text)
        and status.sent_bytes == len(text.encode("utf-8"))
    )
    again = SynthStatus()
    run_synth(
        [job("a", text), job("b", text)], "fake", factory([]), tmp_path, workers=2, status=again
    )
    assert again.sent_requests == 0 and again.sent_chars == 0 and again.sent_bytes == 0


def test_sent_usage_counts_rendered_text_not_the_speech_length(tmp_path):
    rendered = "[sad] Grüße."
    status = SynthStatus()
    (result,) = run_synth(
        [SynthJob("a", rendered, 6, None, {})], "fake", factory([]), tmp_path, status=status
    )
    assert result.ok and result.attempts == 1
    assert status.sent_chars == len(rendered) and status.sent_bytes == len(rendered.encode("utf-8"))
    assert status.sent_bytes > status.sent_chars


def test_sent_usage_counts_a_request_whose_worker_dies(tmp_path):
    status = SynthStatus()
    jobs = [job("a", "Das ist STOPP hier."), job("b", "Danach kommt noch etwas.")]
    results = run_synth(
        jobs, "fake", factory([], die_on="STOPP"), tmp_path, workers=1, status=status
    )
    by_id = {r.id: r for r in results}
    assert not by_id["a"].ok and not by_id["b"].ok
    assert status.sent_requests == 1 and status.sent_chars == len(jobs[0].text)


def test_parallel_workers_share_one_utf8_budget(tmp_path):
    jobs = [job(str(i), f"Zeile{i}") for i in range(8)]
    one = len(jobs[0].text.encode("utf-8"))
    calls = []
    status = SynthStatus()
    results = run_synth(
        jobs, "fake", factory(calls), tmp_path, workers=8, status=status, max_utf8_bytes=one
    )
    assert status.sent_requests == 1 and status.sent_bytes == one
    assert status.aborted == BUDGET_REACHED and status.not_run == 7
    assert len(results) == 1 and len(calls) == 1


def test_budget_uses_utf8_bytes_so_an_umlaut_blocks_a_one_byte_limit(tmp_path):
    calls = []
    status = SynthStatus()
    results = run_synth(
        [job("a", "ä"), job("b", "ö")],
        "fake",
        factory(calls),
        tmp_path,
        workers=4,
        status=status,
        max_utf8_bytes=1,
    )
    assert calls == [] and results == []
    assert status.sent_requests == 0 and status.sent_bytes == 0
    assert status.not_run == 2 and status.aborted == BUDGET_REACHED


def test_budget_stops_a_second_attempt_when_the_first_audio_is_implausible(tmp_path):
    text = "Grüße."
    status = SynthStatus()
    (r,) = run_synth(
        [job("a", text)],
        "fake",
        factory([], seconds=40.0),
        tmp_path,
        status=status,
        max_utf8_bytes=len(text.encode("utf-8")),
    )
    assert r.ok and r.flagged and r.attempts == 1
    assert status.sent_requests == 1
    assert status.sent_bytes == len(text.encode("utf-8")) > len(text)
    assert status.aborted == BUDGET_REACHED and status.not_run == 0


def test_fatal_failures_count_every_attempt_until_abort(tmp_path):
    status = SynthStatus()
    jobs = [job(f"T|P|{i}", f"quota Nummer {i}.") for i in range(12)]
    results = run_synth(jobs, "fish", quota_factory([]), tmp_path, workers=1, status=status)
    assert len(results) == ABORT_AFTER and status.not_run == 12 - ABORT_AFTER
    assert status.sent_requests == ABORT_AFTER * MAX_ATTEMPTS
    assert status.sent_chars == sum(len(j.text) * MAX_ATTEMPTS for j in jobs[:ABORT_AFTER])
    assert status.sent_bytes == status.sent_chars
