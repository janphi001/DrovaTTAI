"""Die echten Engine-Worker laufen in fremden venvs mit torch – hier prüfen wir nur, was ohne torch geht."""
from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

WORKERS = Path(__file__).resolve().parents[1] / "workers"
ENGINES = {"kitten": "KittenML/kitten-tts-2", "chatterbox": "ResembleAI/chatterbox-multilingual", "xtts": "tts_models/multilingual/multi-dataset/xtts_v2"}
# Alles, was ein Worker VOR serve() importieren darf (Ledger Task 9: schwere Imports gehören in load()/synth()).
ALLOWED_TOP_LEVEL = {"__future__", "os", "sys", "pathlib", "worker_loop"}


def _load_module(engine: str):
    path = WORKERS / engine / "worker.py"
    spec = importlib.util.spec_from_file_location(f"_worker_{engine}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("engine", ENGINES)
def test_worker_files_exist(engine):
    for name in ("worker.py", "requirements.txt", "README.md"):
        assert (WORKERS / engine / name).is_file(), f"{engine}/{name} fehlt"


@pytest.mark.parametrize("engine", ENGINES)
def test_worker_imports_nothing_heavy_before_serve(engine):
    tree = ast.parse((WORKERS / engine / "worker.py").read_text(encoding="utf-8"))
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= ALLOWED_TOP_LEVEL, f"{engine}: schwere Imports auf Modulebene: {imported - ALLOWED_TOP_LEVEL}"


@pytest.mark.parametrize("engine,model", ENGINES.items())
def test_worker_module_loads_without_torch_and_exposes_model(engine, model):
    module = _load_module(engine)  # würde ohne torch scheitern, wenn Imports nicht lazy wären
    assert module.MODEL == model
    assert callable(module.load) and callable(module.synth)


def test_xtts_refuses_to_load_without_cpml_consent(monkeypatch):
    monkeypatch.delenv("COQUI_TOS_AGREED", raising=False)
    with pytest.raises(RuntimeError, match="COQUI_TOS_AGREED"):
        _load_module("xtts").load()


class _FakeSoundfile(types.ModuleType):
    def __init__(self):
        super().__init__("soundfile")
        self.written = []

    def write(self, path, data, rate):
        self.written.append((path, len(data), rate))


def test_kitten_synth_uses_voice_without_reference_and_reference_with_it(monkeypatch, tmp_path):
    fake_sf = _FakeSoundfile()
    monkeypatch.setitem(sys.modules, "soundfile", fake_sf)
    calls = []

    class FakeModel:
        sample_rate = 24000

        def generate(self, text, **kwargs):
            calls.append((text, kwargs))
            return [0.0] * 24000

    module = _load_module("kitten")
    rate, seconds = module.synth(FakeModel(), {"text": "Hallo", "out_path": "a.wav", "voice": "Bruno"})
    assert (rate, seconds) == (24000, 1.0)
    assert calls[-1] == ("Hallo", {"normalize": False, "voice": "Bruno"})
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x")
    ref.with_suffix(".txt").write_text("Ich bleibe.", encoding="utf-8")
    module.synth(FakeModel(), {"text": "Hallo", "out_path": "b.wav", "reference": str(ref)})
    assert calls[-1] == ("Hallo", {"normalize": False, "reference": str(ref), "reference_text": "Ich bleibe."})
    assert [w[0] for w in fake_sf.written] == ["a.wav", "b.wav"]


def _kitten_with_fake_model(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", _FakeSoundfile())
    calls = []

    class FakeModel:
        sample_rate = 24000

        def generate(self, text, **kwargs):
            calls.append(kwargs)
            return [0.0] * 24000

    return _load_module("kitten"), FakeModel(), calls


def test_kitten_clone_passes_the_known_transcript_instead_of_letting_whisper_guess(monkeypatch, tmp_path):
    module, model, calls = _kitten_with_fake_model(monkeypatch)
    (tmp_path / "ref.wav").write_bytes(b"x")
    (tmp_path / "ref.txt").write_text("Ich bleibe.", encoding="utf-8")
    module.synth(model, {"text": "Hallo", "out_path": "a.wav", "reference": str(tmp_path / "ref.wav")})
    assert calls[-1]["reference_text"] == "Ich bleibe."


def test_kitten_clone_without_transcript_fails_instead_of_downloading_whisper(monkeypatch, tmp_path):
    module, model, calls = _kitten_with_fake_model(monkeypatch)
    (tmp_path / "ref.wav").write_bytes(b"x")
    with pytest.raises(ValueError, match="Whisper"):
        module.synth(model, {"text": "Hallo", "out_path": "a.wav", "reference": str(tmp_path / "ref.wav")})
    assert not calls


def test_kitten_passes_the_preset_from_params(monkeypatch):
    module, model, calls = _kitten_with_fake_model(monkeypatch)
    module.synth(model, {"text": "Hallo", "out_path": "a.wav", "voice": "Bruno", "params": {"preset": "expressive"}})
    assert calls[-1]["preset"] == "expressive"
    module.synth(model, {"text": "Hallo", "out_path": "b.wav", "voice": "Bruno"})
    assert "preset" not in calls[-1]


class _FakeWav:
    shape = (1, 24000)

    def squeeze(self, _dim):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return [0.0] * 24000


class _FakeChatterbox:
    sr = 24000

    def __init__(self):
        self.conds = "eingebaut"
        self._builtin_conds = self.conds  # so setzt load() es
        self._ref_conds = {}
        self.prepared = []
        self.seen = []

    def prepare_conditionals(self, path, exaggeration=0.5):
        self.prepared.append(path)
        self.conds = f"conds:{path}"

    def generate(self, text, language_id, audio_prompt_path=None, exaggeration=0.5, cfg_weight=0.5):
        self.seen.append((self.conds, audio_prompt_path))
        return _FakeWav()


def test_chatterbox_reference_does_not_leak_into_the_next_default_voice_request(monkeypatch):
    fake_sf = _FakeSoundfile()
    monkeypatch.setitem(sys.modules, "soundfile", fake_sf)
    module, model = _load_module("chatterbox"), _FakeChatterbox()
    module.synth(model, {"text": "a", "out_path": "1.wav", "reference": "ref.wav"})
    module.synth(model, {"text": "b", "out_path": "2.wav"})
    assert model.seen == [("conds:ref.wav", None), ("eingebaut", None)]


def test_chatterbox_embeds_each_reference_only_once(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", _FakeSoundfile())
    module, model = _load_module("chatterbox"), _FakeChatterbox()
    for i in range(3):
        module.synth(model, {"text": "a", "out_path": f"{i}.wav", "reference": "ref.wav"})
    assert model.prepared == ["ref.wav"]


def test_chatterbox_writes_through_soundfile_like_the_other_workers(monkeypatch):
    fake_sf = _FakeSoundfile()
    monkeypatch.setitem(sys.modules, "soundfile", fake_sf)
    module, model = _load_module("chatterbox"), _FakeChatterbox()
    assert module.synth(model, {"text": "a", "out_path": "x.wav"}) == (24000, 1.0)
    assert fake_sf.written == [("x.wav", 24000, 24000)]
