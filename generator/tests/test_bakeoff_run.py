from pathlib import Path

from drova_voice.bakeoff import BakeoffResult, Sample, VoiceSpec, run_bakeoff, write_sheet
from drova_voice.engines.protocol import SynthResponse

SAMPLES = [
    Sample("short_00", "NPC_A_de", "Plh_1", "Hmpf.", "Hmpf.", {"emotion": "neutral", "intensity": 0.0, "events": [], "emphasis": [], "notes": [], "source": "default"}, "short"),
    Sample("stage_01", "NPC_A_de", "Plh_2", "*seufzt* Na <gut>.", "Na gut & so.", {"emotion": "neutral", "intensity": 0.0, "events": [{"tag": "sigh", "pos": 0}], "emphasis": [], "notes": [], "source": "stage"}, "stage"),
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
        return SynthResponse(id=req.id, ok=True, out_path=req.out_path, sample_rate=22050, duration=1.0)


def test_voice_slug():
    assert VoiceSpec("xtts", voice="Ana Florence").slug == "ana-florence"
    assert VoiceSpec("chatterbox", reference="voices/bakeoff/xtts-viktor-eka.wav").slug == "xtts-viktor-eka"
    assert VoiceSpec("chatterbox").slug == "default"


def test_run_writes_final_files_and_renders_per_engine(tmp_path):
    client = FakeClient()
    results = run_bakeoff(SAMPLES, [VoiceSpec("kitten", voice="German")], lambda engine: client, tmp_path)
    assert all(r.ok for r in results)
    assert (tmp_path / "kitten" / "german" / "short_00.wav").exists()
    assert not list(tmp_path.rglob("*.part.wav"))
    assert client.requests[1].text == "<sigh> Na gut & so."


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
    results = [
        BakeoffResult("fake", "default", "short_00", True, str(tmp_path / "fake" / "default" / "short_00.wav"), 1.0, 0.5, None),
        BakeoffResult("fake", "default", "stage_01", False, None, None, 0.1, "kaputt"),
    ]
    html = write_sheet(SAMPLES, results, tmp_path).read_text(encoding="utf-8")
    assert 'src="fake/default/short_00.wav"' in html
    assert "Na gut &amp; so." in html
    assert "kaputt" in html
    assert "0.50" in html  # Echtzeitfaktor 0.5 s / 1.0 s
