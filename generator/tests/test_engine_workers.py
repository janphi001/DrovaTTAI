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


def test_kitten_synth_uses_voice_without_reference_and_reference_with_it(monkeypatch):
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
    module.synth(FakeModel(), {"text": "Hallo", "out_path": "b.wav", "reference": "ref.wav"})
    assert calls[-1] == ("Hallo", {"normalize": False, "reference": "ref.wav"})
    assert [w[0] for w in fake_sf.written] == ["a.wav", "b.wav"]
