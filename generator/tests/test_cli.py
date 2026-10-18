import shutil
import io
import sys
import urllib.parse
from pathlib import Path

import pytest

from drova_voice import pipeline
from drova_voice.cli import main
from drova_voice.engines.protocol import SynthResponse
from drova_voice.jsonl import read_jsonl


def test_bakeoff_select_and_run_with_fake_engine(tmp_path, guarded):
    repo = tmp_path / "repo"
    gen = repo / "generator"
    gen.mkdir(parents=True)
    game = tmp_path / "game"
    dialog = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    dialog.mkdir(parents=True)
    (dialog / "NPC_A_de.loc").write_text("Plh_1 { Wohin führt dieser Weg eigentlich? }\n", encoding="utf-8")
    cfg = gen / "config.yaml"
    cfg.write_text(f'game_dir: "{game.as_posix()}"\n', encoding="utf-8")
    voices = gen / "voices.yaml"
    voices.write_text("- {engine: fake}\n", encoding="utf-8")

    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    samples = read_jsonl(repo / "data" / "bakeoff" / "samples.jsonl")
    assert [s["bucket"] for s in samples] == ["question"]

    assert guarded(lambda: main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices)])) == 0
    assert (repo / "out" / "bakeoff" / "fake" / "default" / "question_00.wav").exists()
    assert (repo / "out" / "bakeoff" / "index.html").exists()


LOC_TWO_QUESTIONS = "Plh_1 { Wohin führt dieser Weg eigentlich? }\nPlh_2 { Wann kommt der Regen wohl an? }\n"


def _setup(tmp_path, repo_name="repo", loc=LOC_TWO_QUESTIONS):
    repo = tmp_path / repo_name
    gen = repo / "generator"
    gen.mkdir(parents=True)
    game = tmp_path / "game"
    dialog = game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    dialog.mkdir(parents=True)
    (dialog / "NPC_A_de.loc").write_text(loc, encoding="utf-8")
    cfg = gen / "config.yaml"
    cfg.write_text(f'game_dir: "{game.as_posix()}"\n', encoding="utf-8")
    voices = gen / "voices.yaml"
    voices.write_text("- {engine: fake}\n", encoding="utf-8")
    return repo, cfg, voices


class StubClient:
    """Liefert erfolgreiche Antworten; bei interrupt_on_second wird beim zweiten Aufruf abgebrochen."""

    def __init__(self, interrupt_on_second=False, ok=True):
        self.calls = 0
        self.interrupt_on_second = interrupt_on_second
        self.ok = ok

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def synth(self, req):
        self.calls += 1
        if self.interrupt_on_second and self.calls == 2:
            raise KeyboardInterrupt
        Path(req.out_path).write_bytes(b"RIFF")
        if not self.ok:
            return SynthResponse(id=req.id, ok=False, error="kaputt")
        return SynthResponse(id=req.id, ok=True, out_path=req.out_path, sample_rate=22050, duration=1.0)


def test_interrupted_run_keeps_finished_results_on_disk(tmp_path, monkeypatch):
    repo, cfg, voices = _setup(tmp_path)
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    monkeypatch.setattr("drova_voice.cli._client", lambda engine: StubClient(interrupt_on_second=True))
    try:
        main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices)])
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("KeyboardInterrupt hätte durchgereicht werden müssen")
    persisted = read_jsonl(repo / "out" / "bakeoff" / "results.jsonl")
    assert [(r["sample_id"], r["ok"]) for r in persisted] == [("question_00", True)]


def test_run_with_unmatched_engine_returns_2(tmp_path, capsys):
    repo, cfg, voices = _setup(tmp_path)
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    assert main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices), "--engine", "nope"]) == 2
    assert "nope" in capsys.readouterr().err


def test_refs_works_without_samples_and_leaves_no_part_file(tmp_path, monkeypatch, capsys):
    repo, cfg, voices = _setup(tmp_path)  # kein select: samples.jsonl fehlt
    monkeypatch.setattr("drova_voice.cli._client", lambda engine: StubClient())
    assert main(["--config", str(cfg), "bakeoff", "refs", "--speaker", "Viktor Eka"]) == 0
    target = repo / "voices" / "bakeoff"
    assert (target / "xtts-viktor-eka.wav").exists()
    assert not list(target.glob("*.part.wav"))
    assert "->" in capsys.readouterr().out


def test_failed_refs_leaves_neither_final_nor_part_file(tmp_path, monkeypatch, capsys):
    repo, cfg, voices = _setup(tmp_path)
    monkeypatch.setattr("drova_voice.cli._client", lambda engine: StubClient(ok=False))
    assert main(["--config", str(cfg), "bakeoff", "refs", "--speaker", "Viktor Eka"]) == 1
    target = repo / "voices" / "bakeoff"
    assert not (target / "xtts-viktor-eka.wav").exists()
    assert not list(target.glob("*.wav"))
    assert "kaputt" in capsys.readouterr().out


def test_unknown_engine_is_a_german_error_with_exit_1(tmp_path, capsys):
    _, cfg, _ = _setup(tmp_path)
    assert main(["--config", str(cfg), "smoke", "nope"]) == 1
    assert "Unbekannte Engine" in capsys.readouterr().err


def test_console_with_cp1252_and_unencodable_path_does_not_crash(tmp_path, monkeypatch):
    _, cfg, _ = _setup(tmp_path, repo_name="Ωrepo")  # Ω ist nicht in cp1252
    buf = io.BytesIO()
    console = io.TextIOWrapper(buf, encoding="cp1252", write_through=True)
    monkeypatch.setattr(sys, "stdout", console)
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    console.flush()
    text = buf.getvalue().decode("cp1252")
    assert "Zeilen ->" in text and "→" not in text


