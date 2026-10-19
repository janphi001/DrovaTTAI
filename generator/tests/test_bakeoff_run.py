import sys
from pathlib import Path

import pytest

from drova_voice.bakeoff import (
    BakeoffResult,
    Sample,
    VoiceSpec,
    load_voice_specs,
    run_bakeoff,
    write_sheet,
)
from drova_voice.engines.client import EngineClient, EngineError
from drova_voice.engines.protocol import SynthResponse

SAMPLES = [
    Sample(
        "short_00",
        "NPC_A_de",
        "Plh_1",
        "Hmpf.",
        "Hmpf.",
        {
            "emotion": "neutral",
            "intensity": 0.0,
            "events": [],
            "emphasis": [],
            "notes": [],
            "source": "default",
        },
        "short",
    ),
    Sample(
        "stage_01",
        "NPC_A_de",
        "Plh_2",
        "*seufzt* Na <gut>.",
        "Na gut & so.",
        {
            "emotion": "neutral",
            "intensity": 0.0,
            "events": [{"tag": "sigh", "pos": 0}],
            "emphasis": [],
            "notes": [],
            "source": "stage",
        },
        "stage",
    ),
]


class FakeClient:
    def __init__(self):
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def synth(self, req):
        self.requests.append(req)
        Path(req.out_path).write_bytes(b"RIFF")
        return SynthResponse(
            id=req.id, ok=True, out_path=req.out_path, sample_rate=22050, duration=1.0
        )


def test_voice_slug():
    assert VoiceSpec("xtts", voice="Ana Florence").slug == "ana-florence"
    assert (
        VoiceSpec("chatterbox", reference="voices/bakeoff/xtts-viktor-eka.wav").slug
        == "xtts-viktor-eka"
    )
    assert VoiceSpec("chatterbox").slug == "default"


def test_run_writes_final_files_and_renders_per_engine(tmp_path):
    client = FakeClient()
    results = run_bakeoff(
        SAMPLES, [VoiceSpec("kitten", voice="German")], lambda engine: client, tmp_path
    )
    assert all(r.ok for r in results)
    assert (tmp_path / "kitten" / "german" / "short_00.wav").exists()
    assert not list(tmp_path.rglob("*.part.wav"))
    assert client.requests[1].text == "Na gut & so."  # Laut-Tags werden für Kitten nicht gerendert


def test_resume_skips_finished_and_ignores_partial(tmp_path):
    run_bakeoff(SAMPLES[:1], [VoiceSpec("fake")], lambda e: FakeClient(), tmp_path)
    stale = tmp_path / "fake" / "default" / "stage_01.part.wav"
    stale.write_bytes(b"halb")
    client = FakeClient()
    results = run_bakeoff(SAMPLES, [VoiceSpec("fake")], lambda e: client, tmp_path)
    assert [r.id for r in client.requests] == ["fake/default/stage_01"]
    assert (tmp_path / "fake" / "default" / "stage_01.wav").exists()
    assert len(results) == 2


def test_failed_synth_leaves_no_file(tmp_path):
    class Failing(FakeClient):
        def synth(self, req):
            Path(req.out_path).write_bytes(b"x")
            return SynthResponse(id=req.id, ok=False, error="kaputt")

    results = run_bakeoff(SAMPLES[:1], [VoiceSpec("fake")], lambda e: Failing(), tmp_path)
    assert not results[0].ok and results[0].error == "kaputt"
    assert not list((tmp_path / "fake").rglob("*.wav"))


def test_sheet_escapes_text_and_links_audio(tmp_path):
    wav0 = _finished_wav(tmp_path, "fake", "default", SAMPLES[0])
    results = [
        BakeoffResult("fake", "default", "short_00", True, str(wav0), 1.0, 0.5, None),
        BakeoffResult("fake", "default", "stage_01", False, None, None, 0.1, "kaputt"),
    ]
    html = write_sheet(SAMPLES, results, tmp_path).read_text(encoding="utf-8")
    assert 'src="fake/default/short_00.wav"' in html
    assert "Na gut &amp; so." in html
    assert "kaputt" in html
    assert "0.50" in html  # Echtzeitfaktor 0.5 s / 1.0 s


NEUTRAL = {
    "emotion": "neutral",
    "intensity": 0.0,
    "events": [],
    "emphasis": [],
    "notes": [],
    "source": "default",
}


