import json

from drova_voice.cli import main
from drova_voice.jsonl import latest_by_id, read_jsonl_lenient
from drova_voice.lines import read_lines
from drova_voice.synth import MAX_ATTEMPTS

NPC_TREE = "DT_Test_NPC_Mira|Dialog/NPC_Mira|"


def run(pipeline_repo, *args):
    return main(["--config", str(pipeline_repo.cfg), *args])


def test_synth_fake_engine_writes_results_and_cache(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--workers", "2")) == 0
    rows = latest_by_id(read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl"))
    assert sorted(rows) == [NPC_TREE + "Plh_1", NPC_TREE + "Plh_2", NPC_TREE + "Plh_3"]
    assert all(r["ok"] for r in rows.values())
    assert len(list((pipeline_repo.repo / "cache" / "synth").glob("*.wav"))) == 3
    out = capsys.readouterr().out
    assert "3 erzeugt" in out and "übersprungen: gvar_value: 1, player_choice: 1, unspeakable: 1" in out


def test_synth_second_run_uses_the_cache(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    capsys.readouterr()
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    assert "0 neu erzeugt" in capsys.readouterr().out


def test_synth_second_run_does_not_append_cached_rows(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    path = pipeline_repo.data / "synth" / "results.jsonl"
    first = read_jsonl_lenient(path)
    assert len(first) == 3
    raw = path.read_bytes()
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    assert path.read_bytes() == raw
    assert read_jsonl_lenient(path) == first


def test_synth_reports_speaker_without_voice(pipeline_repo, guarded, capsys):
    (pipeline_repo.casting / "casting.yaml").write_text("default_player: leon\nspeakers: {}\n", encoding="utf-8")
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    assert "no_voice: 2" in capsys.readouterr().out


def test_synth_limit(pipeline_repo, guarded):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--limit", "1")) == 0
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl")
    assert len(rows) == 1


def test_synth_records_the_characters_sent(pipeline_repo, guarded, capsys):
    texts = (
        "Der Weg nach Norden ist weit.",
        "Wohin soll ich dich führen?",
        "Zum Brunnen, bitte.",
    )
    chars = sum(len(text) for text in texts)
    utf8_bytes = sum(len(text.encode("utf-8")) for text in texts)
    assert utf8_bytes > chars
    run(pipeline_repo, "extract")
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    first = capsys.readouterr().out
    guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake"))
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "usage.jsonl")
    assert rows[0]["engine"] == "fake" and rows[0]["requests"] == 3
    assert rows[0]["chars"] == chars and rows[0]["utf8_bytes"] == utf8_bytes
    assert rows[1]["chars"] == 0 and rows[1]["utf8_bytes"] == 0 and rows[1]["requests"] == 0
    assert f"Zeichen neu an fake gesendet: {chars} ({utf8_bytes} UTF-8-Bytes, 3 Anfragen)" in first
    assert f"insgesamt bisher: {chars} ({utf8_bytes} UTF-8-Bytes)" in first


def test_utf8_budget_sends_nothing_and_writes_no_error_rows(pipeline_repo, guarded, capsys):
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake", "--max-utf8-bytes", "1", "--workers", "4")) == 1
    err = capsys.readouterr().err
    assert "UTF-8-Budget erreicht" in err and "Traceback" not in err
    assert read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl") == []
    usage = read_jsonl_lenient(pipeline_repo.data / "synth" / "usage.jsonl")
    assert usage[0]["requests"] == 0 and usage[0]["utf8_bytes"] == 0 and usage[0]["chars"] == 0


def test_utf8_budget_rejects_zero(pipeline_repo, capsys):
    run(pipeline_repo, "extract")
    assert run(pipeline_repo, "synth", "--engine", "fake", "--max-utf8-bytes", "0") == 2
    assert "--max-utf8-bytes" in capsys.readouterr().err


def test_usage_total_counts_old_rows_without_byte_field(pipeline_repo, guarded, capsys):
    usage = pipeline_repo.data / "synth"
    usage.mkdir(parents=True)
    (usage / "usage.jsonl").write_text(
        '{"at": "2026-10-01T00:00:00", "engine": "fake", "lines": 1, "chars": 40}\n', encoding="utf-8")
    texts = ("Der Weg nach Norden ist weit.", "Wohin soll ich dich führen?", "Zum Brunnen, bitte.")
    chars = 40 + sum(len(text) for text in texts)
    utf8_bytes = 40 + sum(len(text.encode("utf-8")) for text in texts)
    run(pipeline_repo, "extract")
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 0
    out = capsys.readouterr().out
    assert f"insgesamt bisher: {chars} ({utf8_bytes} UTF-8-Bytes)" in out


def test_synth_counts_retries_and_failed_fake_requests(pipeline_repo, guarded, capsys):
    fail = "FAIL Grüße vom Test."
    loc = (pipeline_repo.game / "Drova_Data" / "StreamingAssets" / "Localization" / "de" / "Dialog"
           / "NPC_Mira_de.loc")
    loc.write_text(loc.read_text(encoding="utf-8") + f"Plh_7 {{ {fail} }}\n", encoding="utf-8")
    manifest_path = pipeline_repo.data / "export" / "de" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["lines"].append({
        "id": "DT_Test_NPC_Mira|Dialog/NPC_Mira|Plh_7", "tree": "DT_Test_NPC_Mira", "nodeId": 7,
        "nodeType": "statement", "actorName": "Mira", "category": "dialog", "generic": False,
        "locaPath": "Dialog/NPC_Mira", "locaKey": "Plh_7", "text": "x", "gvars": [],
    })
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run(pipeline_repo, "extract")
    speech = {line.loca_key: line.speech for line in read_lines(pipeline_repo.data / "lines.jsonl") if not line.skip}
    assert speech["Plh_7"] == fail
    ok = ("Der Weg nach Norden ist weit.", "Wohin soll ich dich führen?", "Zum Brunnen, bitte.")
    assert set(ok) <= set(speech.values())
    first_chars = sum(len(text) for text in ok) + MAX_ATTEMPTS * len(fail)
    first_bytes = sum(len(text.encode("utf-8")) for text in ok) + MAX_ATTEMPTS * len(fail.encode("utf-8"))
    first_requests = len(ok) + MAX_ATTEMPTS
    assert first_bytes > first_chars
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 1
    first = capsys.readouterr().out
    assert guarded(lambda: run(pipeline_repo, "synth", "--engine", "fake")) == 1
    second = capsys.readouterr().out
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "usage.jsonl")
    assert rows[0]["lines"] == len(ok) and rows[0]["requests"] == first_requests
    assert rows[0]["chars"] == first_chars and rows[0]["utf8_bytes"] == first_bytes
    retry_chars, retry_bytes = MAX_ATTEMPTS * len(fail), MAX_ATTEMPTS * len(fail.encode("utf-8"))
    assert rows[1]["lines"] == 0 and rows[1]["requests"] == MAX_ATTEMPTS
    assert rows[1]["chars"] == retry_chars and rows[1]["utf8_bytes"] == retry_bytes
    assert f"Zeichen neu an fake gesendet: {first_chars} ({first_bytes} UTF-8-Bytes, {first_requests} Anfragen)" in first
    assert (f"insgesamt bisher: {first_chars + retry_chars} ({first_bytes + retry_bytes} UTF-8-Bytes)") in second


def test_an_aborted_synth_still_records_what_finished(pipeline_repo, guarded, monkeypatch):
    import pytest
    from drova_voice import pipeline
    from drova_voice.synth import SynthResult

    def half_then_abort(jobs, *args, on_result=None, **kwargs):
        on_result(SynthResult(id=jobs[0].id, key="k", wav="a.wav", duration=1.0, ok=True,
                              attempts=1, flagged=False, error=None))
        raise KeyboardInterrupt

    run(pipeline_repo, "extract")
    monkeypatch.setattr(pipeline, "run_synth", half_then_abort)
    with pytest.raises(KeyboardInterrupt):
        run(pipeline_repo, "synth", "--engine", "fake")
    rows = read_jsonl_lenient(pipeline_repo.data / "synth" / "results.jsonl")
    assert [r["wav"] for r in rows] == ["a.wav"]