def test_select_with_empty_dialog_returns_2_and_keeps_old_samples(tmp_path, capsys):
    repo, cfg, voices = _setup(tmp_path)
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    samples_path = repo / "data" / "bakeoff" / "samples.jsonl"
    before = samples_path.read_bytes()
    dialog = tmp_path / "game" / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
    (dialog / "NPC_A_de.loc").write_text("Plh_1 { *grinst* }\n", encoding="utf-8")
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 2
    assert "Keine Zeilen gefunden" in capsys.readouterr().err
    assert samples_path.read_bytes() == before


def test_select_without_dialog_dir_returns_2(tmp_path, capsys):
    _, cfg, _ = _setup(tmp_path)
    shutil.rmtree(tmp_path / "game" / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog")
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 2
    err = capsys.readouterr().err
    assert "Dialog-Ordner fehlt" in err and "Dialog" in err


@pytest.mark.parametrize("argv", [
    ["bakeoff", "select"],
    ["bakeoff", "run"],
    ["bakeoff", "sheet"],
    ["bakeoff", "refs", "--speaker", "Viktor Eka"],
    ["smoke", "fake"],
])
def test_broken_config_is_a_german_error_with_exit_2(tmp_path, capsys, argv):
    _, cfg, _ = _setup(tmp_path)
    cfg.write_text('game_dir: ""\n', encoding="utf-8")
    assert main(["--config", str(cfg), *argv]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "game_dir" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("argv", [["bakeoff", "select"], ["smoke", "fake"]])
def test_missing_config_file_is_a_german_error_with_exit_2(tmp_path, capsys, argv):
    missing = tmp_path / "gibt_es_nicht.yaml"
    assert main(["--config", str(missing), *argv]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "nicht gefunden" in err and "gibt_es_nicht.yaml" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("argv", [["bakeoff", "select"], ["smoke", "fake"]])
def test_config_path_that_cannot_be_read_returns_2(tmp_path, capsys, argv):
    folder = tmp_path / "konfig"
    folder.mkdir()  # ein Verzeichnis lässt sich nicht als Konfigurationsdatei lesen
    assert main(["--config", str(folder), *argv]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "nicht lesbar" in err
    assert "Traceback" not in err


def test_refs_writes_the_spoken_text_next_to_each_reference(tmp_path, monkeypatch):
    from drova_voice.bakeoff import REF_TEXT
    repo, cfg, voices = _setup(tmp_path)
    monkeypatch.setattr("drova_voice.cli._client", lambda engine: StubClient())
    assert main(["--config", str(cfg), "bakeoff", "refs", "--speaker", "Viktor Eka"]) == 0
    assert (repo / "voices" / "bakeoff" / "xtts-viktor-eka.txt").read_text(encoding="utf-8") == REF_TEXT


def test_failed_refs_leaves_no_text_file(tmp_path, monkeypatch):
    repo, cfg, voices = _setup(tmp_path)
    monkeypatch.setattr("drova_voice.cli._client", lambda engine: StubClient(ok=False))
    assert main(["--config", str(cfg), "bakeoff", "refs", "--speaker", "Viktor Eka"]) == 1
    assert not list((repo / "voices" / "bakeoff").glob("*.txt"))


def test_run_refuses_a_missing_reference_with_a_clear_message(tmp_path, capsys):
    repo, cfg, voices = _setup(tmp_path)
    voices.write_text("- {engine: kitten, reference: voices/bakeoff/xtts-fehlt.wav}\n", encoding="utf-8")
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    assert main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices)]) == 2
    err = capsys.readouterr().err
    assert "xtts-fehlt.wav" in err and "refs" in err


def test_cli_errors_redact_the_fish_key_and_have_no_traceback(tmp_path, monkeypatch, capsys):
    _, cfg, _ = _setup(tmp_path)
    key = "sk-test-geheim-123"
    monkeypatch.setenv("FISH_API_KEY", key)
    encoded = urllib.parse.quote(key, safe="")

    def boom(_cfg, _args):
        raise ValueError(f"siehe {key} und {encoded}")

    monkeypatch.setitem(pipeline.HANDLERS, "report", boom)
    assert main(["--config", str(cfg), "report"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "Traceback" not in err
    assert key not in err and encoded not in err and "geheim" not in err and "***" in err


def test_corrupt_lines_file_is_a_german_error_without_traceback(tmp_path, capsys):
    repo, cfg, _ = _setup(tmp_path)
    path = repo / "data" / "lines.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("{\n", encoding="utf-8")
    assert main(["--config", str(cfg), "synth", "--engine", "fake"]) == 2
    err = capsys.readouterr().err
    assert "FEHLER:" in err and "Traceback" not in err


def test_run_refuses_a_kitten_reference_without_transcript(tmp_path, capsys):
    repo, cfg, voices = _setup(tmp_path)
    ref = repo / "voices" / "bakeoff" / "ohne-text.wav"
    ref.parent.mkdir(parents=True)
    ref.write_bytes(b"RIFF")
    voices.write_text("- {engine: kitten, reference: voices/bakeoff/ohne-text.wav}\n", encoding="utf-8")
    assert main(["--config", str(cfg), "bakeoff", "select", "--per-bucket", "2"]) == 0
    assert main(["--config", str(cfg), "bakeoff", "run", "--voices", str(voices)]) == 2
    assert "ohne-text.txt" in capsys.readouterr().err