def _finished_wav(root, engine, slug, sample):
    """Eine fertige Datei wie run_bakeoff sie hinterlaesst: wav plus Sidecar mit dem gerenderten Text."""
    from drova_voice.emotions import EmotionTag
    from drova_voice.render import render_request

    wav = Path(root) / engine / slug / f"{sample.sample_id}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(b"RIFF")
    wav.with_suffix(".txt").write_bytes(
        render_request(engine, sample.text, EmotionTag.from_dict(sample.emotion))[0].encode("utf-8")
    )
    return wav


class TextClient(FakeClient):
    """Schreibt den gesendeten Text als Dateiinhalt, damit der Test den Inhalt prüfen kann."""

    def synth(self, req):
        self.requests.append(req)
        Path(req.out_path).write_bytes(req.text.encode("utf-8"))
        return SynthResponse(
            id=req.id, ok=True, out_path=req.out_path, sample_rate=22050, duration=1.0
        )


def test_changed_text_resynthesizes_and_same_text_skips(tmp_path):
    a = Sample("short_00", "NPC_A_de", "Plh_1", "raw", "Text A.", NEUTRAL, "short")
    b = Sample("short_00", "NPC_A_de", "Plh_1", "raw", "Text B.", NEUTRAL, "short")
    first = TextClient()
    run_bakeoff([a], [VoiceSpec("fake")], lambda e: first, tmp_path)
    assert [r.text for r in first.requests] == ["Text A."]

    second = TextClient()
    run_bakeoff([b], [VoiceSpec("fake")], lambda e: second, tmp_path)
    assert [r.text for r in second.requests] == ["Text B."]
    wav = tmp_path / "fake" / "default" / "short_00.wav"
    assert wav.read_bytes() == b"Text B."
    assert wav.with_suffix(".txt").read_bytes() == b"Text B."

    third = TextClient()
    run_bakeoff([b], [VoiceSpec("fake")], lambda e: third, tmp_path)
    assert third.requests == []


def test_duplicate_slug_for_same_engine_is_rejected(tmp_path):
    p = tmp_path / "voices.yaml"
    p.write_text(
        '- {engine: xtts, voice: "Ana Florence"}\n- {engine: xtts, voice: "ana-florence"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc:
        load_voice_specs(p, tmp_path)
    assert "xtts" in str(exc.value) and "ana-florence" in str(exc.value)


def test_same_slug_for_different_engines_is_allowed(tmp_path):
    p = tmp_path / "voices.yaml"
    p.write_text(
        "- {engine: kitten, voice: German}\n- {engine: xtts, voice: German}\n", encoding="utf-8"
    )
    assert len(load_voice_specs(p, tmp_path)) == 2


def test_on_result_gets_every_result_in_order(tmp_path):
    got = []
    results = run_bakeoff(
        SAMPLES, [VoiceSpec("fake")], lambda e: FakeClient(), tmp_path, on_result=got.append
    )
    assert got == results
    assert [r.sample_id for r in got] == ["short_00", "stage_01"]
    again = []
    results2 = run_bakeoff(
        SAMPLES, [VoiceSpec("fake")], lambda e: FakeClient(), tmp_path, on_result=again.append
    )
    assert again == results2 and all(r.ok and r.seconds == 0.0 for r in again)


def test_keyboard_interrupt_keeps_already_reported_results(tmp_path):
    class InterruptOnSecond(FakeClient):
        def synth(self, req):
            if self.requests:
                raise KeyboardInterrupt
            return super().synth(req)

    got = []
    with pytest.raises(KeyboardInterrupt):
        run_bakeoff(
            SAMPLES,
            [VoiceSpec("fake")],
            lambda e: InterruptOnSecond(),
            tmp_path,
            on_result=got.append,
        )
    assert [r.sample_id for r in got] == ["short_00"]
    assert (tmp_path / "fake" / "default" / "short_00.wav").exists()
    assert not (tmp_path / "fake" / "default" / "stage_01.wav").exists()


def test_engine_that_fails_to_start_is_recorded_and_others_continue(tmp_path):
    def factory(engine):
        if engine == "xtts":
            raise EngineError("Worker nicht bereit")
        return FakeClient()

    results = run_bakeoff(SAMPLES, [VoiceSpec("xtts"), VoiceSpec("fake")], factory, tmp_path)
    broken = [r for r in results if r.engine == "xtts"]
    assert len(broken) == 1
    assert not broken[0].ok and broken[0].sample_id == "short_00"
    assert "Worker nicht bereit" in broken[0].error
    fake = [r for r in results if r.engine == "fake"]
    assert len(fake) == 2 and all(r.ok for r in fake)


def test_engine_error_during_synth_skips_rest_of_that_engine(tmp_path):
    class Dying(FakeClient):
        def synth(self, req):
            raise EngineError("Worker beendet")

    results = run_bakeoff(
        SAMPLES,
        [VoiceSpec("kitten"), VoiceSpec("fake")],
        lambda e: Dying() if e == "kitten" else FakeClient(),
        tmp_path,
    )
    dying = [r for r in results if r.engine == "kitten"]
    assert [r.sample_id for r in dying] == ["short_00"] and not dying[0].ok
    assert [r.sample_id for r in results if r.engine == "fake"] == ["short_00", "stage_01"]


def test_sheet_falls_back_to_file_uri_for_wav_outside_out_dir(tmp_path):
    outside = _finished_wav(tmp_path / "elsewhere", "fake", "default", SAMPLES[0])
    results = [BakeoffResult("fake", "default", "short_00", True, str(outside), 1.0, 0.5, None)]
    page = write_sheet(SAMPLES[:1], results, tmp_path / "out").read_text(encoding="utf-8")
    assert outside.resolve().as_uri() in page


SILENT_WORKER = """
import sys
sys.path.insert(0, COMMON)
from worker_loop import serve

def load():
    return None

def synth(_state, req):
    return 22050, 0.1  # schreibt absichtlich nichts

serve("fake", "stub-silent", load, synth)
"""


def test_stale_part_file_from_killed_run_is_not_promoted(tmp_path, guarded):
    common = Path(__file__).resolve().parents[1] / "workers" / "_common"
    stub = tmp_path / "silent_worker.py"
    stub.write_text(SILENT_WORKER.replace("COMMON", repr(str(common))), encoding="utf-8")
    part = tmp_path / "fake" / "default" / "short_00.part.wav"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"alter Rest")

    results = guarded(
        lambda: run_bakeoff(
            SAMPLES[:1],
            [VoiceSpec("fake")],
            lambda e: EngineClient([sys.executable, str(stub)]),
            tmp_path,
        )
    )
    assert len(results) == 1 and not results[0].ok
    assert results[0].error == f"Keine Audiodatei geschrieben: {part}"
    assert not (tmp_path / "fake" / "default" / "short_00.wav").exists()
    assert not (tmp_path / "fake" / "default" / "short_00.txt").exists()
    assert not part.exists()


def test_sheet_hides_audio_whose_text_no_longer_matches_the_line(tmp_path):
    wav = _finished_wav(tmp_path, "fake", "default", SAMPLES[0])
    wav.with_suffix(".txt").write_bytes(b"ein ganz anderer Text")  # Stichprobe wurde neu gezogen
    results = [BakeoffResult("fake", "default", "short_00", True, str(wav), 1.0, 0.5, None)]
    page = write_sheet(SAMPLES[:1], results, tmp_path).read_text(encoding="utf-8")
    assert "<audio" not in page and "veraltet" in page


def test_sheet_summary_only_counts_current_samples(tmp_path):
    wav = _finished_wav(tmp_path, "fake", "default", SAMPLES[0])
    results = [
        BakeoffResult("fake", "default", "short_00", True, str(wav), 1.0, 0.5, None),
        BakeoffResult(
            "fake", "default", "alt_99", True, str(wav), 100.0, 100.0, None
        ),  # gehoert zu einer frueheren Stichprobe
    ]
    page = write_sheet(SAMPLES[:1], results, tmp_path).read_text(encoding="utf-8")
    assert "0.50" in page and "100.0 s" not in page


def test_finished_wav_is_put_in_place_even_if_another_program_briefly_holds_the_old_one(
    tmp_path, monkeypatch
):
    import os

    import drova_voice.jsonl as jsonl_mod

    real, failures = os.replace, []

    def flaky(src, dst):
        if len(failures) < 2:
            failures.append(1)
            raise PermissionError(5, "Zugriff verweigert")
        real(src, dst)

    monkeypatch.setattr(jsonl_mod.os, "replace", flaky)
    monkeypatch.setattr(jsonl_mod.time, "sleep", lambda _s: None)
    results = run_bakeoff(SAMPLES[:1], [VoiceSpec("fake")], lambda e: FakeClient(), tmp_path)
    assert (
        results[0].ok
        and (tmp_path / "fake" / "default" / "short_00.wav").exists()
        and len(failures) == 2
    )
